"""
ConsumerAgent — GitHub Models-powered autonomous agent.

Key fixes:
- Conversation history persists across messages (cleared only on payment)
- All text in English
- Demo balance shows 0 (not fake 100 USDC)
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

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": "Get user's current balance: Solana mainnet USDC and Private PER balance.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "private_transfer",
            "description": "Send a private USDC transfer via MagicBlock Private Ephemeral Rollup. No on-chain link between sender and receiver.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Recipient Solana address (base58)"},
                    "amount": {"type": "number", "description": "Amount in USDC"},
                    "memo": {"type": "string", "description": "Optional memo for the transfer"}
                },
                "required": ["recipient", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_service",
            "description": "Book a service (hotel, restaurant, flight, event) and pay privately with USDC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_type": {"type": "string", "enum": ["hotel", "restaurant", "flight", "event", "other"]},
                    "description": {"type": "string", "description": "Booking description"},
                    "amount": {"type": "number", "description": "Amount in USDC"},
                    "merchant_address": {"type": "string", "description": "Merchant Solana address (optional)"}
                },
                "required": ["service_type", "description", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buy_product",
            "description": "Buy a product and pay privately with USDC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string", "description": "Product name"},
                    "amount": {"type": "number", "description": "Amount in USDC"},
                    "store": {"type": "string", "description": "Store or platform"},
                    "merchant_address": {"type": "string", "description": "Merchant Solana address (optional)"}
                },
                "required": ["product_name", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_spending_history",
            "description": "Get user spending history. Stored locally only — never shared with advertisers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string", "enum": ["week", "month", "all"]},
                    "category": {"type": "string", "description": "Filter: booking, purchase, send"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deposit_to_per",
            "description": "Delegate USDC into the Private Ephemeral Rollup to enable private transactions.",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "number", "description": "Amount in USDC"}},
                "required": ["amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "withdraw_from_per",
            "description": "Withdraw USDC from Private PER back to Solana mainnet.",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "number", "description": "Amount in USDC"}},
                "required": ["amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_confirmation",
            "description": "Ask the user to confirm a payment before executing. MUST call this before any transfer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Short description of the action"},
                    "amount": {"type": "number", "description": "Amount in USDC"},
                    "details": {"type": "string", "description": "Full details to show the user"}
                },
                "required": ["action", "amount", "details"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are an Autonomous Consumer Agent — an AI assistant for private purchases, bookings, and payments in Telegram.

Powered by:
- GitHub Models (free inference) — intelligence
- MagicBlock Private Payments API — confidential USDC transactions on Solana
- Private Ephemeral Rollup (TEE / Intel TDX) — privacy layer

RULES:
1. 🔒 ALWAYS call request_confirmation before any payment — no exceptions
2. 💬 Remember conversation context — if the user previously asked to book a hotel and then sends just "150", that is the budget for that booking
3. 📊 Spending history is stored locally only, never shared with advertisers
4. ⚡ Be specific: show amounts, addresses, and details clearly
5. 🛡️ All transfers go through Private PER — fully confidential

Respond in English. Use emojis. Markdown: *bold*, _italic_."""


class ConsumerAgent:
    def __init__(self, user_id: str, wallet_mgr: WalletManager, storage: SpendingStorage):
        self.user_id = user_id
        self.wallet_mgr = wallet_mgr
        self.storage = storage
        self.mb_client = MagicBlockClient(wallet_mgr)

    async def _call_api(self, messages: list) -> dict:
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

    async def process(self, user_message: str, history: list) -> dict:
        """
        Main agentic loop.

        history: list of previous {"role": ..., "content": ...} messages.
                 Persisted between calls, cleared only after confirmed payment.

        Returns dict with keys:
          message, keyboard, history (updated), awaiting_confirmation, clear_history_on_confirm
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Track new messages added this turn to append to history
        new_messages = [{"role": "user", "content": user_message}]

        for _ in range(10):
            data = await self._call_api(messages)
            choice = data["choices"][0]
            message = choice["message"]

            messages.append(message)
            new_messages.append(message)

            finish_reason = choice.get("finish_reason")

            if finish_reason == "stop" or not message.get("tool_calls"):
                return {
                    "message": message.get("content") or "✅ Done.",
                    "keyboard": None,
                    "history": history + new_messages,
                    "awaiting_confirmation": False
                }

            for tool_call in message["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                try:
                    fn_args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}

                if fn_name == "request_confirmation":
                    keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_tx:{tool_call['id']}"),
                        InlineKeyboardButton("❌ Cancel", callback_data="cancel_tx"),
                    ]])
                    return {
                        "message": (
                            f"⚠️ *Confirm Payment*\n\n"
                            f"🎯 *{fn_args.get('action', '')}*\n\n"
                            f"{fn_args.get('details', '')}\n\n"
                            f"💵 Amount: *{fn_args.get('amount', 0):.2f} USDC*\n\n"
                            f"_🔒 Payment is private via MagicBlock PER_"
                        ),
                        "keyboard": keyboard,
                        "history": history + new_messages,
                        "awaiting_confirmation": True,
                        "clear_history_on_confirm": True  # caller clears after payment
                    }

                result = await self._execute_tool(fn_name, fn_args)
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False)
                }
                messages.append(tool_msg)
                new_messages.append(tool_msg)

        return {"message": "✅ Done.", "keyboard": None, "history": history + new_messages}

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
                    description=args.get("memo", "Transfer"),
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
                    description=f"Purchase: {args['product_name']}",
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
