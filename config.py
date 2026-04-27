import os
from dataclasses import dataclass

@dataclass
class Config:
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_MODEL: str = os.getenv("GITHUB_MODEL", "openai/gpt-4o-mini")
    USE_DEVNET: bool = os.getenv("USE_DEVNET", "true").lower() == "true"
    DEMO_MERCHANT_ADDRESS: str = os.getenv("DEMO_MERCHANT_ADDRESS", "")
    MAGICBLOCK_VALIDATOR: str = os.getenv("MAGICBLOCK_VALIDATOR", "")
    MAGICBLOCK_AUTHORIZATION: str = os.getenv("MAGICBLOCK_AUTHORIZATION", "")

    # Storage paths — always use /app/data/... in Docker (mounted volume)
    # Locally defaults to ./data/...
    WALLETS_DIR: str = os.getenv("WALLETS_DIR", "./data/wallets")
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "./data/history")

    def __post_init__(self):
        if not self.TELEGRAM_TOKEN:
            print("⚠️  WARNING: TELEGRAM_TOKEN is not set")
        if not self.GITHUB_TOKEN:
            print("⚠️  WARNING: GITHUB_TOKEN is not set")
