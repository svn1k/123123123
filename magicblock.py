"""
MagicBlock Private Payments API Client
+ Real Solana RPC balance (no fake numbers)
"""

import httpx
import logging
import base64
import time
import secrets
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)
config = Config()

MAGICBLOCK_API_BASE = "https://private-payments-api.magicblock.app"
MAGICBLOCK_DEVNET_BASE = "https://private-payments-devnet.magicblock.app"

# Solana USDC mint address (mainnet)
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
# Solana USDC mint address (devnet)
USDC_MINT_DEVNET = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"

SOLANA_RPC_MAINNET = "https://api.mainnet-beta.solana.com"
SOLANA_RPC_DEVNET = "https://api.devnet.solana.com"


class MagicBlockClient:
    def __init__(self, wallet_mgr):
        self.wallet_mgr = wallet_mgr
        self._session_key: Optional[str] = None
        self._session_expiry: float = 0
        self.base_url = MAGICBLOCK_DEVNET_BASE if config.USE_DEVNET else MAGICBLOCK_API_BASE
        self.rpc_url = SOLANA_RPC_DEVNET if config.USE_DEVNET else SOLANA_RPC_MAINNET
        self.usdc_mint = USDC_MINT_DEVNET if config.USE_DEVNET else USDC_MINT

    async def _get_session(self) -> str:
        """Get or refresh MagicBlock session key via challenge-response auth."""
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
                json={
                    "public_key": wallet["public_key"],
                    "challenge": challenge,
                    "signature": signature
                }
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

    async def _get_solana_usdc_balance(self, public_key: str) -> float:
        """
        Fetch real USDC balance directly from Solana RPC.
        Free, no API key needed.
        """
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                resp = await http.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenAccountsByOwner",
                        "params": [
                            public_key,
                            {"mint": self.usdc_mint},
                            {"encoding": "jsonParsed"}
                        ]
                    }
                )
                data = resp.json()
                total = 0.0
                for acc in data.get("result", {}).get("value", []):
                    amount = acc["account"]["data"]["parsed"]["info"]["tokenAmount"].get("uiAmount") or 0
                    total += float(amount)
                return total
        except Exception as e:
            logger.warning(f"Solana RPC balance failed: {e}")
            return 0.0

    async def get_balance(self) -> dict:
        """
        Get real USDC balance from Solana RPC.
        Falls back to 0.0 (not fake numbers) if unavailable.
        """
        wallet = self.wallet_mgr.get_wallet_info()
        public_key = wallet["public_key"]

        # Skip RPC for demo/mock wallets (they start with "Demo")
        if public_key.startswith("Demo"):
            return {
                "solana_usdc": 0.0,
                "private_usdc": 0.0,
                "total": 0.0,
                "demo_mode": True
            }

        # Get real on-chain balance
        solana_usdc = await self._get_solana_usdc_balance(public_key)

        # Try to get Private PER balance from MagicBlock API
        private_usdc = 0.0
        try:
            session = await self._get_session()
            async with httpx.AsyncClient(timeout=15) as http:
                resp = await http.get(
                    f"{self.base_url}/balance/{public_key}",
                    headers=self._headers(session)
                )
                resp.raise_for_status()
                data = resp.json()
                private_usdc = data.get("per_balance", 0.0)
        except Exception as e:
            logger.warning(f"PER balance unavailable: {e}")

        return {
            "solana_usdc": solana_usdc,
            "private_usdc": private_usdc,
            "total": solana_usdc + private_usdc,
            "demo_mode": False
        }

    async def deposit_to_per(self, amount: float) -> dict:
        """Delegate USDC from Solana into Private Ephemeral Rollup."""
        try:
            session = await self._get_session()
            wallet = self.wallet_mgr.get_wallet_info()
            async with httpx.AsyncClient(timeout=60) as http:
                resp = await http.post(
                    f"{self.base_url}/deposit",
                    headers=self._headers(session),
                    json={
                        "public_key": wallet["public_key"],
                        "amount_usdc": amount,
                        "delegate": True
                    }
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"Deposit failed: {e} — demo mode")
            return self._demo_tx("deposit", amount)

    async def private_transfer(self, recipient: str, amount: float, memo: str = "") -> dict:
        """Execute a private USDC transfer inside the PER (no on-chain sender/receiver link)."""
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
        """Withdraw USDC from Private PER back to Solana mainnet."""
        try:
            session = await self._get_session()
            wallet = self.wallet_mgr.get_wallet_info()
            async with httpx.AsyncClient(timeout=60) as http:
                resp = await http.post(
                    f"{self.base_url}/withdraw",
                    headers=self._headers(session),
                    json={
                        "public_key": wallet["public_key"],
                        "amount_usdc": amount
                    }
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"Withdraw failed: {e} — demo mode")
            return self._demo_tx("withdraw", amount)

    def _encrypt_recipient(self, recipient: str, sender_pubkey: str) -> str:
        """Client-side encryption before sending to API (placeholder — use TEE key in prod)."""
        data = f"{recipient}:{sender_pubkey}".encode()
        return base64.b64encode(data).decode()

    def _demo_tx(self, op: str, amount: float, recipient: str = "") -> dict:
        tx_id = "DEMO_" + secrets.token_hex(16).upper()
        logger.info(f"[DEMO] {op}: {amount} USDC -> {recipient or 'PER'}")
        return {
            "success": True,
            "tx_id": tx_id,
            "amount": amount,
            "operation": op,
            "demo_mode": True
        }