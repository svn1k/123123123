import httpx, time, logging
from config import Config

config = Config()

class MagicBlockClient:
    def __init__(self, wallet_mgr):
        self.wallet_mgr = wallet_mgr
        self.base_url = "https://private-payments-api.magicblock.app"

    async def get_balance(self):
        try:
            # В реальном API тут был бы запрос, в демо — возвращаем 0
            wallet = self.wallet_mgr.get_wallet_info()
            bal = wallet.get("demo_balance", {"solana": 0.0, "per": 0.0})
            return {"solana_usdc": bal["solana"], "private_usdc": bal["per"], "total": bal["solana"]+bal["per"]}
        except: return {"solana_usdc": 0.0, "private_usdc": 0.0, "total": 0.0}

    async def private_transfer(self, recipient, amount, memo=""):
        # Имитация успешной транзакции
        return {"success": True, "tx_id": "SIM_" + str(int(time.time()))}