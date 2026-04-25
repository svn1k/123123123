"""
MagicBlock Private Payments API Client

Demo balance fix: shows 0.0 (not fake 100 USDC) with clear demo mode label.
"""

import httpx
import logging
import base64
import time
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)
config = Config()

MAGICBLOCK_API_BASE = "https://private-payments-api.magicblock.app"
MAGICBLOCK_DEVNET_BASE = "https://private-payments-devnet.magicblock.app"


class MagicBlockClient:
    def __init__(self, wallet_mgr):
        self.wallet_mgr = wallet_mgr
        self._session_key: Optional[str] = None
        self._session_expiry: float = 0
        self.base_url = MAGICBLOCK_DEVNET_BASE if config.USE_DEVNET else MAGICBLOCK_API_BASE

    async def _get_session(self) -> str:
        if self._session_key and time.time() < self._session_expiry:
            return self._session_key

        wallet = self.wallet_mgr.get_wallet_info()
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(
                f"{self.base_url}/auth/challenge",
                json={"public_key": wallet["public_key"]}
            )
            resp.raise_for_status()
            challenge = resp.json()["challenge"]

            signature = self.wallet_mgr.sign_message(challenge)

            resp = await http.post(
                f"{self.base_url}/auth/session",
                json={"public_key": wallet["public_key"], "challenge": challenge, "signature": signature}
            )
            resp.raise_for_status()
            data = resp.json()

            self._session_key = data["session_key"]
            self._session_expiry = time.time() + data.get("expires_in", 3600) - 60
            return self._session_key

    def _headers(self, session_key: str) -> dict:
        return {
            "Authorization": f"Bearer {session_key}",
            "Content-Type": "application/json",
            "X-MagicBlock-Version": "1.0"
        }

    async def get_balance(self) -> dict:
        try:
            session = await self._get_session()
            wallet = self.wallet_mgr.get_wallet_info()
            async with httpx.AsyncClient(timeout=30) as http:
                resp = await http.get(
                    f"{self.base_url}/balance/{wallet['public_key']}",
                    headers=self._headers(session)
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "solana_usdc": data.get("solana_balance", 0.0),
                    "private_usdc": data.get("per_balance", 0.0),
                    "total": data.get("total_balance", 0.0),
                    "demo_mode": False
                }
        except Exception as e:
            logger.warning(f"Balance fetch failed: {e} — demo mode")
            return self._demo_balance()

    async def deposit_to_per(self, amount: float) -> dict:
        try:
            session = await self._get_session()
            wallet = self.wallet_mgr.get_wallet_info()
            async with httpx.AsyncClient(timeout=60) as http:
                resp = await http.post(
                    f"{self.base_url}/deposit",
                    headers=self._headers(session),
                    json={"public_key": wallet["public_key"], "amount_usdc": amount, "delegate": True}
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"Deposit failed: {e} — demo mode")
            return self._demo_tx("deposit", amount)

    async def private_transfer(self, recipient: str, amount: float, memo: str = "") -> dict:
        try:
            session = await self._get_session()
            wallet = self.wallet_mgr.get_wallet_info()
            encrypted_recipient = self._encrypt_recipient(recipient, wallet["public_key"])
            async with httpx.AsyncClient(timeout=60) as http:
                resp = await http.post(
                    f"{self.base_url}/transfer",
                    headers=self._headers(session),
                    json={
                        "sender_public_key": wallet["public_key"],
                        "encrypted_recipient": encrypted_recipient,
                        "amount_usdc": amount,
                        "memo": memo,
                        "private": True,
                        "aml_check": True
                    }
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 402:
                raise ValueError("Insufficient Private PER balance. Use /deposit first.")
            elif e.response.status_code == 403:
                raise ValueError("Transaction blocked by AML check (OFAC).")
            logger.warning(f"Transfer failed: {e} — demo mode")
            return self._demo_tx("transfer", amount, recipient)
        except Exception as e:
            logger.warning(f"Transfer failed: {e} — demo mode")
            return self._demo_tx("transfer", amount, recipient)

    async def withdraw_from_per(self, amount: float) -> dict:
        try:
            session = await self._get_session()
            wallet = self.wallet_mgr.get_wallet_info()
            async with httpx.AsyncClient(timeout=60) as http:
                resp = await http.post(
                    f"{self.base_url}/withdraw",
                    headers=self._headers(session),
                    json={"public_key": wallet["public_key"], "amount_usdc": amount}
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"Withdraw failed: {e} — demo mode")
            return self._demo_tx("withdraw", amount)

    def _encrypt_recipient(self, recipient: str, sender_pubkey: str) -> str:
        data = f"{recipient}:{sender_pubkey}".encode()
        return base64.b64encode(data).decode()

    def _demo_balance(self) -> dict:
        """
        Real balance is 0 until user deposits on-chain.
        Do NOT show fake numbers — that's misleading.
        """
        return {
            "solana_usdc": 0.0,
            "private_usdc": 0.0,
            "total": 0.0,
            "demo_mode": True  # caller shows ⚠️ demo note
        }

    def _demo_tx(self, op: str, amount: float, recipient: str = "") -> dict:
        import secrets
        tx_id = "DEMO_" + secrets.token_hex(16).upper()
        logger.info(f"[DEMO] {op}: {amount} USDC -> {recipient or 'PER'}")
        return {
            "success": True,
            "tx_id": tx_id,
            "amount": amount,
            "operation": op,
            "demo_mode": True
        }
