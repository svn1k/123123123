"""
WalletManager — Solana wallet with Railway Variables persistence.
"""

import os
import json
import base64
import logging
import hashlib
import secrets
import httpx
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# ── Base58 ────────────────────────────────────────────────────────────────────
_B58 = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def _b58encode(data: bytes) -> str:
    lead = len(data) - len(data.lstrip(b"\x00"))
    num = int.from_bytes(data, "big")
    result = []
    while num:
        num, rem = divmod(num, 58)
        result.append(_B58[rem:rem+1].decode())
    return "1" * lead + "".join(reversed(result))

# ── Railway GraphQL API ───────────────────────────────────────────────────────
RAILWAY_API = "https://backboard.railway.com/graphql/v2"

RAILWAY_TOKEN     = os.getenv("RAILWAY_TOKEN", "")
RAILWAY_PROJECT_ID= os.getenv("RAILWAY_PROJECT_ID", "")
RAILWAY_SERVICE_ID= os.getenv("RAILWAY_SERVICE_ID", "")
RAILWAY_ENV_ID    = os.getenv("RAILWAY_ENVIRONMENT_ID", "")

def _railway_configured() -> bool:
    return all([RAILWAY_TOKEN, RAILWAY_PROJECT_ID, RAILWAY_SERVICE_ID, RAILWAY_ENV_ID])

def _railway_get(key: str) -> Optional[str]:
    """Read a single variable from Railway (Synchronous)."""
    query = """
    query($projectId: String!, $serviceId: String!, $environmentId: String!) {
      variables(projectId: $projectId, serviceId: $serviceId, environmentId: $environmentId)
    }
    """
    try:
        with httpx.Client(timeout=15) as http:
            resp = http.post(
                RAILWAY_API,
                headers={"Authorization": f"Bearer {RAILWAY_TOKEN}", "Content-Type": "application/json"},
                json={"query": query, "variables": {
                    "projectId": RAILWAY_PROJECT_ID,
                    "serviceId": RAILWAY_SERVICE_ID,
                    "environmentId": RAILWAY_ENV_ID,
                }}
            )
            resp.raise_for_status()
            data = resp.json()
            variables = data.get("data", {}).get("variables", {})
            return variables.get(key)
    except Exception as e:
        logger.error(f"Railway GET error: {e}")
        return None

def _railway_set(key: str, value: str) -> bool:
    """Upsert a variable in Railway (Synchronous)."""
    mutation = """
    mutation($input: VariableUpsertInput!) {
      variableUpsert(input: $input)
    }
    """
    try:
        with httpx.Client(timeout=15) as http:
            resp = http.post(
                RAILWAY_API,
                headers={"Authorization": f"Bearer {RAILWAY_TOKEN}", "Content-Type": "application/json"},
                json={"query": mutation, "variables": {"input": {
                    "projectId": RAILWAY_PROJECT_ID,
                    "serviceId": RAILWAY_SERVICE_ID,
                    "environmentId": RAILWAY_ENV_ID,
                    "name": key,
                    "value": value,
                }}}
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("data", {}).get("variableUpsert") is not False
    except Exception as e:
        logger.error(f"Railway SET error: {e}")
        return False

# ── Encryption ────────────────────────────────────────────────────────────────
WALLETS_DIR = Path(os.getenv("WALLETS_DIR", "./data/wallets"))
WALLETS_DIR.mkdir(parents=True, exist_ok=True)

def _derive_key(user_id: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    return base64.urlsafe_b64encode(kdf.derive(user_id.encode()))

def _encrypt(data: dict, user_id: str, salt: bytes) -> bytes:
    return Fernet(_derive_key(user_id, salt)).encrypt(json.dumps(data).encode())

def _decrypt(encrypted: bytes, user_id: str, salt: bytes) -> dict:
    return json.loads(Fernet(_derive_key(user_id, salt)).decrypt(encrypted).decode())
class WalletManager:
    """
    Wallet storage with Railway Variables as primary backend.

    Railway var names (per user):
      WALLET_{USER_ID}       — base64-encoded encrypted wallet JSON
      WALLET_SALT_{USER_ID}  — hex-encoded salt
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._var_key  = f"WALLET_{user_id}"
        self._salt_key = f"WALLET_SALT_{user_id}"
        # Local fallback paths
        self._local_file = WALLETS_DIR / f"{user_id}.enc"
        self._salt_file  = WALLETS_DIR / f"{user_id}.salt"
        self._cache: Optional[dict] = None

    def has_wallet(self) -> bool:
        if _railway_configured():
            val = _railway_get(self._var_key)
            if val is not None:
                return True
        return self._local_file.exists()

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

        self._save(wallet_data)
        self._cache = wallet_data
        return {"public_key": public_key, "mnemonic": mnemonic,
                "private_key_b58": _b58encode(private_key_bytes)}

    def get_wallet_info(self) -> dict:
        if self._cache:
            return self._cache
        data = self._load()
        self._cache = data
        return data

    def sign_message(self, message: str) -> str:
        try:
            from solders.keypair import Keypair
            wallet = self.get_wallet_info()
            keypair = Keypair.from_bytes(bytes(wallet["private_key_bytes"]))
            return _b58encode(bytes(keypair.sign_message(message.encode())))
        except ImportError:
            h = hashlib.sha256(f"{message}:{self.user_id}".encode()).hexdigest()
            return _b58encode(bytes.fromhex(h))

    def update_per_status(self, active: bool, per_balance: float = 0):
        wallet = self.get_wallet_info()
        wallet["per_active"] = active
        wallet["demo_balance"]["per"] = per_balance
        self._save(wallet)
        self._cache = wallet

    # ── Storage ───────────────────────────────────────────────────────────────

    def _save(self, data: dict):
        salt = secrets.token_bytes(16)
        encrypted = _encrypt(data, self.user_id, salt)
        encoded = base64.b64encode(encrypted).decode()
        salt_hex = salt.hex()

        saved_to_railway = False
        if _railway_configured():
            ok1 = _railway_set(self._var_key, encoded)
            ok2 = _railway_set(self._salt_key, salt_hex)
            saved_to_railway = ok1 and ok2
            if saved_to_railway:
                logger.info(f"Wallet {self.user_id} saved to Railway Variables ✅")

        self._salt_file.write_text(salt_hex)
        self._local_file.write_bytes(encrypted)

    def _load(self) -> dict:
        if _railway_configured():
            encoded = _railway_get(self._var_key)
            salt_hex = _railway_get(self._salt_key)
            if encoded and salt_hex:
                encrypted = base64.b64decode(encoded)
                salt = bytes.fromhex(salt_hex)
                data = _decrypt(encrypted, self.user_id, salt)
                logger.info(f"Wallet {self.user_id} loaded from Railway ✅")
                return data

        if self._local_file.exists() and self._salt_file.exists():
            salt = bytes.fromhex(self._salt_file.read_text())
            encrypted = self._local_file.read_bytes()
            return _decrypt(encrypted, self.user_id, salt)

        raise ValueError("Wallet not found")


# ── Helpers ───────────────────────────────────────────────────────────────────

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