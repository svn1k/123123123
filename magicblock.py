"""
MagicBlockClient — реальный клиент для Private Payments API.
https://payments.magicblock.app/reference
"""

import base64
import logging
import time
from urllib.parse import quote
import httpx

logger = logging.getLogger(__name__)

PAYMENTS_API = "https://payments.magicblock.app/v1/spl"

USDC_DEVNET  = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
USDC_MAINNET = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

RPC_DEVNET  = "https://api.devnet.solana.com"
RPC_MAINNET = "https://api.mainnet-beta.solana.com"
ROUTER_DEVNET = "https://devnet-router.magicblock.app"
ROUTER_MAINNET = "https://router.magicblock.app"

DEVNET_AS_VALIDATOR = "MAS1Dt9qreoRMQ14YQuhg8UTZMMzDdKhmkZMECCzk57"
DEVNET_EU_VALIDATOR = "MEUGGrYPxKk17hCr7wpT6s8dtNokZj5U2L57vjYMS8e"
DEVNET_US_VALIDATOR = "MUS3hc9TCw4cGC12vHNoYcCGzJG1txjgQLZWVoeNHNd"
TEE_VALIDATOR = "MTEWGuqxUpYZGFJQcp8tLN7x5v9BSeoFHYWQQ3n3xzo"

# MagicBlock validator RPCs
DEVNET_VALIDATOR_URLS = {
    DEVNET_AS_VALIDATOR: "https://devnet-as.magicblock.app",
    DEVNET_EU_VALIDATOR: "https://devnet-eu.magicblock.app",
    DEVNET_US_VALIDATOR: "https://devnet-us.magicblock.app",
    TEE_VALIDATOR: "https://devnet-tee.magicblock.app",
}
MAINNET_VALIDATOR_URLS = {
    DEVNET_AS_VALIDATOR: "https://as.magicblock.app",
    DEVNET_EU_VALIDATOR: "https://eu.magicblock.app",
    DEVNET_US_VALIDATOR: "https://us.magicblock.app",
    TEE_VALIDATOR: "https://mainnet-tee.magicblock.app",
}

EPHEMERAL_RPC_DEVNET  = DEVNET_VALIDATOR_URLS[DEVNET_US_VALIDATOR]
EPHEMERAL_RPC_MAINNET = MAINNET_VALIDATOR_URLS[DEVNET_US_VALIDATOR]
TEE_RPC_DEVNET = "https://devnet-tee.magicblock.app"
TEE_RPC_MAINNET = "https://mainnet-tee.magicblock.app"

USDC_DECIMALS = 6


def _to_base_units(amount_usdc: float) -> int:
    return max(1, int(round(amount_usdc * 10 ** USDC_DECIMALS)))


def _from_base_units(amount_raw, decimals: int = USDC_DECIMALS) -> float:
    try:
        return int(amount_raw) / (10 ** decimals)
    except Exception:
        return 0.0


