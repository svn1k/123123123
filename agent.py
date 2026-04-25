"""
ConsumerAgent — С памятью диалога и Tool Calling
"""
import json
import logging
import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import Config
from magicblock import MagicBlockClient
from storage import SpendingStorage
from wallet import WalletManager

logger = logging.getLogger(__name__)
config = Config()
GITHUB_MODELS_URL = "https://models.github.io/inference/chat/completions"

# (AGENT_TOOLS остаются такими же, как в предыдущем коде...)
from agent_tools import AGENT_TOOLS # Вынеси инструменты в отдельный файл или оставь тут

SYSTEM_PROMPT = """Ты — Autonomous Consumer Agent. Помогаешь с покупками в Telegram.
1. 🔒 Перед ЛЮБЫМ платежом вызывай request_confirmation.
2. 🧠 Помни контекст беседы (если пользователь уточнил сумму — это к предыдущему запросу).
3. 🛡️ Все платежи приватны через MagicBlock PER.
Отвечай на русском."""

class ConsumerAgent:
    def __init__(self, user_id: str, wallet_mgr: WalletManager, storage: SpendingStorage):
        self.user_id = user_id
        self.wallet_mgr = wallet_mgr
        self.storage = storage
        self.mb_client = MagicBlockClient(wallet_mgr)

    async def process(self, user_message: str, chat_history: list = None) -> dict:
        if chat_history is None: chat_history = []
        if not chat_history:
            chat_history.append({"role": "system", "content": SYSTEM_PROMPT})
        
        chat_history.append({"role": "user", "content": user_message})

        for _ in range(8): # Loop для Tool Calling
            headers = {"Authorization": f"Bearer {config.GITHUB_TOKEN}", "Content-Type": "application/json"}
            payload = {
                "model": config.GITHUB_MODEL,
                "messages": chat_history,
                "tools": AGENT_TOOLS,
                "tool_choice": "auto"
            }
            
            async with httpx.AsyncClient(timeout=60) as http:
                resp = await http.post("https://models.github.ai/inference/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            message = data["choices"][0]["message"]
            chat_history.append(message)

            if not message.get("tool_calls"):
                return {"message": message["content"], "new_history": chat_history}

            for tool_call in message["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                fn_args = json.loads(tool_call["function"]["arguments"])

                if fn_name == "request_confirmation":
                    return {
                        "message": f"⚠️ *Подтверждение*\n\n{fn_args.get('details')}\n💰 Сумма: *{fn_args.get('amount')} USDC*",
                        "keyboard": InlineKeyboardMarkup([[InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_tx:{tool_call['id']}"), InlineKeyboardButton("❌ Отмена", callback_data="cancel_tx")]]),
                        "awaiting_confirmation": True,
                        "pending_tx_data": fn_args,
                        "new_history": chat_history
                    }

                result = await self._execute_tool(fn_name, fn_args)
                chat_history.append({"role": "tool", "tool_call_id": tool_call["id"], "content": json.dumps(result)})

        return {"message": "✅ Готово", "new_history": chat_history}

    async def _execute_tool(self, tool_name, args):
        # (Логика выполнения инструментов как в прошлом коде...)
        if tool_name == "get_balance": return await self.mb_client.get_balance()
        # ... и т.д.
        return {"status": "executed"}