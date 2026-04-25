import os
from dataclasses import dataclass

@dataclass
class Config:
    # Токен Телеграм бота (от @BotFather)
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    
    # GitHub Personal Access Token (для работы нейронки)
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    
    # Модель для GitHub Models (например: gpt-4o, gpt-4o-mini, Llama-3.1-70b-instruct)
    GITHUB_MODEL: str = os.getenv("GITHUB_MODEL", "gpt-4o")
    
    # Настройки сети (True для тестов, False для реальных транзакций)
    USE_DEVNET: bool = os.getenv("USE_DEVNET", "True").lower() == "true"
    
    # Демо-адрес мерчанта для тестов покупок
    DEMO_MERCHANT_ADDRESS: str = os.getenv(
        "DEMO_MERCHANT_ADDRESS", 
        "6v5M8L8...placeholder...address"
    )

    def __post_init__(self):
        if not self.TELEGRAM_TOKEN:
            print("⚠️ WARNING: TELEGRAM_TOKEN не установлен!")
        if not self.GITHUB_TOKEN:
            print("⚠️ WARNING: GITHUB_TOKEN не установлен!")