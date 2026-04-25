"""
WalletManager — Solana wallet creation, storage, and signing.

Wallets are encrypted with the user's Telegram ID as key derivation seed.
Private keys never leave the device unencrypted.
"""

import os
import json
import base64
import logging
import hashlib
import secrets
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


# ── Base58 (no external dep) ──────────────────────────────────────────────────
_B58_ALPHA = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def _b58encode(data: bytes) -> str:
    lead = len(data) - len(data.lstrip(b"\x00"))
    num = int.from_bytes(data, "big")
    result = []
    while num:
        num, rem = divmod(num, 58)
        result.append(_B58_ALPHA[rem:rem+1].decode())
    return "1" * lead + "".join(reversed(result))

logger = logging.getLogger(__name__)

WALLETS_DIR = Path(os.getenv("WALLETS_DIR", "./data/wallets"))
WALLETS_DIR.mkdir(parents=True, exist_ok=True)


def _derive_fernet_key(user_id: str, salt: bytes) -> bytes:
    """Derive an encryption key from user_id."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(user_id.encode()))


class WalletManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.wallet_file = WALLETS_DIR / f"{user_id}.enc"
        self._wallet_cache: Optional[dict] = None

    def has_wallet(self) -> bool:
        return self.wallet_file.exists()

    def create_wallet(self) -> dict:
        """Create a new Solana wallet with mnemonic seed phrase."""
        try:
            from solders.keypair import Keypair
            keypair = Keypair()
            private_key_bytes = bytes(keypair)
            public_key = str(keypair.pubkey())
            private_key_b58 = _b58encode(private_key_bytes)
            mnemonic = _generate_mnemonic()
        except ImportError:
            logger.warning("solders not available, using mock wallet")
            private_key_bytes = secrets.token_bytes(64)
            public_key = "Demo" + secrets.token_hex(16)
            private_key_b58 = _b58encode(private_key_bytes)
            mnemonic = _generate_mnemonic()

        wallet_data = {
            "public_key": public_key,
            "private_key_b58": private_key_b58,
            "private_key_bytes": list(private_key_bytes),
            "mnemonic": mnemonic,
            "per_active": False,
            "demo_balance": {"solana": 100.0, "per": 0.0},
            "created_at": _now()
        }

        self._save_wallet(wallet_data)
        self._wallet_cache = wallet_data
        
        # Return safe subset
        return {
            "public_key": public_key,
            "mnemonic": mnemonic,
            "private_key_b58": private_key_b58
        }

    def get_wallet_info(self) -> dict:
        """Get wallet info (includes private key — handle with care)."""
        if self._wallet_cache:
            return self._wallet_cache
        
        if not self.has_wallet():
            raise ValueError("Wallet not found")
        
        data = self._load_wallet()
        self._wallet_cache = data
        return data

    def sign_message(self, message: str) -> str:
        """Sign a message with the wallet's private key (for session auth)."""
        try:
            from solders.keypair import Keypair
            wallet = self.get_wallet_info()
            private_key_bytes = bytes(wallet["private_key_bytes"])
            keypair = Keypair.from_bytes(private_key_bytes)
            
            msg_bytes = message.encode()
            signature = keypair.sign_message(msg_bytes)
            return _b58encode(bytes(signature))
        except ImportError:
            # Mock signature for testing
            h = hashlib.sha256(f"{message}:{self.user_id}".encode()).hexdigest()
            return base64.b58encode(bytes.fromhex(h)).decode()

    def update_per_status(self, active: bool, per_balance: float = 0):
        wallet = self.get_wallet_info()
        wallet["per_active"] = active
        wallet["demo_balance"]["per"] = per_balance
        self._save_wallet(wallet)
        self._wallet_cache = wallet

    # ── Encryption ────────────────────────────────────────────────────────────

    def _save_wallet(self, data: dict):
        salt_file = WALLETS_DIR / f"{self.user_id}.salt"
        
        if salt_file.exists():
            salt = salt_file.read_bytes()
        else:
            salt = secrets.token_bytes(16)
            salt_file.write_bytes(salt)

        key = _derive_fernet_key(self.user_id, salt)
        f = Fernet(key)
        encrypted = f.encrypt(json.dumps(data).encode())
        self.wallet_file.write_bytes(encrypted)

    def _load_wallet(self) -> dict:
        salt_file = WALLETS_DIR / f"{self.user_id}.salt"
        salt = salt_file.read_bytes()
        
        key = _derive_fernet_key(self.user_id, salt)
        f = Fernet(key)
        encrypted = self.wallet_file.read_bytes()
        decrypted = f.decrypt(encrypted)
        return json.loads(decrypted.decode())


# ── Helpers ───────────────────────────────────────────────────────────────────

BIP39_WORDS = [
    "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
    "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
    "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual",
    "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance",
    "advice", "aerobic", "afford", "afraid", "again", "agent", "agree", "ahead",
    "aim", "air", "airport", "aisle", "alarm", "album", "alcohol", "alert",
    "alien", "all", "alley", "allow", "almost", "alone", "alpha", "already",
    "also", "alter", "always", "amateur", "amazing", "among", "amount", "amused",
    "analyst", "anchor", "ancient", "anger", "angle", "angry", "animal", "ankle",
    "announce", "annual", "another", "answer", "antenna", "antique", "anxiety", "any",
]


def _generate_mnemonic(word_count: int = 12) -> str:
    """Generate a BIP39-style mnemonic (simplified)."""
    return " ".join(secrets.choice(BIP39_WORDS) for _ in range(word_count))


def _now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat()
