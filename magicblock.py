"""
MagicBlockClient — реальный клиент для Private Payments API.
https://payments.magicblock.app/reference
"""

import base64
import logging
import httpx

logger = logging.getLogger(__name__)

PAYMENTS_API = "https://payments.magicblock.app/v1/spl"

DEVNET_VALIDATOR  = "MTEWGuqxUpYZGFJQcp8tLN7x5v9BSeoFHYWQQ3n3xzo"
MAINNET_VALIDATOR = "MTEWGuqxUpYZGFJQcp8tLN7x5v9BSeoFHYWQQ3n3xzo"

USDC_DEVNET  = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
USDC_MAINNET = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

RPC_DEVNET  = "https://api.devnet.solana.com"
RPC_MAINNET = "https://api.mainnet-beta.solana.com"

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
    def __init__(self, wallet_mgr, config):
        self.wallet_mgr = wallet_mgr
        self.config = config

        if config.USE_DEVNET:
            self.cluster          = "devnet"
            self.mint             = USDC_DEVNET
            self.validator        = DEVNET_VALIDATOR
            self.rpc_url          = RPC_DEVNET
            self.ephemeral_rpc_url = EPHEMERAL_RPC_DEVNET
        else:
            self.cluster          = "mainnet"
            self.mint             = USDC_MAINNET
            self.validator        = MAINNET_VALIDATOR
            self.rpc_url          = RPC_MAINNET
            self.ephemeral_rpc_url = EPHEMERAL_RPC_MAINNET

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
            accounts = r.json().get("result", {}).get("value", [])
            logger.info(f"RPC token accounts: {accounts}")
            if accounts:
                ui = accounts[0]["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"]
                return float(ui) if ui else 0.0
        return 0.0

    def _sign_and_send_tx(self, tx_base64: str, send_to: str = "base") -> str:
        """
        Подписывает транзакцию и отправляет в нужный RPC.
        send_to="ephemeral" -> MagicBlock ephemeral validator RPC
        send_to="base"      -> обычный Solana RPC
        """
        from solders.keypair import Keypair
        from solders.transaction import VersionedTransaction
        import httpx as _httpx

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

        # Выбираем RPC в зависимости от sendTo
        if send_to == "ephemeral":
            rpc_url = self.ephemeral_rpc_url
        else:
            rpc_url = self.rpc_url

        signed_b64 = base64.b64encode(signed_bytes).decode()
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "sendTransaction",
            "params": [signed_b64, {"encoding": "base64", "skipPreflight": True}]
        }
        logger.info(f"Sending tx to {rpc_url} (sendTo={send_to})")
        with _httpx.Client(timeout=30) as http:
            r = http.post(rpc_url, json=payload)
            r.raise_for_status()
            result = r.json()
            if "error" in result:
                raise ValueError(f"Solana RPC error: {result['error']['message']}")
            return result["result"]

    async def get_balance(self) -> dict:
        wallet = self.wallet_mgr.get_wallet_info()
        pubkey = wallet["public_key"]

        solana_usdc  = 0.0
        private_usdc = 0.0
        demo_mode    = False

        async with httpx.AsyncClient(timeout=15) as http:
            # 1. Публичный баланс — fallback на RPC если payments API недоступен
            try:
                params = {"address": pubkey, "mint": self.mint, "cluster": self.cluster}
                r = await http.get(f"{PAYMENTS_API}/balance", params=params)
                logger.info(f"Balance API: status={r.status_code} body={r.text[:200]}")
                r.raise_for_status()
                data = r.json()
                solana_usdc = _from_base_units(
                    data.get("balance", "0"), data.get("decimals", USDC_DECIMALS)
                )
            except Exception as e:
                logger.warning(f"Balance API unavailable ({e}), falling back to Solana RPC")
                try:
                    solana_usdc = await self._get_balance_via_rpc(pubkey)
                except Exception as e2:
                    logger.warning(f"RPC fallback failed: {e2}")
                    demo_mode = True

            # 2. Приватный баланс — API требует параметр "address", не "owner"
            try:
                params_priv = {"address": pubkey, "mint": self.mint, "cluster": self.cluster}
                r = await http.get(f"{PAYMENTS_API}/private-balance", params=params_priv)
                logger.info(f"Private-balance API: status={r.status_code} body={r.text[:200]}")
                r.raise_for_status()
                data = r.json()
                private_usdc = _from_base_units(
                    data.get("balance", "0"), data.get("decimals", USDC_DECIMALS)
                )
            except Exception as e:
                logger.warning(f"Private-balance API error: {e}")

        return {
            "solana_usdc":  solana_usdc,
            "private_usdc": private_usdc,
            "total":        solana_usdc + private_usdc,
            "demo_mode":    demo_mode,
        }

    async def private_transfer(self, recipient: str, amount: float, memo: str = "") -> dict:
        wallet = self.wallet_mgr.get_wallet_info()
        payload = {
            "from":        wallet["public_key"],
            "to":          recipient,
            "amount":      _to_base_units(amount),
            "mint":        self.mint,
            "cluster":     self.cluster,
            "validator":   self.validator,
            "visibility":  "private",    # скрыть детали транзакции
            "fromBalance": "ephemeral",  # списать с PER (ephemeral rollup)
            "toBalance":   "ephemeral",  # зачислить получателю в PER
        }
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
            "from":               wallet["public_key"],
            "amount":             _to_base_units(amount),
            "mint":               self.mint,
            "cluster":            self.cluster,
            "validator":          self.validator,
            "initIfMissing":      True,
            "initVaultIfMissing": True,
        }
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
            "validator":  self.validator,
            "idempotent": True,
        }
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{PAYMENTS_API}/withdraw", json=payload)
            r.raise_for_status()
            tx_data = r.json()

        send_to = tx_data.get("sendTo", "base")
        sig = self._sign_and_send_tx(tx_data["transactionBase64"], send_to=send_to)
        return {"success": True, "tx_id": sig, "amount": amount}
