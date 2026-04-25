"""
WalletManager — Solana wallet creation, storage, and signing.
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
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    return base64.urlsafe_b64encode(kdf.derive(user_id.encode()))

class WalletManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.wallet_file = WALLETS_DIR / f"{user_id}.enc"
        self._wallet_cache: Optional[dict] = None

    def has_wallet(self) -> bool:
        return self.wallet_file.exists()

    def create_wallet(self) -> dict:
        try:
            from solders.keypair import Keypair
            keypair = Keypair()
            private_key_bytes = bytes(keypair)
            public_key = str(keypair.pubkey())
            private_key_b58 = _b58encode(private_key_bytes)
        except ImportError:
            private_key_bytes = secrets.token_bytes(64)
            public_key = "Demo" + secrets.token_hex(16)
            private_key_b58 = _b58encode(private_key_bytes)

        wallet_data = {
            "public_key": public_key,
            "private_key_b58": private_key_b58,
            "private_key_bytes": list(private_key_bytes),
            "mnemonic": " ".join(secrets.choice(["apple", "banana", "cherry"]) for _ in range(12)),
            "per_active": False,
            "demo_balance": {"solana": 0.0, "per": 0.0}, # УСТАНОВЛЕНО 0.0
            "created_at": _now()
        }
        self._save_wallet(wallet_data)
        self._wallet_cache = wallet_data
        return {"public_key": public_key, "mnemonic": wallet_data["mnemonic"], "private_key_b58": private_key_b58}

    def get_wallet_info(self) -> dict:
        if self._wallet_cache: return self._wallet_cache
        data = self._load_wallet()
        self._wallet_cache = data
        return data

    def sign_message(self, message: str) -> str:
        try:
            from solders.keypair import Keypair
            wallet = self.get_wallet_info()
            keypair = Keypair.from_bytes(bytes(wallet["private_key_bytes"]))
            return _b58encode(bytes(keypair.sign_message(message.encode())))
        except:
            return hashlib.sha256(f"{message}:{self.user_id}".encode()).hexdigest()

    def _save_wallet(self, data: dict):
        salt_file = WALLETS_DIR / f"{self.user_id}.salt"
        salt = salt_file.read_bytes() if salt_file.exists() else secrets.token_bytes(16)
        if not salt_file.exists(): salt_file.write_bytes(salt)
        f = Fernet(_derive_fernet_key(self.user_id, salt))
        self.wallet_file.write_bytes(f.encrypt(json.dumps(data).encode()))

    def _load_wallet(self) -> dict:
        salt = (WALLETS_DIR / f"{self.user_id}.salt").read_bytes()
        f = Fernet(_derive_fernet_key(self.user_id, salt))
        return json.loads(f.decrypt(self.wallet_file.read_bytes()).decode())

def _now():
    from datetime import datetime
    return datetime.utcnow().isoformat()