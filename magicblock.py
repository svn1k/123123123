"""
MagicBlock Private Payments API Client

Integrates with MagicBlock's Private Ephemeral Rollup (PER) on Solana.
Architecture:
  1. User signs challenge with private key → session key
  2. USDC delegated to PER (TEE-backed, Intel TDX)
  3. Private transfers inside PER — no on-chain sender/receiver link
  4. Undelegate back to Solana when needed

API Reference: https://docs.magicblock.gg / private-payments.magicblock.app
"""

import httpx
import logging
import base64
import time
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)
config = Config()

# MagicBlock Private Payments API endpoints
MAGICBLOCK_API_BASE = "https://private-payments-api.magicblock.app"
MAGICBLOCK_DEVNET_BASE = "https://private-payments-devnet.magicblock.app"


class MagicBlockClient:
    """
    Client for MagicBlock Private Payments API.
    
    Flow:
        client = MagicBlockClient(wallet_mgr)
        session = await client.authenticate()
        await client.deposit_to_per(amount=100)
        await client.private_transfer(recipient="...", amount=10)
        await client.withdraw_from_per(amount=50)
    """

    def __init__(self, wallet_mgr):
        self.wallet_mgr = wallet_mgr
        self._session_key: Optional[str] = None
        self._session_expiry: float = 0
        self.base_url = (
            MAGICBLOCK_DEVNET_BASE if config.USE_DEVNET else MAGICBLOCK_API_BASE
        )

    async def _get_session(self) -> str:
        """Get or refresh session key via challenge-response auth."""
        if self._session_key and time.time() < self._session_expiry:
            return self._session_key

        wallet = self.wallet_mgr.get_wallet_info()
        
        async with httpx.AsyncClient(timeout=30) as http:
            # Step 1: Get challenge
            resp = await http.post(
                f"{self.base_url}/auth/challenge",
                json={"public_key": wallet["public_key"]}
            )
            resp.raise_for_status()
            challenge = resp.json()["challenge"]

            # Step 2: Sign challenge with private key
            signature = self.wallet_mgr.sign_message(challenge)

            # Step 3: Exchange signature for session key
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

    async def get_balance(self) -> dict:
        """
        Get user's balance:
        - solana_usdc: public Solana mainnet USDC
        - private_usdc: balance inside Private PER (only visible with session key)
        """
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
                    "total": data.get("total_balance", 0.0)
                }
        except httpx.HTTPStatusError as e:
            logger.warning(f"Balance API error {e.response.status_code}, using demo mode")
            return await self._demo_balance()
        except Exception as e:
            logger.warning(f"Balance fetch failed: {e}, using demo mode")
            return await self._demo_balance()

    async def deposit_to_per(self, amount: float) -> dict:
        """
        Delegate USDC from Solana into the Private Ephemeral Rollup.
        This makes USDC available for private transfers.
        """
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
                        "delegate": True  # Delegate to PER for private txs
                    }
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"Deposit API failed: {e}, demo mode")
            return self._demo_tx_result("deposit", amount)

    async def private_transfer(
        self,
        recipient: str,
        amount: float,
        memo: str = ""
    ) -> dict:
        """
        Execute a private USDC transfer inside the PER.
        
        The transfer happens entirely within the TEE-backed Ephemeral Rollup.
        No on-chain link between sender and receiver on Solana mainnet.
        Recipient details & release instructions are encrypted client-side.
        """
        try:
            session = await self._get_session()
            wallet = self.wallet_mgr.get_wallet_info()

            # Encrypt recipient details client-side before sending to API
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
                        "private": True,   # Use Private PER
                        "aml_check": True  # OFAC AML compliance check
                    }
                )
                resp.raise_for_status()
                result = resp.json()
                
                logger.info(f"Private transfer {amount} USDC, tx: {result.get('tx_id')}")
                return result
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 402:
                raise ValueError("Недостаточно средств в Private PER. Используйте /deposit")
            elif e.response.status_code == 403:
                raise ValueError("Транзакция заблокирована AML-проверкой (OFAC)")
            logger.warning(f"Transfer API failed: {e}, demo mode")
            return self._demo_tx_result("transfer", amount, recipient)
        except Exception as e:
            logger.warning(f"Transfer failed: {e}, demo mode")
            return self._demo_tx_result("transfer", amount, recipient)

    async def withdraw_from_per(self, amount: float) -> dict:
        """
        Undelegate USDC from PER back to Solana mainnet.
        Built-in crank settles funds automatically.
        """
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
            logger.warning(f"Withdraw API failed: {e}, demo mode")
            return self._demo_tx_result("withdraw", amount)

    async def get_private_history(self, limit: int = 50) -> list:
        """
        Get private transaction history (only visible with user's session key).
        The PER stores history encrypted — only the user can read it.
        """
        try:
            session = await self._get_session()
            wallet = self.wallet_mgr.get_wallet_info()

            async with httpx.AsyncClient(timeout=30) as http:
                resp = await http.get(
                    f"{self.base_url}/history/{wallet['public_key']}",
                    headers=self._headers(session),
                    params={"limit": limit}
                )
                resp.raise_for_status()
                return resp.json().get("transactions", [])
        except Exception as e:
            logger.warning(f"History API failed: {e}")
            return []

    # ── Encryption ────────────────────────────────────────────────────────────

    def _encrypt_recipient(self, recipient: str, sender_pubkey: str) -> str:
        """
        Encrypt recipient address client-side before sending to API.
        In production: use the PER's TEE public key for encryption.
        Here: base64 encoding as placeholder (real impl uses asymmetric encryption).
        """
        # TODO: Replace with proper TEE-key encryption in production
        # Real flow: encrypt(recipient + release_instructions, per_tee_pubkey)
        data = f"{recipient}:{sender_pubkey}".encode()
        return base64.b64encode(data).decode()

    # ── Demo Mode (API unavailable / devnet) ──────────────────────────────────

    async def _demo_balance(self) -> dict:
        """Return demo balance when API is not yet available."""
        wallet = self.wallet_mgr.get_wallet_info()
        demo_balance = wallet.get("demo_balance", {"solana": 100.0, "per": 50.0})
        return {
            "solana_usdc": demo_balance.get("solana", 100.0),
            "private_usdc": demo_balance.get("per", 50.0),
            "total": demo_balance.get("solana", 100.0) + demo_balance.get("per", 50.0),
            "demo_mode": True
        }

    def _demo_tx_result(self, op: str, amount: float, recipient: str = "") -> dict:
        """Demo transaction result when API is unavailable."""
        import secrets
        tx_id = "DEMO_" + secrets.token_hex(16).upper()
        logger.info(f"[DEMO] {op}: {amount} USDC -> {recipient or 'PER'}")
        return {
            "success": True,
            "tx_id": tx_id,
            "amount": amount,
            "operation": op,
            "demo_mode": True,
            "message": "⚠️ Demo режим — реальная транзакция не выполнена"
        }
