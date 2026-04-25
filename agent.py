"""
ConsumerAgent — GitHub Models-powered autonomous agent.

Uses GitHub Models free inference API (OpenAI-compatible endpoint):
  https://models.github.ai/inference
  Model: openai/gpt-4.1  (or meta/llama-3.3-70b, etc.)
  Auth:  GitHub PAT with models:read scope — БЕСПЛАТНО

Tool calling format: OpenAI function calling spec.
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

GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"

# ─── Tool Definitions (OpenAI function-calling format) ────────────────────────

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": "Получить текущий баланс пользователя (Solana + Private PER)",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "private_transfer",
            "description": "Отправить приватный перевод USDC через MagicBlock Private Ephemeral Rollup. Полностью конфиденциально — нет on-chain связи.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Solana адрес получателя (base58)"},
                    "amount": {"type": "number", "description": "Сумма в USDC"},
                    "memo": {"type": "string", "description": "Комментарий к переводу"}
                },
                "required": ["recipient", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_service",
            "description": "Забронировать сервис (отель, ресторан, билет) и оплатить приватно.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_type": {"type": "string", "enum": ["hotel", "restaurant", "flight", "event", "other"]},
                    "description": {"type": "string", "description": "Описание бронирования"},
                    "amount": {"type": "number", "description": "Сумма в USDC"},
                    "merchant_address": {"type": "string", "description": "Solana адрес мерчанта"}
                },
                "required": ["service_type", "description", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buy_product",
            "description": "Купить товар и оплатить приватно через USDC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string", "description": "Название товара"},
                    "amount": {"type": "number", "description": "Сумма в USDC"},
                    "store": {"type": "string", "description": "Магазин или платформа"},
                    "merchant_address": {"type": "string", "description": "Solana адрес мерчанта"}
                },
                "required": ["product_name", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_spending_history",
            "description": "Получить историю трат (хранится только локально, не у рекламодателей).",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string", "enum": ["week", "month", "all"]},
                    "category": {"type": "string", "description": "Категория (booking, purchase, send)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deposit_to_per",
            "description": "Делегировать USDC в Private Ephemeral Rollup для приватных транзакций.",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "number", "description": "Сумма USDC"}},
                "required": ["amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "withdraw_from_per",
            "description": "Вывести USDC из Private PER обратно на Solana mainnet.",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "number", "description": "Сумма USDC"}},
                "required": ["amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_confirmation",
            "description": "Запросить подтверждение от пользователя перед платежом. ОБЯЗАТЕЛЬНО вызывать перед любым переводом.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Краткое описание действия"},
                    "amount": {"type": "number", "description": "Сумма в USDC"},
                    "details": {"type": "string", "description": "Детали для пользователя"}
                },
                "required": ["action", "amount", "details"]
            }
        }
    }
]

SYSTEM_PROMPT = """Ты — Autonomous Consumer Agent, ИИ-ассистент для приватных покупок и платежей в Telegram.

Работаешь на базе:
- GitHub Models (бесплатный inference) — для интеллекта
- MagicBlock Private Payments API — для конфиденциальных USDC-транзакций на Solana
- Private Ephemeral Rollup (TEE/Intel TDX) — для защиты приватности

ПРАВИЛА:
1. 🔒 Перед ЛЮБЫМ платежом — вызывай request_confirmation
2. 💡 Понимай запросы на русском и выполняй их автономно
3. 📊 История трат хранится только у пользователя, не у рекламодателей
4. ⚡ Будь конкретен: показывай суммы, адреса, детали
5. 🛡️ Все переводы через Private PER — конфиденциально

