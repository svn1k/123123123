import os
from dataclasses import dataclass

@dataclass
class Config:
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_MODEL: str = os.getenv("GITHUB_MODEL", "gpt-4o")
    USE_DEVNET: bool = os.getenv("USE_DEVNET", "True").lower() == "true"
    DEMO_MERCHANT_ADDRESS: str = os.getenv("DEMO_MERCHANT_ADDRESS", "6v5M8L8...merchant...address")

    def __post_init__(self):
        if not self.TELEGRAM_TOKEN or not self.GITHUB_TOKEN:
            print("⚠️ Настройте TELEGRAM_TOKEN и GITHUB_TOKEN в Variables!")