import json, httpx
from config import Config
from magicblock import MagicBlockClient
from agent_tools import AGENT_TOOLS

config = Config()

SYSTEM_PROMPT = """Ты — ИИ-ассистент Consumer Agent.
Помогаешь пользователю тратить USDC приватно на Solana.
1. Всегда помни историю диалога. Если пользователь пишет просто число — это уточнение к прошлому вопросу.
2. Перед любым списанием денег ОБЯЗАТЕЛЬНО вызывай функцию 'request_confirmation'.
3. Отвечай кратко и на русском."""

class ConsumerAgent:
    def __init__(self, user_id, wallet_mgr, storage):
        self.user_id = user_id
        self.mb = MagicBlockClient(wallet_mgr)
        self.storage = storage

    async def process(self, user_text, history):
        if not history:
            history.append({"role": "system", "content": SYSTEM_PROMPT})
        
        history.append({"role": "user", "content": user_text})

        # Ограничение контекста (последние 10 сообщений + системный)
        if len(history) > 12:
            history = [history[0]] + history[-10:]

        headers = {"Authorization": f"Bearer {config.GITHUB_TOKEN}", "Content-Type": "application/json"}
        
        for _ in range(5): # Допускаем до 5 цепочек вызовов функций
            payload = {
                "model": config.GITHUB_MODEL,
                "messages": history,
                "tools": AGENT_TOOLS,
                "tool_choice": "auto"
            }
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post("https://models.github.ai/inference/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]
            
            history.append(msg)

            if not msg.get("tool_calls"):
                return {"text": msg["content"], "history": history}

            for tool in msg["tool_calls"]:
                name = tool["function"]["name"]
                args = json.loads(tool["function"]["arguments"])

                if name == "request_confirmation":
                    return {
                        "text": f"⚠️ *Подтвердите действие*\n\n{args['details']}\nСумма: *{args['amount']} USDC*",
                        "history": history,
                        "confirm_data": args,
                        "tool_call_id": tool["id"]
                    }
                
                # Выполнение других функций (balance и т.д.)
                res = await self._exec(name, args)
                history.append({"role": "tool", "tool_call_id": tool["id"], "content": json.dumps(res)})

    async def _exec(self, name, args):
        if name == "get_balance": return await self.mb.get_balance()
        return {"result": "ok"}