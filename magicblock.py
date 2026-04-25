"""
MagicBlockClient — реальный клиент для Private Payments API.

Документация: https://payments.magicblock.app/reference
Базовый URL:  https://payments.magicblock.app/v1/spl/

Архитектура:
  API возвращает НЕПОДПИСАННЫЕ транзакции (base64).
  Клиент подписывает их приватным ключом и отправляет в Solana RPC.
  Авторизация через Bearer-токен НЕ нужна для этих эндпоинтов.
"""

import base64
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

PAYMENTS_API = "https://payments.magicblock.app/v1/spl"

# TEE validators
DEVNET_VALIDATOR  = "MTEWGuqxUpYZGFJQcp8tLN7x5v9BSeoFHYWQQ3n3xzo"
MAINNET_VALIDATOR = "MTEWGuqxUpYZGFJQcp8tLN7x5v9BSeoFHYWQQ3n3xzo"

# USDC mints
USDC_DEVNET  = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
USDC_MAINNET = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# Solana RPC
RPC_DEVNET  = "https://api.devnet.solana.com"
RPC_MAINNET = "https://api.mainnet-beta.solana.com"

USDC_DECIMALS = 6


def _to_base_units(amount_usdc: float) -> int:
    """Конвертирует USDC в базовые единицы (6 знаков)."""
    return max(1, int(round(amount_usdc * 10 ** USDC_DECIMALS)))


def _from_base_units(amount_raw, decimals: int = USDC_DECIMALS) -> float:
    """Конвертирует базовые единицы обратно в USDC."""
    try:
        return int(amount_raw) / (10 ** decimals)
    except Exception:
        return 0.0


class MagicBlockClient:
    def __init__(self, wallet_mgr, config):
        self.wallet_mgr = wallet_mgr
        self.config = config

        if config.USE_DEVNET:
            self.cluster   = "devnet"
            self.mint      = USDC_DEVNET
            self.validator = DEVNET_VALIDATOR
            self.rpc_url   = RPC_DEVNET
        else:
            self.cluster   = "mainnet"
            self.mint      = USDC_MAINNET
            self.validator = MAINNET_VALIDATOR
            self.rpc_url   = RPC_MAINNET

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sign_and_send_tx(self, tx_base64: str) -> str:
        """
        Подписывает транзакцию приватным ключом кошелька
        и отправляет в Solana RPC.
        Возвращает TX signature (base58).
        """
        from solders.keypair import Keypair
        from solders.transaction import Transaction
        import httpx as _httpx

        wallet = self.wallet_mgr.get_wallet_info()
        keypair = Keypair.from_bytes(bytes(wallet["private_key_bytes"]))

        tx_bytes = base64.b64decode(tx_base64)
        tx = Transaction.from_bytes(tx_bytes)
        tx.sign([keypair])

        signed_b64 = base64.b64encode(bytes(tx)).decode()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [signed_b64, {"encoding": "base64", "preflightCommitment": "confirmed"}]
        }
        with _httpx.Client(timeout=30) as http:
            r = http.post(self.rpc_url, json=payload)
            r.raise_for_status()
            result = r.json()
            if "error" in result:
                raise ValueError(f"Solana RPC error: {result['error']['message']}")
            return result["result"]

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_balance(self) -> dict:
        """
        Получает публичный и приватный балансы через реальный API.
        GET /v1/spl/balance и GET /v1/spl/private-balance
        """
        wallet = self.wallet_mgr.get_wallet_info()
        pubkey = wallet["public_key"]

        solana_usdc  = 0.0
        private_usdc = 0.0
        demo_mode    = False

        params = {"owner": pubkey, "mint": self.mint, "cluster": self.cluster}

        async with httpx.AsyncClient(timeout=15) as http:
            # 1. Публичный баланс (base chain)
            try:
                r = await http.get(f"{PAYMENTS_API}/balance", params=params)
                r.raise_for_status()
                data = r.json()
                solana_usdc = _from_base_units(data.get("balance", "0"),
                                               data.get("decimals", USDC_DECIMALS))
            except Exception as e:
                logger.warning(f"Balance API error: {e}")
                demo_mode = True

            # 2. Приватный баланс (ephemeral rollup)
            try:
                r = await http.get(f"{PAYMENTS_API}/private-balance", params=params)
                r.raise_for_status()
                data = r.json()
                private_usdc = _from_base_units(data.get("balance", "0"),
                                                data.get("decimals", USDC_DECIMALS))
            except Exception as e:
                logger.warning(f"Private-balance API error: {e}")
                demo_mode = True

        return {
            "solana_usdc":  solana_usdc,
            "private_usdc": private_usdc,
            "total":        solana_usdc + private_usdc,
            "demo_mode":    demo_mode,
        }

    async def private_transfer(self, recipient: str, amount: float, memo: str = "") -> dict:
        """
        POST /v1/spl/transfer с privacy=private.
        Строит транзакцию, подписывает, отправляет в Solana.
        """
        wallet = self.wallet_mgr.get_wallet_info()
        pubkey = wallet["public_key"]

        payload = {
            "owner":       pubkey,
            "destination": recipient,
            "amount":      _to_base_units(amount),
            "mint":        self.mint,
            "cluster":     self.cluster,
            "validator":   self.validator,
            "privacy":     "private",
        }
        if memo:
            payload["memo"] = memo

        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{PAYMENTS_API}/transfer", json=payload)
            if r.status_code == 402:
                raise ValueError("Insufficient private balance.")
            r.raise_for_status()
            tx_data = r.json()

        try:
            sig = self._sign_and_send_tx(tx_data["transactionBase64"])
            return {"success": True, "tx_id": sig, "amount": amount}
        except ImportError:
            logger.warning("solders not available — returning unsigned tx")
            return {
                "success":           False,
                "unsigned_tx":       tx_data["transactionBase64"],
                "required_signers":  tx_data.get("requiredSigners", []),
                "send_to":           tx_data.get("sendTo"),
                "amount":            amount,
            }

    async def deposit_to_per(self, amount: float) -> dict:
        """
        POST /v1/spl/deposit — Solana base → ephemeral rollup.
        """
        wallet = self.wallet_mgr.get_wallet_info()
        pubkey = wallet["public_key"]

        payload = {
            "owner":              pubkey,
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

        try:
            sig = self._sign_and_send_tx(tx_data["transactionBase64"])
            return {"success": True, "tx_id": sig, "amount": amount}
        except ImportError:
            return {"success": False, "unsigned_tx": tx_data["transactionBase64"], "amount": amount}

    async def withdraw_from_per(self, amount: float) -> dict:
        """
        POST /v1/spl/withdraw — ephemeral rollup → Solana base.
        """
        wallet = self.wallet_mgr.get_wallet_info()
        pubkey = wallet["public_key"]

        payload = {
            "owner":      pubkey,
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

        try:
            sig = self._sign_and_send_tx(tx_data["transactionBase64"])
            return {"success": True, "tx_id": sig, "amount": amount}
        except ImportError:
            return {"success": False, "unsigned_tx": tx_data["transactionBase64"], "amount": amount}