class MagicBlockClient:
    def __init__(self, wallet_mgr, config, use_devnet=None):
        self.wallet_mgr = wallet_mgr
        self.config = config
        self.use_devnet = config.USE_DEVNET if use_devnet is None else use_devnet

        if self.use_devnet:
            self.cluster          = "devnet"
            self.mint             = USDC_DEVNET
            self.validator        = (config.MAGICBLOCK_VALIDATOR or "").strip() or None
            self.rpc_url          = RPC_DEVNET
            self.router_url       = ROUTER_DEVNET
            self.ephemeral_rpc_url = DEVNET_VALIDATOR_URLS.get(self.validator, EPHEMERAL_RPC_DEVNET)
            self.tee_rpc_url      = TEE_RPC_DEVNET
        else:
            self.cluster          = "mainnet"
            self.mint             = USDC_MAINNET
            self.validator        = (config.MAGICBLOCK_VALIDATOR or "").strip() or None
            self.rpc_url          = RPC_MAINNET
            self.router_url       = ROUTER_MAINNET
            self.ephemeral_rpc_url = MAINNET_VALIDATOR_URLS.get(self.validator, EPHEMERAL_RPC_MAINNET)
            self.tee_rpc_url      = TEE_RPC_MAINNET

    @property
    def authorization_token(self):
        if self.config.MAGICBLOCK_AUTHORIZATION:
            return self.config.MAGICBLOCK_AUTHORIZATION
        return self._ensure_authorization_token()

    def _coerce_expiry_ms(self, value) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except Exception:
                pass
        return int((time.time() + 60 * 60 * 24 * 30) * 1000)

    def _ensure_authorization_token(self) -> str:
        cached = self.wallet_mgr.get_magicblock_auth()
        now_ms = int(time.time() * 1000)
        token = cached.get("token")
        expires_at = self._coerce_expiry_ms(cached.get("expires_at", 0))
        if token and expires_at > now_ms + 5 * 60 * 1000:
            return token

        wallet = self.wallet_mgr.get_wallet_info()
        pubkey = wallet["public_key"]

        with httpx.Client(timeout=20) as http:
            challenge_resp = http.get(f"{self.tee_rpc_url}/auth/challenge", params={"pubkey": pubkey})
            challenge_resp.raise_for_status()
            challenge_json = challenge_resp.json()
            challenge = challenge_json.get("challenge")
            error = challenge_json.get("error")
            if error:
                raise ValueError(f"MagicBlock auth challenge failed: {error}")
            if not challenge:
                raise ValueError("MagicBlock auth challenge is empty.")

            signature_b58 = self.wallet_mgr.sign_message(challenge)
            logger.info(f"MagicBlock auth challenge received for {pubkey[:8]}...")
            auth_resp = http.post(
                f"{self.tee_rpc_url}/auth/login",
                json={
                    "pubkey": pubkey,
                    "challenge": challenge,
                    "signature": signature_b58,
                },
            )
            auth_json = auth_resp.json()
            if auth_resp.status_code != 200:
                raise ValueError(f"MagicBlock auth failed: {auth_json.get('error', auth_json)}")

            token = auth_json.get("token")
            if not token:
                raise ValueError("MagicBlock auth returned no token.")

            expires_at = self._coerce_expiry_ms(auth_json.get("expiresAt"))
            self.wallet_mgr.set_magicblock_auth(token, expires_at)
            logger.info(f"Obtained MagicBlock {self.cluster} auth token for {pubkey[:8]}...")
            return token

    @staticmethod
    def _dedupe_urls(urls: list[str]) -> list[str]:
        seen = set()
        result = []
        for url in urls:
            if not url or url in seen:
                continue
            seen.add(url)
            result.append(url)
        return result

    def _get_private_tee_rpc_url(self) -> str | None:
        """
        Возвращает приватный TEE RPC endpoint с токеном, если авторизация доступна.
        Для private ER/PER запросов и на mainnet, и на devnet нужен auth token.
        """
        try:
            token = self.authorization_token
        except Exception as e:
            logger.warning(f"MagicBlock auth unavailable for TEE RPC: {e}")
            return None

        if not token:
            return None
        return f"{self.tee_rpc_url}?token={quote(token, safe='')}"

    def _get_ephemeral_rpc_for_validator(self, validator: str | None) -> str:
        validator = validator or self.validator
        if self.use_devnet:
            return DEVNET_VALIDATOR_URLS.get(validator, self.ephemeral_rpc_url)
        return MAINNET_VALIDATOR_URLS.get(validator, self.ephemeral_rpc_url)

    def _get_rpc_candidates(self, send_to: str, validator: str | None = None) -> tuple[list[str], list[str]]:
        if send_to == "ephemeral":
            target_rpc = self._get_ephemeral_rpc_for_validator(validator)
            private_tee_rpc = self._get_private_tee_rpc_url() if (validator or self.validator) == TEE_VALIDATOR else None
            submit_candidates = self._dedupe_urls([
                target_rpc,
                self.router_url,
                private_tee_rpc,
            ])
            confirm_candidates = self._dedupe_urls([
                target_rpc,
                self.router_url,
                self.rpc_url,
                private_tee_rpc,
            ])
        else:
            submit_candidates = self._dedupe_urls([self.rpc_url, self.router_url])
            confirm_candidates = self._dedupe_urls([self.rpc_url, self.router_url])
        return submit_candidates, confirm_candidates

    def _get_confirm_candidates_for_submit(self, send_to: str, submit_url: str, validator: str | None = None) -> list[str]:
        if send_to != "ephemeral":
            return self._dedupe_urls([submit_url, self.rpc_url, self.router_url])

        target_rpc = self._get_ephemeral_rpc_for_validator(validator)
        private_tee_rpc = self._get_private_tee_rpc_url() if (validator or self.validator) == TEE_VALIDATOR else None
        if submit_url == target_rpc:
            return self._dedupe_urls([
                target_rpc,
                self.router_url,
                self.rpc_url,
                private_tee_rpc,
            ])
        if submit_url == self.router_url:
            return self._dedupe_urls([
                self.router_url,
                target_rpc,
                self.rpc_url,
                private_tee_rpc,
            ])
        if submit_url == private_tee_rpc:
            return self._dedupe_urls([
                private_tee_rpc,
                target_rpc,
                self.router_url,
                self.rpc_url,
            ])
        return self._dedupe_urls([
            submit_url,
            target_rpc,
            self.router_url,
            self.rpc_url,
            private_tee_rpc,
        ])

    def _get_mint_init_params(self) -> dict:
        params = {
            "mint": self.mint,
            "cluster": self.cluster,
        }
        if self.validator:
            params["validator"] = self.validator
        return params

    async def _is_mint_initialized(self) -> bool:
        params = self._get_mint_init_params()
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.get(f"{PAYMENTS_API}/is-mint-initialized", params=params)
            r.raise_for_status()
            data = r.json()
            return bool(data.get("initialized"))

    async def _initialize_mint_if_needed(self):
        try:
            initialized = await self._is_mint_initialized()
        except Exception as e:
            logger.warning(f"Mint initialization status check failed: {e}")
            return

        if initialized:
            return

        wallet = self.wallet_mgr.get_wallet_info()
        payload = {
            "owner": wallet["public_key"],
            "mint": self.mint,
            "cluster": self.cluster,
        }
        if self.validator:
            payload["validator"] = self.validator

        logger.info(f"Mint transfer queue is not initialized for {self.mint}; initializing now")
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{PAYMENTS_API}/initialize-mint", json=payload)
            if r.status_code == 422:
                logger.warning(
                    "MagicBlock initialize-mint returned 422; continuing without explicit mint init. "
                    f"payload={payload} body={r.text[:500]}"
                )
                return
            if not r.is_success:
                raise ValueError(f"Initialize mint failed {r.status_code}: {r.text[:300]}")
            tx_data = r.json()

        send_to = tx_data.get("sendTo", "base")
        if send_to == "base":
            self._sign_and_send_tx_base_single_path(tx_data["transactionBase64"])
        else:
            self._sign_and_send_tx(tx_data["transactionBase64"], send_to=send_to)

    async def _get_balance_via_rpc(self, pubkey: str) -> float:
        """Fallback: USDC баланс через Solana JSON-RPC."""
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [pubkey, {"mint": self.mint}, {"encoding": "jsonParsed"}]
        }
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(self.rpc_url, json=payload)
            r.raise_for_status()
            raw = r.json()
            accounts = raw.get("result", {}).get("value", [])
            logger.info(f"RPC token accounts for {pubkey[:8]}...: count={len(accounts)} raw={str(raw)[:300]}")
            if not accounts:
                if self.use_devnet:
                    logger.warning(f"No USDC token account found for {pubkey[:8]}... (mint={self.mint}). Wallet may need devnet USDC airdrop.")
                else:
                    logger.warning(f"No USDC token account found for {pubkey[:8]}... (mint={self.mint}). Wallet has no mainnet USDC associated token account.")
                return 0.0
            ui = accounts[0]["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"]
            logger.info(f"RPC USDC balance: {ui}")
            return float(ui) if ui else 0.0

    def _send_raw_transaction(self, rpc_url: str, signed_b64: str) -> str:
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "sendTransaction",
            "params": [signed_b64, {"encoding": "base64", "skipPreflight": True}]
        }
        with httpx.Client(timeout=30) as http:
            r = http.post(rpc_url, json=payload)
            r.raise_for_status()
            result = r.json()
            if "error" in result:
                raise ValueError(f"Solana RPC error: {result['error'].get('message', result['error'])}")
            return result["result"]

    def _get_signature_status(self, rpc_url: str, signature: str):
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "getSignatureStatuses",
            "params": [[signature], {"searchTransactionHistory": True}]
        }
        with httpx.Client(timeout=20) as http:
            r = http.post(rpc_url, json=payload)
            r.raise_for_status()
            data = r.json()
            values = data.get("result", {}).get("value", [])
            return values[0] if values else None

    def _confirm_signature(self, signature: str, rpc_candidates: list[str], timeout_seconds: int = 60):
        deadline = time.time() + timeout_seconds
        saw_pending = False

        while time.time() < deadline:
            for rpc_url in rpc_candidates:
                try:
                    status = self._get_signature_status(rpc_url, signature)
                    if status is None:
                        continue

                    saw_pending = True
                    if status.get("err"):
                        raise ValueError(f"Transaction failed on-chain: {status['err']}")

                    confirmation = status.get("confirmationStatus")
                    if confirmation in {"confirmed", "finalized"}:
                        logger.info(f"Transaction {signature} reached {confirmation} via {rpc_url}")
                        return
                except ValueError:
                    raise
                except Exception as e:
                    logger.warning(f"getSignatureStatuses via {rpc_url} failed: {e}")

            time.sleep(2)

        network_name = self.cluster
        if saw_pending:
            raise ValueError(f"Transaction {signature} was submitted but not confirmed within {timeout_seconds}s.")
        raise ValueError(f"Transaction {signature} was submitted but not found on {network_name} within {timeout_seconds}s.")

    def _sign_and_send_tx(self, tx_base64: str, send_to: str = "base", validator: str | None = None) -> str:
        """
        Подписывает транзакцию и отправляет в нужный RPC.
        send_to="ephemeral" -> MagicBlock ephemeral validator RPC
        send_to="base"      -> обычный Solana RPC
        """
        from solders.keypair import Keypair
        from solders.transaction import VersionedTransaction

        wallet = self.wallet_mgr.get_wallet_info()
        keypair = Keypair.from_bytes(bytes(wallet["private_key_bytes"]))

        tx_bytes = base64.b64decode(tx_base64)

        # Подписываем транзакцию
        try:
            tx = VersionedTransaction.from_bytes(tx_bytes)
            tx = VersionedTransaction(tx.message, [keypair])
            signed_bytes = bytes(tx)
        except Exception:
            from solders.transaction import Transaction
            tx = Transaction.from_bytes(tx_bytes)
            blockhash = tx.message.recent_blockhash
            tx.sign([keypair], blockhash)
            signed_bytes = bytes(tx)

        signed_b64 = base64.b64encode(signed_bytes).decode()
        submit_candidates, default_confirm_candidates = self._get_rpc_candidates(send_to, validator=validator)

        last_error = None
        last_signature = None
        selected_validator = validator or self.validator
        for rpc_url in submit_candidates:
            try:
                logger.info(f"Sending tx to {rpc_url} (sendTo={send_to}, validator={selected_validator})")
                signature = self._send_raw_transaction(rpc_url, signed_b64)
                last_signature = signature
                logger.info(f"Submitted tx signature: {signature}")
                confirm_candidates = self._get_confirm_candidates_for_submit(send_to, rpc_url, validator=validator) or default_confirm_candidates
                self._confirm_signature(signature, confirm_candidates)
                return signature
            except Exception as e:
                last_error = e
                logger.warning(f"sendTransaction via {rpc_url} failed: {e}")
                err_lower = str(e).lower()
                if "transaction failed on-chain" in err_lower:
                    break
                if ("already been processed" in err_lower or "already processed" in err_lower) and last_signature:
                    try:
                        confirm_candidates = self._get_confirm_candidates_for_submit(send_to, rpc_url, validator=validator) or default_confirm_candidates
                        self._confirm_signature(last_signature, confirm_candidates)
                        return last_signature
                    except Exception as confirm_error:
                        last_error = confirm_error
                    break
                if "submitted but" in err_lower:
                    break

        raise ValueError(f"Unable to submit transaction: {last_error}")

    def _sign_and_send_tx_base_single_path(self, tx_base64: str) -> str:
        from solders.keypair import Keypair
        from solders.transaction import VersionedTransaction

        wallet = self.wallet_mgr.get_wallet_info()
        keypair = Keypair.from_bytes(bytes(wallet["private_key_bytes"]))
        tx_bytes = base64.b64decode(tx_base64)

        try:
            tx = VersionedTransaction.from_bytes(tx_bytes)
            tx = VersionedTransaction(tx.message, [keypair])
            signed_bytes = bytes(tx)
        except Exception:
            from solders.transaction import Transaction
            tx = Transaction.from_bytes(tx_bytes)
            blockhash = tx.message.recent_blockhash
            tx.sign([keypair], blockhash)
            signed_bytes = bytes(tx)

        signed_b64 = base64.b64encode(signed_bytes).decode()
        logger.info(f"Sending tx to {self.rpc_url} (sendTo=base, single-path)")
        signature = self._send_raw_transaction(self.rpc_url, signed_b64)
        logger.info(f"Submitted tx signature: {signature}")
        self._confirm_signature(signature, [self.rpc_url], timeout_seconds=45)
        return signature

    async def get_balance(self) -> dict:
        wallet = self.wallet_mgr.get_wallet_info()
        pubkey = wallet["public_key"]

        solana_usdc  = 0.0
        private_usdc = 0.0
        api_per_ok   = False
        demo_mode    = False
        has_local_per_activity = False
        auth_error = ""

        async with httpx.AsyncClient(timeout=15) as http:
            # 1. Публичный баланс через RPC (самый надёжный для devnet)
            try:
                solana_usdc = await self._get_balance_via_rpc(pubkey)
                logger.info(f"RPC Solana USDC: {solana_usdc}")
            except Exception as e:
                logger.warning(f"RPC balance failed: {e}")
                # Fallback на MagicBlock balance API
                try:
                    params = {"address": pubkey, "mint": self.mint, "cluster": self.cluster}
                    r = await http.get(f"{PAYMENTS_API}/balance", params=params)
                    logger.info(f"Balance API: status={r.status_code} body={r.text[:200]}")
                    if r.is_success:
                        data = r.json()
                        solana_usdc = _from_base_units(
                            data.get("balance", "0"), data.get("decimals", USDC_DECIMALS)
                        )
                    else:
                        demo_mode = True
                except Exception as e2:
                    logger.warning(f"Balance API also failed: {e2}")
                    demo_mode = True

            # 2. Приватный баланс можно читать только с authorization token
            if self.authorization_token:
                try:
                    params_priv = {
                        "owner": pubkey,
                        "address": pubkey,
                        "mint": self.mint,
                        "cluster": self.cluster,
                    }
                    headers_priv = {
                        "Authorization": f"Bearer {self.authorization_token}",
                        "X-Authorization": self.authorization_token,
                    }
                    r = await http.get(
                        f"{PAYMENTS_API}/private-balance",
                        params=params_priv,
                        headers=headers_priv,
                    )
                    logger.info(f"Private-balance: status={r.status_code} body={r.text[:300]}")
                    if r.is_success:
                        data = r.json()
                        private_usdc = _from_base_units(
                            data.get("balance", "0"), data.get("decimals", USDC_DECIMALS)
                        )
                        api_per_ok = True
                    else:
                        logger.warning(f"Private-balance non-2xx: {r.status_code} {r.text[:200]}")
                except Exception as e:
                    auth_error = str(e)
                    logger.warning(f"Private-balance error: {e}")
            elif not self.use_devnet:
                auth_error = "MagicBlock authorization token is unavailable."

        # 3. Если API вернул 0 для PER — считаем локально из истории storage
        #    deposit увеличивает PER, withdraw/send уменьшают
        if not api_per_ok:
            try:
                from storage import SpendingStorage
                user_id = self.wallet_mgr.user_id
                st = SpendingStorage(user_id)
                records = st.get_history(limit=1000, period="all")
                has_local_per_activity = any(
                    r["type"] in ("deposit", "send", "booking", "purchase", "withdraw")
                    for r in records
                )
                local_per = 0.0
                for r in records:
                    if r["type"] == "deposit":
                        local_per += r["amount"]
                    elif r["type"] in ("send", "booking", "purchase", "withdraw"):
                        local_per -= r["amount"]
                private_usdc = max(0.0, round(local_per, 6))
                logger.info(f"Local PER estimate from history: {private_usdc}")
            except Exception as e:
                logger.warning(f"Local PER estimate failed: {e}")

        explorer_base = "https://explorer.solana.com/address"
        cluster_param = f"?cluster={self.cluster}"
        return {
            "solana_usdc":  solana_usdc,
            "private_usdc": private_usdc,
            "total":        solana_usdc + private_usdc,
            "demo_mode":    demo_mode,
            "per_estimated": not api_per_ok,
            "private_balance_source": (
                "api" if api_per_ok else
                "history" if has_local_per_activity else
                "unavailable"
            ),
            "needs_private_auth": (not self.use_devnet) and (not bool(self.authorization_token)),
            "auth_error": auth_error,
            "explorer_url": f"{explorer_base}/{wallet['public_key']}{cluster_param}",
        }

    async def _build_private_transfer(
        self,
        recipient: str,
        amount: float,
        memo: str = "",
        from_balance: str = "base",
        to_balance: str = "ephemeral",
    ) -> dict:
        wallet = self.wallet_mgr.get_wallet_info()
        init_if_missing = to_balance == "ephemeral"
        init_atas_if_missing = from_balance == "base"
        init_vault_if_missing = from_balance == "base" and to_balance == "base"
        payload = {
            "from":        wallet["public_key"],
            "to":          recipient,
            "amount":      _to_base_units(amount),
            "mint":        self.mint,
            "cluster":     self.cluster,
            "visibility":  "private",
            "fromBalance": from_balance,
            "toBalance":   to_balance,
            "initIfMissing": init_if_missing,
            "initAtasIfMissing": init_atas_if_missing,
            "initVaultIfMissing": init_vault_if_missing,
        }
        if self.validator:
            payload["validator"] = self.validator
        if memo:
            payload["memo"] = memo

        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{PAYMENTS_API}/transfer", json=payload)
            logger.info(f"Transfer API: status={r.status_code} body={r.text[:500]}")
            if r.status_code == 402:
                raise ValueError(f"Insufficient {from_balance} balance.")
            if not r.is_success:
                raise ValueError(f"Transfer failed {r.status_code}: {r.text[:300]}")
            return r.json()

    async def private_transfer(
        self,
        recipient: str,
        amount: float,
        memo: str = "",
        from_balance: str = "base",
        to_balance: str = "ephemeral",
    ) -> dict:
        await self._initialize_mint_if_needed()

        tx_data = await self._build_private_transfer(
            recipient=recipient,
            amount=amount,
            memo=memo,
            from_balance=from_balance,
            to_balance=to_balance,
        )
        send_to = tx_data.get("sendTo", "base")
        tx_validator = tx_data.get("validator") or self.validator
        logger.info(
            f"Private transfer prepared for validator={tx_validator} endpoint={self._get_ephemeral_rpc_for_validator(tx_validator)} "
            f"(fromBalance={from_balance}, toBalance={to_balance})"
        )
        sig = self._sign_and_send_tx(
            tx_data["transactionBase64"],
            send_to=send_to,
            validator=tx_validator,
        )

        return {"success": True, "tx_id": sig, "amount": amount}

    async def deposit_to_per(self, amount: float) -> dict:
        await self._initialize_mint_if_needed()
        wallet = self.wallet_mgr.get_wallet_info()
        payload = {
            "owner":              wallet["public_key"],
            "amount":             _to_base_units(amount),
            "mint":               self.mint,
            "cluster":            self.cluster,
            "initIfMissing":      True,
            "initAtasIfMissing":  True,
            "initVaultIfMissing": True,
        }
        if self.validator:
            payload["validator"] = self.validator
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{PAYMENTS_API}/deposit", json=payload)
            r.raise_for_status()
            tx_data = r.json()

        send_to = tx_data.get("sendTo", "base")
        if send_to == "base":
            sig = self._sign_and_send_tx_base_single_path(tx_data["transactionBase64"])
        else:
            tx_validator = tx_data.get("validator") or self.validator
            logger.info(
                f"Deposit prepared for validator={tx_validator} endpoint={self._get_ephemeral_rpc_for_validator(tx_validator)}"
            )
            sig = self._sign_and_send_tx(
                tx_data["transactionBase64"],
                send_to=send_to,
                validator=tx_validator,
            )
        return {"success": True, "tx_id": sig, "amount": amount}

    async def withdraw_from_per(self, amount: float) -> dict:
        await self._initialize_mint_if_needed()
        wallet = self.wallet_mgr.get_wallet_info()
        payload = {
            "owner":      wallet["public_key"],
            "mint":       self.mint,
            "amount":     _to_base_units(amount),
            "cluster":    self.cluster,
            "idempotent": True,
        }
        if self.validator:
            payload["validator"] = self.validator
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{PAYMENTS_API}/withdraw", json=payload)
            r.raise_for_status()
            tx_data = r.json()

        send_to = tx_data.get("sendTo", "base")
        if send_to == "base":
            sig = self._sign_and_send_tx_base_single_path(tx_data["transactionBase64"])
        else:
            tx_validator = tx_data.get("validator") or self.validator
            logger.info(
                f"Withdraw prepared for validator={tx_validator} endpoint={self._get_ephemeral_rpc_for_validator(tx_validator)}"
            )
            sig = self._sign_and_send_tx(
                tx_data["transactionBase64"],
                send_to=send_to,
                validator=tx_validator,
            )
        return {"success": True, "tx_id": sig, "amount": amount}
