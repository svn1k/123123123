"""
MagicBlockClient — реальный клиент для Private Payments API.
https://payments.magicblock.app/reference
"""

import base64
import logging
import time
import httpx

logger = logging.getLogger(__name__)

PAYMENTS_API = "https://payments.magicblock.app/v1/spl"

USDC_DEVNET  = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
USDC_MAINNET = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

RPC_DEVNET  = "https://api.devnet.solana.com"
RPC_MAINNET = "https://api.mainnet-beta.solana.com"
ROUTER_DEVNET = "https://devnet-router.magicblock.app"
ROUTER_MAINNET = "https://router.magicblock.app"

# MagicBlock ephemeral validator RPC (для транзакций в rollup)
EPHEMERAL_RPC_DEVNET  = "https://devnet.magicblock.app"
EPHEMERAL_RPC_MAINNET = "https://mainnet.magicblock.app"

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
            self.validator        = config.MAGICBLOCK_VALIDATOR or None
            self.rpc_url          = RPC_DEVNET
            self.router_url       = ROUTER_DEVNET
            self.ephemeral_rpc_url = EPHEMERAL_RPC_DEVNET
        else:
            self.cluster          = "mainnet"
            self.mint             = USDC_MAINNET
            self.validator        = config.MAGICBLOCK_VALIDATOR or None
            self.rpc_url          = RPC_MAINNET
            self.router_url       = ROUTER_MAINNET
            self.ephemeral_rpc_url = EPHEMERAL_RPC_MAINNET

    @property
    def authorization_token(self):
        # Devnet currently works more reliably without private-balance authorization flow.
        # Use MagicBlock authorization only on mainnet.
        if self.use_devnet:
            return ""
        return self.config.MAGICBLOCK_AUTHORIZATION

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
                logger.warning(f"No USDC token account found for {pubkey[:8]}... (mint={self.mint}). Wallet may need devnet USDC airdrop.")
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
                except Exception as e:
                    logger.warning(f"getSignatureStatuses via {rpc_url} failed: {e}")

            time.sleep(2)

        network_name = self.cluster
        if saw_pending:
            raise ValueError(f"Transaction {signature} was submitted but not confirmed within {timeout_seconds}s.")
        raise ValueError(f"Transaction {signature} was submitted but not found on {network_name} within {timeout_seconds}s.")

    def _sign_and_send_tx(self, tx_base64: str, send_to: str = "base") -> str:
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
        if send_to == "ephemeral":
            submit_candidates = [self.router_url]
            confirm_candidates = [self.router_url, self.rpc_url]
        else:
            submit_candidates = [self.rpc_url, self.router_url]
            confirm_candidates = [self.rpc_url, self.router_url]

        last_error = None
        for rpc_url in submit_candidates:
            try:
                logger.info(f"Sending tx to {rpc_url} (sendTo={send_to})")
                signature = self._send_raw_transaction(rpc_url, signed_b64)
                logger.info(f"Submitted tx signature: {signature}")
                self._confirm_signature(signature, confirm_candidates)
                return signature
            except Exception as e:
                last_error = e
                logger.warning(f"sendTransaction via {rpc_url} failed: {e}")

        raise ValueError(f"Unable to submit transaction: {last_error}")

    async def get_balance(self) -> dict:
        wallet = self.wallet_mgr.get_wallet_info()
        pubkey = wallet["public_key"]

        solana_usdc  = 0.0
        private_usdc = 0.0
        api_per_ok   = False
        demo_mode    = False
        has_local_per_activity = False

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
                        "address": pubkey,
                        "mint": self.mint,
                        "cluster": self.cluster,
                        "authorization": self.authorization_token,
                    }
                    r = await http.get(f"{PAYMENTS_API}/private-balance", params=params_priv)
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
                    logger.warning(f"Private-balance error: {e}")

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
            "explorer_url": f"{explorer_base}/{wallet['public_key']}{cluster_param}",
        }

    async def private_transfer(self, recipient: str, amount: float, memo: str = "") -> dict:
        wallet = self.wallet_mgr.get_wallet_info()
        payload = {
            "from":        wallet["public_key"],
            "to":          recipient,
            "amount":      _to_base_units(amount),
            "mint":        self.mint,
            "cluster":     self.cluster,
            "visibility":  "private",
            "fromBalance": "ephemeral",
            "toBalance":   "ephemeral",
        }
        if self.validator:
            payload["validator"] = self.validator
        if memo:
            payload["memo"] = memo

        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{PAYMENTS_API}/transfer", json=payload)
            logger.info(f"Transfer API: status={r.status_code} body={r.text[:500]}")
            if r.status_code == 402:
                raise ValueError("Insufficient private balance.")
            if not r.is_success:
                raise ValueError(f"Transfer failed {r.status_code}: {r.text[:300]}")
            tx_data = r.json()

        send_to = tx_data.get("sendTo", "base")
        sig = self._sign_and_send_tx(tx_data["transactionBase64"], send_to=send_to)
        return {"success": True, "tx_id": sig, "amount": amount}

    async def deposit_to_per(self, amount: float) -> dict:
        wallet = self.wallet_mgr.get_wallet_info()
        payload = {
            "owner":              wallet["public_key"],
            "amount":             _to_base_units(amount),
            "mint":               self.mint,
            "cluster":            self.cluster,
            "initIfMissing":      True,
            "initVaultIfMissing": True,
        }
        if self.validator:
            payload["validator"] = self.validator
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{PAYMENTS_API}/deposit", json=payload)
            r.raise_for_status()
            tx_data = r.json()

        send_to = tx_data.get("sendTo", "base")
        sig = self._sign_and_send_tx(tx_data["transactionBase64"], send_to=send_to)
        return {"success": True, "tx_id": sig, "amount": amount}

    async def withdraw_from_per(self, amount: float) -> dict:
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
        sig = self._sign_and_send_tx(tx_data["transactionBase64"], send_to=send_to)
        return {"success": True, "tx_id": sig, "amount": amount}
