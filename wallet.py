"""
WalletManager — Multi-user Solana wallet using Upstash Redis (Cloud DB).
"""

import os
import json
import logging
import base64
import secrets
import httpx
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# ── Base58 ────────────────────────────────────────────────────────────────────
_B58 = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _normalize_alias_key(value: str) -> str:
    cleaned = "".join(str(value or "").strip().split()).lower()
    return cleaned[1:] if cleaned.startswith("@") else cleaned

def _b58encode(data: bytes) -> str:
    lead = len(data) - len(data.lstrip(b"\x00"))
    num = int.from_bytes(data, "big")
    result = []
    while num:
        num, rem = divmod(num, 58)
        result.append(_B58[rem:rem+1].decode())
    return "1" * lead + "".join(reversed(result))

# ── Upstash DB Config ─────────────────────────────────────────────────────────
UPSTASH_URL = os.getenv("UPSTASH_URL", "").rstrip("/")
UPSTASH_TOKEN = os.getenv("UPSTASH_TOKEN", "")

def _get_cipher():
    """Создает ключ шифрования на основе токена Telegram"""
    secret = os.getenv("TELEGRAM_TOKEN", "fallback_secret").encode()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"magic_wallet_salt", iterations=100000)
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return Fernet(key)

# ── BIP39 Seed Phrase Generator ───────────────────────────────────────────────
BIP39_WORDS = [
    "abandon","ability","able","about","above","absent","absorb","abstract",
    "absurd","abuse","access","accident","account","accuse","achieve","acid",
    "acoustic","acquire","across","act","action","actor","actress","actual",
    "adapt","add","addict","address","adjust","admit","adult","advance",
    "advice","aerobic","afford","afraid","again","agent","agree","ahead",
    "aim","air","airport","aisle","alarm","album","alcohol","alert",
    "alien","all","alley","allow","almost","alone","alpha","already",
    "also","alter","always","amateur","amazing","among","amount","amused",
    "analyst","anchor","ancient","anger","angle","angry","animal","ankle",
    "announce","annual","another","answer","antenna","antique","anxiety","any",
]

def _generate_mnemonic(n: int = 12) -> str:
    return " ".join(secrets.choice(BIP39_WORDS) for _ in range(n))

