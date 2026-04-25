import httpx
import logging
import time
import base64
from typing import Optional

logger = logging.getLogger(__name__)

class MagicBlockClient:
    def __init__(self, wallet_mgr, config):
        self.wallet_mgr = wallet_mgr
        self.config = config
        
        # Настройка эндпоинтов в зависимости от сети
        if config.USE_DEVNET:
            self.base_url = "https://private-payments-devnet.magicblock.app"
            self.rpc_url = "https://api.devnet.solana.com"
            self.usdc_mint = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
        else:
            self.base_url = "https://private-payments-api.magicblock.app"
            self.rpc_url = "https://api.mainnet-beta.solana.com"
            self.usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

        self._session_key: Optional[str] = None
        self._session_expiry: float = 0

    async def _get_session(self) -> str:
        """
        Аутентификация в MagicBlock через схему Challenge-Response.
        Использует подпись сообщения приватным ключом пользователя.
        """
        # Если сессия еще жива, используем её
        if self._session_key and time.time() < self._session_expiry:
            return self._session_key

        wallet = self.wallet_mgr.get_wallet_info()
        pubkey = wallet["public_key"]

        async with httpx.AsyncClient(timeout=30) as http:
            try:
                # 1. Получаем уникальный челендж (строку для подписи)
                resp = await http.post(f"{self.base_url}/auth/challenge", json={"public_key": pubkey})
                resp.raise_for_status()
                challenge = resp.json()["challenge"]

                # 2. Подписываем челендж через WalletManager
                signature = self.wallet_mgr.sign_message(challenge)

                # 3. Обмениваем подпись на сессионный JWT токен
                resp = await http.post(
                    f"{self.base_url}/auth/session",
                    json={
                        "public_key": pubkey,
                        "challenge": challenge,
                        "signature": signature
                    }
                )
                resp.raise_for_status()
                data = resp.json()

                self._session_key = data["session_key"]
                # Срок жизни сессии обычно 1 час
                self._session_expiry = time.time() + data.get("expires_in", 3600) - 60
                return self._session_key
                
            except Exception as e:
                logger.error(f"MagicBlock Auth Error: {e}")
                raise ConnectionError("Не удалось авторизоваться в системе MagicBlock.")

    async def get_balance(self) -> dict:
        """
        Возвращает баланс пользователя:
        - solana_usdc: публичные средства в основной сети
        - private_usdc: конфиденциальные средства внутри роллапа (PER)
        """
        wallet = self.wallet_mgr.get_wallet_info()
        pubkey = wallet["public_key"]

        solana_usdc = 0.0
        private_usdc = 0.0

        async with httpx.AsyncClient(timeout=15) as http:
            # 1. Запрос баланса из публичного блокчейна Solana
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenAccountsByOwner",
                    "params": [
                        pubkey,
                        {"mint": self.usdc_mint},
                        {"encoding": "jsonParsed"}
                    ]
                }
                r = await http.post(self.rpc_url, json=payload)
                accounts = r.json().get("result", {}).get("value", [])
                if accounts:
                    info = accounts[0]["account"]["data"]["parsed"]["info"]
                    solana_usdc = float(info["tokenAmount"]["uiAmount"])
            except Exception as e:
                logger.warning(f"Solana RPC Error: {e}")

            # 2. Запрос баланса из приватного роллапа MagicBlock
            try:
                token = await self._get_session()
                headers = {"Authorization": f"Bearer {token}"}
                r = await http.get(f"{self.base_url}/balance/{pubkey}", headers=headers)
                r.raise_for_status()
                private_usdc = r.json().get("balance", 0.0)
            except Exception as e:
                logger.warning(f"MagicBlock Balance Error: {e}")

        return {
            "solana_usdc": solana_usdc,
            "private_usdc": private_usdc,
            "total": solana_usdc + private_usdc
        }

    async def private_transfer(self, recipient: str, amount: float, memo: str = "") -> dict:
        """
        Выполняет приватный перевод внутри роллапа.
        Данные о транзакции скрыты внутри TEE (Intel TDX).
        """
        token = await self._get_session()
        wallet = self.wallet_mgr.get_wallet_info()

        async with httpx.AsyncClient(timeout=60) as http:
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            payload = {
                "sender": wallet["public_key"],
                "recipient": recipient,
                "amount": amount,
                "memo": memo,
                "is_private": True,
                "aml_check": True # Автоматическая проверка на санкции
            }
            
            resp = await http.post(f"{self.base_url}/transfer", headers=headers, json=payload)
            
            if resp.status_code == 402:
                raise ValueError("Недостаточно средств на приватном балансе.")
            
            resp.raise_for_status()
            return resp.json() # Содержит tx_id роллапа

    async def deposit_to_per(self, amount: float) -> dict:
        """
        Внесение средств (USDC) в приватный слой.
        Блокирует USDC в Solana и выпускает их внутри роллапа.
        """
        token = await self._get_session()
        wallet = self.wallet_mgr.get_wallet_info()

        async with httpx.AsyncClient(timeout=60) as http:
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "public_key": wallet["public_key"],
                "amount": amount
            }
            resp = await http.post(f"{self.base_url}/deposit", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def withdraw_from_per(self, amount: float) -> dict:
        """Вывод средств из приватного слоя обратно в публичную сеть Solana"""
        token = await self._get_session()
        wallet = self.wallet_mgr.get_wallet_info()

        async with httpx.AsyncClient(timeout=60) as http:
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "public_key": wallet["public_key"],
                "amount": amount
            }
            resp = await http.post(f"{self.base_url}/withdraw", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()