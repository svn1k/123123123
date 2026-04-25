import os, json, base64, secrets, hashlib, logging
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

_B58 = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58e(d):
    l = len(d) - len(d.lstrip(b"\x00"))
    n = int.from_bytes(d, "big")
    res = []
    while n: n, r = divmod(n, 58); res.append(_B58[r:r+1].decode())
    return "1" * l + "".join(reversed(res))

WALLETS_DIR = Path("./data/wallets")
WALLETS_DIR.mkdir(parents=True, exist_ok=True)

class WalletManager:
    def __init__(self, user_id):
        self.user_id = str(user_id)
        self.file = WALLETS_DIR / f"{self.user_id}.enc"
        self.salt_file = WALLETS_DIR / f"{self.user_id}.salt"

    def has_wallet(self): return self.file.exists()

    def create_wallet(self):
        try:
            from solders.keypair import Keypair
            kp = Keypair()
            pk_bytes, pub = bytes(kp), str(kp.pubkey())
        except:
            pk_bytes, pub = secrets.token_bytes(64), "Demo" + secrets.token_hex(16)
        
        data = {
            "public_key": pub,
            "private_key_bytes": list(pk_bytes),
            "private_key_b58": b58e(pk_bytes),
            "mnemonic": " ".join(secrets.choice(["leaf", "ocean", "stone"]) for _ in range(12)),
            "demo_balance": {"solana": 0.0, "per": 0.0} # Было 100, стало 0
        }
        self._save(data)
        return data

    def get_wallet_info(self):
        salt = self.salt_file.read_bytes()
        kdf = PBKDF2HMAC(hashes.SHA256(), 32, salt, 480000)
        key = base64.urlsafe_b64encode(kdf.derive(self.user_id.encode()))
        return json.loads(Fernet(key).decrypt(self.file.read_bytes()).decode())

    def sign_message(self, msg):
        try:
            from solders.keypair import Keypair
            kp = Keypair.from_bytes(bytes(self.get_wallet_info()["private_key_bytes"]))
            return b58e(bytes(kp.sign_message(msg.encode())))
        except: return hashlib.sha256(msg.encode()).hexdigest()

    def _save(self, data):
        salt = secrets.token_bytes(16)
        self.salt_file.write_bytes(salt)
        kdf = PBKDF2HMAC(hashes.SHA256(), 32, salt, 480000)
        key = base64.urlsafe_b64encode(kdf.derive(self.user_id.encode()))
        self.file.write_bytes(Fernet(key).encrypt(json.dumps(data).encode()))