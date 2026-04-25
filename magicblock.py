# Измени в методе _demo_balance значения на 0.0
async def _demo_balance(self) -> dict:
    wallet = self.wallet_mgr.get_wallet_info()
    # Было 100.0 и 50.0 -> Стало 0.0
    demo_balance = wallet.get("demo_balance", {"solana": 0.0, "per": 0.0})
    return {
        "solana_usdc": demo_balance.get("solana", 0.0),
        "private_usdc": demo_balance.get("per", 0.0),
        "total": demo_balance.get("solana", 0.0) + demo_balance.get("per", 0.0),
        "demo_mode": True
    }