# ── Wallet Manager ────────────────────────────────────────────────────────────
class WalletManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.db_key = f"wallet_{user_id}"
        self._cache = None
        self.cipher = _get_cipher()

    def _headers(self):
        return {"Authorization": f"Bearer {UPSTASH_TOKEN}"}

    def _save_encrypted_json(self, key: str, data: dict):
        if not UPSTASH_URL:
            logger.error("UPSTASH_URL is missing!")
            return

        encrypted_data = self.cipher.encrypt(json.dumps(data).encode()).decode('utf-8')

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    f"{UPSTASH_URL}/set/{key}",
                    headers=self._headers(),
                    json=encrypted_data
                )
                resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to save encrypted key {key} to Upstash: {e}")

    def _load_encrypted_json(self, key: str) -> dict | None:
        if not UPSTASH_URL:
            return None

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"{UPSTASH_URL}/get/{key}", headers=self._headers())
                if resp.status_code == 200:
                    result = resp.json().get("result")
                    if result:
                        decrypted_data = self.cipher.decrypt(result.encode()).decode('utf-8')
                        return json.loads(decrypted_data)
        except Exception as e:
            logger.error(f"Failed to load encrypted key {key} from Upstash: {e}")

        return None

    def _save_to_db(self, data: dict):
        self._save_encrypted_json(self.db_key, data)

    def _load_from_db(self) -> dict | None:
        return self._load_encrypted_json(self.db_key)

    def _build_directory_record(self, wallet: dict, username: str = "", first_name: str = "", last_name: str = "") -> dict:
        username_key = _normalize_alias_key(username)
        display_name = " ".join(part for part in [str(first_name or "").strip(), str(last_name or "").strip()] if part).strip()
        owner = wallet.get("owner") or {}
        return {
            "user_id": str(self.user_id),
            "public_key": wallet.get("public_key", ""),
            "username": username_key or owner.get("username", ""),
            "display_name": display_name or owner.get("display_name", ""),
        }

    def sync_directory(self, username: str = "", first_name: str = "", last_name: str = "") -> dict | None:
        if not self.has_wallet():
            return None

        wallet = self.get_wallet_info()
        record = self._build_directory_record(wallet, username=username, first_name=first_name, last_name=last_name)
        wallet["owner"] = {
            "user_id": record["user_id"],
            "username": record["username"],
            "display_name": record["display_name"],
        }
        self._save_to_db(wallet)
        self._cache = wallet

        self._save_encrypted_json(f"wallet_dir_user_{self.user_id}", record)
        if record["public_key"]:
            self._save_encrypted_json(f"wallet_dir_address_{record['public_key']}", record)
        if record["username"]:
            self._save_encrypted_json(f"wallet_dir_alias_{record['username']}", record)
        return record

    def get_wallet_by_user_id(self, user_id: str) -> dict | None:
        key = f"wallet_{str(user_id or '').strip()}"
        if key == self.db_key:
            return self.get_wallet_info()
        return self._load_encrypted_json(key)

    def lookup_wallet_by_user_id(self, user_id: str) -> dict | None:
        wallet = self.get_wallet_by_user_id(user_id)
        if not wallet:
            return None
        owner = wallet.get("owner") or {}
        return {
            "user_id": str(user_id),
            "public_key": wallet.get("public_key", ""),
            "username": owner.get("username", ""),
            "display_name": owner.get("display_name", ""),
        }

    def lookup_wallet_by_address(self, public_key: str) -> dict | None:
        address = str(public_key or "").strip()
        if not address:
            return None
        record = self._load_encrypted_json(f"wallet_dir_address_{address}")
        if not record:
            return None
        user_id = str(record.get("user_id") or "").strip()
        if not user_id:
            return record
        return self.lookup_wallet_by_user_id(user_id) or record

    def lookup_wallet_by_alias(self, alias: str) -> dict | None:
        alias_key = _normalize_alias_key(alias)
        if not alias_key:
            return None
        record = self._load_encrypted_json(f"wallet_dir_alias_{alias_key}")
        if not record:
            return None
        user_id = str(record.get("user_id") or "").strip()
        if not user_id:
            return record
        return self.lookup_wallet_by_user_id(user_id) or record

    def has_wallet(self) -> bool:
        if self._cache:
            return True
        data = self._load_from_db()
        if data:
            self._cache = data
            return True
        return False

    def create_wallet(self) -> dict:
        try:
            from solders.keypair import Keypair
            keypair = Keypair()
            private_key_bytes = bytes(keypair)
            public_key = str(keypair.pubkey())
        except ImportError:
            logger.warning("solders not available, using mock keypair")
            private_key_bytes = secrets.token_bytes(64)
            public_key = "Demo" + secrets.token_hex(16)

        mnemonic = _generate_mnemonic()
        wallet_data = {
            "public_key": public_key,
            "private_key_b58": _b58encode(private_key_bytes),
            "private_key_bytes": list(private_key_bytes),
            "mnemonic": mnemonic,
            "per_active": False,
            "demo_balance": {"solana": 0.0, "per": 0.0},
        }

        self._save_to_db(wallet_data)
        self._cache = wallet_data
        
        return {
            "public_key": public_key, 
            "mnemonic": mnemonic,
            "private_key_b58": _b58encode(private_key_bytes)
        }

    def get_wallet_info(self) -> dict:
        if self._cache:
            return self._cache
        data = self._load_from_db()
        if data:
            self._cache = data
            return data
        raise ValueError("Wallet not found")

    def get_magicblock_auth(self) -> dict:
        wallet = self.get_wallet_info()
        return wallet.get("magicblock_auth", {})

    def set_magicblock_auth(self, token: str, expires_at: int):
        wallet = self.get_wallet_info()
        wallet["magicblock_auth"] = {
            "token": token,
            "expires_at": int(expires_at),
        }
        self._save_to_db(wallet)
        self._cache = wallet

    def sign_message(self, message: str) -> str:
        try:
            from solders.keypair import Keypair
            wallet = self.get_wallet_info()
            keypair = Keypair.from_bytes(bytes(wallet["private_key_bytes"]))
            return _b58encode(bytes(keypair.sign_message(message.encode())))
        except ImportError:
            import hashlib
            h = hashlib.sha256(f"{message}:{self.user_id}".encode()).hexdigest()
            return _b58encode(bytes.fromhex(h))

    def update_per_status(self, active: bool, per_balance: float = 0):
        wallet = self.get_wallet_info()
        wallet["per_active"] = active
        wallet["demo_balance"]["per"] = per_balance
        self._save_to_db(wallet)
        self._cache = wallet