Отвечай на русском языке. Используй эмодзи. Markdown: *жирный*, _курсив_."""


class ConsumerAgent:
    def __init__(self, user_id: str, wallet_mgr: WalletManager, storage: SpendingStorage):
        self.user_id = user_id
        self.wallet_mgr = wallet_mgr
        self.storage = storage
        self.mb_client = MagicBlockClient(wallet_mgr)

    async def _call_api(self, messages: list) -> dict:
        """Call GitHub Models API (OpenAI-compatible, free with GitHub PAT)."""
        headers = {
            "Authorization": f"Bearer {config.GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10"
        }
        payload = {
            "model": config.GITHUB_MODEL,
            "messages": messages,
            "tools": AGENT_TOOLS,
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 2048
        }
        async with httpx.AsyncClient(timeout=60) as http:
            resp = await http.post(GITHUB_MODELS_URL, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def process(self, user_message: str) -> dict:
        """Main agentic loop: understand → plan → execute → respond."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        for _ in range(10):  # max tool call depth
            data = await self._call_api(messages)
            choice = data["choices"][0]
            message = choice["message"]
            messages.append(message)

            finish_reason = choice.get("finish_reason")

            # No tool calls — final text answer
            if finish_reason == "stop" or not message.get("tool_calls"):
                return {
                    "message": message.get("content") or "✅ Задача выполнена.",
                    "keyboard": None
                }

            # Process each tool call
            for tool_call in message["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                try:
                    fn_args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}

                # Confirmation needs user interaction — return early
                if fn_name == "request_confirmation":
                    keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_tx:{tool_call['id']}"),
                        InlineKeyboardButton("❌ Отмена", callback_data="cancel_tx"),
                    ]])
                    return {
                        "message": (
                            f"⚠️ *Подтверждение действия*\n\n"
                            f"🎯 *{fn_args.get('action', '')}*\n\n"
                            f"{fn_args.get('details', '')}\n\n"
                            f"💵 Сумма: *{fn_args.get('amount', 0):.2f} USDC*\n\n"
                            f"_🔒 Оплата приватна через MagicBlock PER_"
                        ),
                        "keyboard": keyboard,
                        "awaiting_confirmation": True
                    }

                # Execute tool and feed result back
                result = await self._execute_tool(fn_name, fn_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False)
                })

        return {"message": "✅ Выполнено.", "keyboard": None}

    async def _execute_tool(self, tool_name: str, args: dict) -> dict:
        logger.info(f"Tool: {tool_name}({args})")
        try:
            if tool_name == "get_balance":
                return await self.mb_client.get_balance()

            elif tool_name == "private_transfer":
                result = await self.mb_client.private_transfer(
                    recipient=args["recipient"],
                    amount=args["amount"],
                    memo=args.get("memo", "")
                )
                self.storage.add_record(
                    type="send",
                    description=args.get("memo", "Перевод"),
                    amount=args["amount"],
                    tx_id=result.get("tx_id", ""),
                    metadata={"recipient": args["recipient"]}
                )
                return {"success": True, "tx_id": result.get("tx_id"), "amount": args["amount"]}

            elif tool_name == "book_service":
                merchant = args.get("merchant_address", config.DEMO_MERCHANT_ADDRESS)
                result = await self.mb_client.private_transfer(
                    recipient=merchant,
                    amount=args["amount"],
                    memo=f"Booking: {args['description']}"
                )
                self.storage.add_record(
                    type="booking",
                    description=args["description"],
                    amount=args["amount"],
                    tx_id=result.get("tx_id", ""),
                    metadata={"service_type": args["service_type"]}
                )
                return {"success": True, "booking_id": result.get("tx_id", "BK-DEMO"), "amount": args["amount"]}

            elif tool_name == "buy_product":
                merchant = args.get("merchant_address", config.DEMO_MERCHANT_ADDRESS)
                result = await self.mb_client.private_transfer(
                    recipient=merchant,
                    amount=args["amount"],
                    memo=f"Purchase: {args['product_name']}"
                )
                self.storage.add_record(
                    type="purchase",
                    description=f"Покупка: {args['product_name']}",
                    amount=args["amount"],
                    tx_id=result.get("tx_id", ""),
                    metadata={"store": args.get("store", "unknown")}
                )
                return {"success": True, "order_id": result.get("tx_id", "ORD-DEMO"), "product": args["product_name"]}

            elif tool_name == "get_spending_history":
                records = self.storage.get_history(
                    period=args.get("period", "month"),
                    category=args.get("category")
                )
                return {"records": records[:20], "stats": self.storage.get_stats()}

            elif tool_name == "deposit_to_per":
                return await self.mb_client.deposit_to_per(args["amount"])

            elif tool_name == "withdraw_from_per":
                return await self.mb_client.withdraw_from_per(args["amount"])

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}", exc_info=True)
            return {"error": str(e), "success": False}
