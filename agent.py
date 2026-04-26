"""
ConsumerAgent — GitHub Models-powered autonomous agent.
"""

import asyncio
import json
import logging

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown

from config import Config
from magicblock import MagicBlockClient
from storage import SpendingStorage, UserProfileStorage
from wallet import WalletManager

logger = logging.getLogger(__name__)
config = Config()

GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
SPEND_RECORD_TYPES = ["send", "booking", "purchase"]


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": "Get user's current balance: public Solana USDC and private PER balance.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "private_transfer",
            "description": "Send a private USDC transfer via MagicBlock PER. The recipient can be a Solana address or a saved contact alias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Recipient Solana address or saved contact alias"},
                    "amount": {"type": "number", "description": "Amount in USDC"},
                    "memo": {"type": "string", "description": "Optional memo for the transfer"},
                },
                "required": ["recipient", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_service",
            "description": "Book a service and pay privately with USDC. merchant_address may be a real address or a saved merchant alias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_type": {"type": "string", "enum": ["hotel", "restaurant", "flight", "event", "other"]},
                    "description": {"type": "string", "description": "Booking description"},
                    "amount": {"type": "number", "description": "Amount in USDC"},
                    "merchant_address": {"type": "string", "description": "Merchant Solana address or saved merchant alias"},
                },
                "required": ["service_type", "description", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buy_product",
            "description": "Buy a product and pay privately with USDC. merchant_address may be a real address or a saved merchant alias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string", "description": "Product name"},
                    "amount": {"type": "number", "description": "Amount in USDC"},
                    "store": {"type": "string", "description": "Store or platform"},
                    "merchant_address": {"type": "string", "description": "Merchant Solana address or saved merchant alias"},
                },
                "required": ["product_name", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spending_history",
            "description": "Get user spending history. Stored locally only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string", "enum": ["week", "month", "all"]},
                    "category": {"type": "string", "description": "Filter: booking, purchase, send"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deposit_to_per",
            "description": "Move USDC from the user's public Solana wallet into the private PER balance.",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "number", "description": "Amount in USDC"}},
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "withdraw_from_per",
            "description": "Move USDC from the user's private PER balance back to the public Solana wallet.",
            "parameters": {
                "type": "object",
                "properties": {"amount": {"type": "number", "description": "Amount in USDC"}},
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_contact",
            "description": "Save or update a contact alias for a Solana address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "alias": {"type": "string"},
                    "address": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["alias", "address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_contacts",
            "description": "List saved contacts and aliases.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_contact",
            "description": "Remove a saved contact alias.",
            "parameters": {
                "type": "object",
                "properties": {"alias": {"type": "string"}},
                "required": ["alias"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_merchant_profile",
            "description": "Save or update a merchant profile with alias, address, category, note, and optional default amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "alias": {"type": "string"},
                    "address": {"type": "string"},
                    "category": {"type": "string"},
                    "note": {"type": "string"},
                    "default_amount": {"type": "number"},
                },
                "required": ["alias", "address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_merchant_profiles",
            "description": "List saved merchant profiles.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_merchant_profile",
            "description": "Remove a merchant profile by alias.",
            "parameters": {
                "type": "object",
                "properties": {"alias": {"type": "string"}},
                "required": ["alias"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_payment_request",
            "description": "Create a shareable payment request/invoice code. recipient_address or recipient_alias is optional; if omitted, use the user's own wallet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "description": {"type": "string"},
                    "recipient_address": {"type": "string"},
                    "recipient_alias": {"type": "string"},
                    "due_date": {"type": "string", "description": "Optional due date text"},
                    "note": {"type": "string"},
                },
                "required": ["amount", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_payment_requests",
            "description": "List local payment requests/invoices.",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string", "enum": ["open", "paid", "cancelled"]}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_payment_request",
            "description": "Cancel an invoice/payment request by invoice_id.",
            "parameters": {
                "type": "object",
                "properties": {"invoice_id": {"type": "string"}},
                "required": ["invoice_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pay_payment_request",
            "description": "Pay a shareable PERPAY payment request code privately with USDC.",
            "parameters": {
                "type": "object",
                "properties": {"share_code": {"type": "string"}},
                "required": ["share_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_recurring_payment",
            "description": "Create a recurring private payment to a contact alias, merchant alias, or Solana address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Alias or Solana address"},
                    "amount": {"type": "number"},
                    "interval": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
                    "memo": {"type": "string"},
                    "category": {"type": "string"},
                    "start_at": {"type": "string", "description": "Optional ISO datetime"},
                },
                "required": ["target", "amount", "interval"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_recurring_payments",
            "description": "List recurring payment schedules.",
            "parameters": {
                "type": "object",
                "properties": {"active_only": {"type": "boolean"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pause_recurring_payment",
            "description": "Pause a recurring payment by recurring_id.",
            "parameters": {
                "type": "object",
                "properties": {"recurring_id": {"type": "string"}},
                "required": ["recurring_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume_recurring_payment",
            "description": "Resume a recurring payment by recurring_id.",
            "parameters": {
                "type": "object",
                "properties": {"recurring_id": {"type": "string"}},
                "required": ["recurring_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_recurring_payment",
            "description": "Delete a recurring payment schedule by recurring_id.",
            "parameters": {
                "type": "object",
                "properties": {"recurring_id": {"type": "string"}},
                "required": ["recurring_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_due_recurring_payments",
            "description": "Run due recurring payments now. Use request_confirmation before calling this tool.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "number", "description": "Optional max number of due recurring payments to process"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_budget",
            "description": "Set or update a budget. category can be all, transfer, booking, purchase, or a custom merchant category like food or travel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "period": {"type": "string", "enum": ["week", "month"]},
                    "amount": {"type": "number"},
                    "strict": {"type": "boolean"},
                },
                "required": ["category", "period", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_budgets",
            "description": "List configured budgets.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_budget",
            "description": "Remove a budget by budget_id.",
            "parameters": {
                "type": "object",
                "properties": {"budget_id": {"type": "string"}},
                "required": ["budget_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget_status",
            "description": "Get current budget usage and remaining amounts.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_risk_rules",
            "description": "Configure risk rules. Provide numeric values in USDC. Omit a field to keep it unchanged. Set a field to 0 to clear it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_single_payment": {"type": "number"},
                    "daily_spend_limit": {"type": "number"},
                    "monthly_spend_limit": {"type": "number"},
                    "require_known_contact_over": {"type": "number"},
                    "block_new_recipient_over": {"type": "number"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_rules",
            "description": "Show the active risk rules.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_confirmation",
            "description": "Ask the user to confirm a payment before executing. MUST call this before any payment tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Short description of the action"},
                    "amount": {"type": "number", "description": "Amount in USDC"},
                    "details": {"type": "string", "description": "Full details to show the user"},
                },
                "required": ["action", "amount", "details"],
            },
        },
    },
]


SYSTEM_PROMPT = """You are an Autonomous Consumer Agent for private payments in Telegram.

Capabilities:
- Private MagicBlock PER payments on Solana
- Saved contacts and merchant aliases
- Payment requests / invoices
- Recurring payments
- Budgets and risk rules

Rules:
1. ALWAYS call request_confirmation before any payment tool: private_transfer, book_service, buy_product, pay_payment_request, run_due_recurring_payments.
2. Contacts and merchants may be referenced by alias instead of raw address.
3. If the user wants a request or invoice, use create_payment_request.
4. If the user wants scheduled repeat payments, use create_recurring_payment and related recurring tools.
5. If the user asks about spending controls, use budgets and risk tools.
6. Do not ask the user to deposit to PER manually for normal payments. The system auto-deposits if needed.
7. Mention tx_id after successful payments.
8. Use the exact requested amount.

Respond in English. Use emojis. Markdown: *bold*, _italic_."""


class ConsumerAgent:
    def __init__(self, user_id: str, wallet_mgr: WalletManager, storage: SpendingStorage, use_devnet: bool | None = None):
        self.user_id = user_id
        self.wallet_mgr = wallet_mgr
        self.storage = storage
        self.profile = UserProfileStorage(user_id)
        self.mb_client = MagicBlockClient(wallet_mgr, config, use_devnet=use_devnet)
        self.network_label = "Solana Devnet" if self.mb_client.use_devnet else "Solana Mainnet"

    def _normalize_solana_address(self, value: str, field_name: str = "recipient") -> str:
        address = "".join(str(value or "").split())
        if not address:
            raise ValueError(f"Missing {field_name} address.")

        try:
            from solders.pubkey import Pubkey

            Pubkey.from_string(address)
        except Exception:
            allowed = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
            if not (32 <= len(address) <= 44) or any(ch not in allowed for ch in address):
                raise ValueError(
                    f"Invalid {field_name} Solana address or alias: {address}. "
                    "Please send a valid base58 wallet address or a saved alias."
                )

        return address

    def _make_target(
        self,
        address: str,
        alias: str = "",
        kind: str = "address",
        category: str = "",
        note: str = "",
        wallet_match: dict | None = None,
    ) -> dict:
        if wallet_match:
            return {
                "address": self._normalize_solana_address(wallet_match.get("public_key", address), "recipient"),
                "alias": alias or (f"@{wallet_match.get('username')}" if wallet_match.get("username") else ""),
                "kind": kind,
                "category": category,
                "note": note,
                "wallet_user_id": str(wallet_match.get("user_id", "") or ""),
                "wallet_username": str(wallet_match.get("username", "") or ""),
                "wallet_display_name": str(wallet_match.get("display_name", "") or ""),
                "is_internal_wallet": True,
                "delivery_preference": "ephemeral",
            }

        return {
            "address": self._normalize_solana_address(address, "recipient"),
            "alias": alias,
            "kind": kind,
            "category": category,
            "note": note,
            "wallet_user_id": "",
            "wallet_username": "",
            "wallet_display_name": "",
            "is_internal_wallet": False,
            "delivery_preference": "ephemeral",
        }

    def _resolve_saved_target(self, value: str, field_name: str = "recipient") -> dict:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError(f"Missing {field_name}.")
        alias_input = raw.startswith("@")
        if alias_input:
            raw = raw[1:]

        saved = self.profile.resolve_alias(raw)
        if saved:
            wallet_match = None
            if saved.get("wallet_user_id"):
                wallet_match = self.wallet_mgr.lookup_wallet_by_user_id(saved.get("wallet_user_id", ""))
            if not wallet_match:
                wallet_match = self.wallet_mgr.lookup_wallet_by_address(saved.get("address", ""))
            return self._make_target(
                address=saved["address"],
                alias=saved.get("alias", ""),
                kind=saved.get("kind", "address"),
                category=saved.get("category", ""),
                note=saved.get("note", ""),
                wallet_match=wallet_match,
            )

        wallet_match = self.wallet_mgr.lookup_wallet_by_alias(raw)
        if wallet_match:
            return self._make_target(
                address=wallet_match.get("public_key", ""),
                alias=f"@{wallet_match.get('username')}" if wallet_match.get("username") else raw,
                kind="bot_wallet",
                wallet_match=wallet_match,
            )

        if alias_input:
            raise ValueError(
                f"Alias @{raw} is not saved yet, and no bot wallet with that username was found. "
                f"Save it first with a valid Solana address or a known bot username."
            )

        address = self._normalize_solana_address(raw, field_name)
        wallet_match = self.wallet_mgr.lookup_wallet_by_address(address)
        return self._make_target(
            address=address,
            alias="",
            kind="address",
            category="",
            note="",
            wallet_match=wallet_match,
        )

    def _recipient_seen_before(self, address: str) -> bool:
        history = self.storage.get_history(limit=100000, period="all")
        for record in history:
            recipient = str((record.get("metadata") or {}).get("recipient", "")).strip()
            if recipient and recipient == address:
                return True
        return False

    def _spend_for_budget(self, budget: dict) -> float:
        category = str(budget.get("category") or "all").lower()
        period = str(budget.get("period") or "month").lower()
        if category == "all":
            return self.storage.get_spent_amount(period=period, record_types=SPEND_RECORD_TYPES)
        if category in {"transfer", "send"}:
            return self.storage.get_spent_amount(period=period, record_types=["send"])
        if category == "booking":
            return self.storage.get_spent_amount(period=period, record_types=["booking"])
        if category == "purchase":
            return self.storage.get_spent_amount(period=period, record_types=["purchase"])
        return self.storage.get_spent_amount(
            period=period,
            record_types=SPEND_RECORD_TYPES,
            budget_category=category,
        )

    def _get_budget_status_entries(self) -> list[dict]:
        entries = []
        for budget in self.profile.get_budgets():
            spent = self._spend_for_budget(budget)
            amount = float(budget.get("amount", 0.0) or 0.0)
            remaining = round(amount - spent, 6)
            usage_ratio = round((spent / amount) * 100, 2) if amount > 0 else 0.0
            entries.append(
                {
                    **budget,
                    "spent": spent,
                    "remaining": remaining,
                    "usage_ratio": usage_ratio,
                    "status": "exceeded" if remaining < 0 else "ok",
                }
            )
        return entries

    def _evaluate_payment_guardrails(
        self,
        amount: float,
        recipient_info: dict,
        spend_type: str,
        budget_category: str,
        context_label: str,
    ) -> dict:
        blockers = []
        warnings = []
        rules = self.profile.get_risk_rules()
        amount = float(amount)
        known_recipient = recipient_info.get("kind") in {"contact", "merchant"} or self._recipient_seen_before(recipient_info["address"])

        max_single = rules.get("max_single_payment")
        if max_single and amount > float(max_single):
            blockers.append(
                f"{context_label} exceeds max single payment rule ({amount:.2f} > {float(max_single):.2f} USDC)."
            )

        daily_limit = rules.get("daily_spend_limit")
        if daily_limit:
            today_spent = self.storage.get_spent_amount(period="day", record_types=SPEND_RECORD_TYPES)
            if today_spent + amount > float(daily_limit):
                blockers.append(
                    f"{context_label} would exceed the daily spend limit ({today_spent + amount:.2f} > {float(daily_limit):.2f} USDC)."
                )

        monthly_limit = rules.get("monthly_spend_limit")
        if monthly_limit:
            month_spent = self.storage.get_spent_amount(period="month", record_types=SPEND_RECORD_TYPES)
            if month_spent + amount > float(monthly_limit):
                blockers.append(
                    f"{context_label} would exceed the monthly spend limit ({month_spent + amount:.2f} > {float(monthly_limit):.2f} USDC)."
                )

        require_known = rules.get("require_known_contact_over")
        if require_known and amount > float(require_known) and not known_recipient:
            blockers.append(
                f"{context_label} is above the known-contact threshold, but the recipient is not a saved contact or merchant."
            )

        block_new = rules.get("block_new_recipient_over")
        if block_new and amount > float(block_new) and not self._recipient_seen_before(recipient_info["address"]):
            blockers.append(
                f"{context_label} is above the new-recipient threshold for a first-time recipient."
            )

        normalized_budget_category = str(budget_category or spend_type or "all").lower()
        for budget in self.profile.get_budgets():
            category = str(budget.get("category") or "all").lower()
            if category not in {"all", normalized_budget_category, spend_type}:
                continue
            spent = self._spend_for_budget(budget)
            projected = spent + amount
            amount_limit = float(budget.get("amount", 0.0) or 0.0)
            if projected > amount_limit:
                message = (
                    f"{context_label} would exceed the {budget.get('period')} budget for {budget.get('category')} "
                    f"({projected:.2f} > {amount_limit:.2f} USDC)."
                )
                if budget.get("strict"):
                    blockers.append(message)
                else:
                    warnings.append(message)

        return {
            "allowed": not blockers,
            "blockers": blockers,
            "warnings": warnings,
            "known_recipient": known_recipient,
        }

    def _record_payment(
        self,
        record_type: str,
        description: str,
        amount: float,
        tx_id: str,
        recipient_info: dict,
        budget_category: str,
        extra_metadata: dict | None = None,
    ):
        metadata = {
            "recipient": recipient_info["address"],
            "recipient_alias": recipient_info.get("alias", ""),
            "recipient_kind": recipient_info.get("kind", "address"),
            "recipient_user_id": recipient_info.get("wallet_user_id", ""),
            "recipient_internal_wallet": bool(recipient_info.get("is_internal_wallet", False)),
            "budget_category": str(budget_category or record_type).lower(),
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        self.storage.add_record(
            type=record_type,
            description=description,
            amount=amount,
            tx_id=tx_id,
            metadata=metadata,
        )

    def _resolve_invoice_recipient(self, args: dict) -> dict:
        if args.get("recipient_address"):
            return self._resolve_saved_target(args["recipient_address"], "recipient")
        if args.get("recipient_alias"):
            return self._resolve_saved_target(args["recipient_alias"], "recipient")
        wallet = self.wallet_mgr.get_wallet_info()
        return {
            "address": wallet["public_key"],
            "alias": "my_wallet",
            "kind": "self",
            "category": "",
            "note": "",
            "wallet_user_id": self.user_id,
            "wallet_username": "",
            "wallet_display_name": "",
            "is_internal_wallet": True,
            "delivery_preference": "ephemeral",
        }

    async def _call_api(self, messages: list) -> dict:
        headers = {
            "Authorization": f"Bearer {config.GITHUB_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.GITHUB_MODEL,
            "messages": messages,
            "tools": AGENT_TOOLS,
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        for attempt in range(3):
            async with httpx.AsyncClient(timeout=60) as http:
                resp = await http.post(GITHUB_MODELS_URL, headers=headers, json=payload)
                if not resp.is_success:
                    logger.error(f"GitHub Models API {resp.status_code}: {resp.text[:300]}")
                if resp.status_code == 429:
                    wait = 30 * (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt + 1}/3)")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
        resp.raise_for_status()
        return resp.json()

    async def process(self, user_message: str, history: list) -> dict:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        new_messages = [{"role": "user", "content": user_message}]

        for _ in range(10):
            data = await self._call_api(messages)
            choice = data["choices"][0]
            message = choice["message"]

            messages.append(message)
            new_messages.append(message)

            if choice.get("finish_reason") == "stop" or not message.get("tool_calls"):
                return {
                    "message": message.get("content") or "✅ Done.",
                    "keyboard": None,
                    "history": history + new_messages,
                    "awaiting_confirmation": False,
                }

            for tool_call in message["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                try:
                    fn_args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}

                if fn_name == "request_confirmation":
                    action = escape_markdown(str(fn_args.get("action", "")), version=2)
                    details = escape_markdown(str(fn_args.get("details", "")), version=2)
                    keyboard = InlineKeyboardMarkup(
                        [[
                            InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_tx:{tool_call['id']}"),
                            InlineKeyboardButton("❌ Cancel", callback_data="cancel_tx"),
                        ]]
                    )
                    return {
                        "message": (
                            "⚠️ *Confirm Payment*\n\n"
                            f"🌐 Network: *{escape_markdown(self.network_label, version=2)}*\n\n"
                            f"🎯 *{action}*\n\n"
                            f"{details}\n\n"
                            f"💵 Amount: *{float(fn_args.get('amount', 0)):.2f} USDC*\n\n"
                            "_🔒 Payment is private via MagicBlock PER_"
                        ),
                        "keyboard": keyboard,
                        "history": history + new_messages,
                        "awaiting_confirmation": True,
                        "clear_history_on_confirm": True,
                        "pending_tx": {
                            "tool_call_id": tool_call["id"],
                            "action": fn_args.get("action", ""),
                            "amount": fn_args.get("amount", 0),
                            "details": fn_args.get("details", ""),
                            "messages": messages,
                        },
                    }

                result = await self._execute_tool(fn_name, fn_args)
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
                messages.append(tool_msg)
                new_messages.append(tool_msg)

        return {"message": "✅ Done.", "keyboard": None, "history": history + new_messages}

    async def resume_after_confirmation(self, tool_call_id: str, messages: list, history: list) -> dict:
        messages = list(messages)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps({"confirmed": True}, ensure_ascii=False),
            }
        )

        for _ in range(10):
            data = await self._call_api(messages)
            choice = data["choices"][0]
            message = choice["message"]
            messages.append(message)

            if choice.get("finish_reason") == "stop" or not message.get("tool_calls"):
                return {
                    "message": message.get("content") or "✅ Payment completed.",
                    "keyboard": None,
                    "history": [],
                    "awaiting_confirmation": False,
                }

            for tool_call in message["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                try:
                    fn_args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}

                result = await self._execute_tool(fn_name, fn_args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        return {"message": "✅ Payment completed.", "keyboard": None, "history": []}

    async def _deposit_then_transfer(self, amount: float, recipient_info: dict, memo: str) -> dict:
        recipient = recipient_info["address"]
        to_balance = recipient_info.get("delivery_preference") or (
            "ephemeral" if recipient_info.get("is_internal_wallet") else "base"
        )
        try:
            logger.info(
                f"Private transfer route selected: fromBalance=base toBalance={to_balance} "
                f"internal={recipient_info.get('is_internal_wallet', False)} recipient={recipient[:8]}..."
            )
            return await self.mb_client.private_transfer(
                recipient=recipient,
                amount=amount,
                memo=memo,
                from_balance="base",
                to_balance=to_balance,
            )
        except ValueError as e:
            err = str(e)
            if "402" in err or "nsufficien" in err or "insufficient" in err.lower():
                retry_to_balance = "base" if to_balance == "ephemeral" else to_balance
                logger.info(
                    f"Base-balance private transfer insufficient or unavailable; retrying from PER "
                    f"with toBalance={retry_to_balance}"
                )
                return await self.mb_client.private_transfer(
                    recipient=recipient,
                    amount=amount,
                    memo=memo,
                    from_balance="ephemeral",
                    to_balance=retry_to_balance,
                )
            raise

    async def _run_due_recurring(self, limit: int | None = None) -> dict:
        due_items = self.profile.get_due_recurring_payments()
        if not due_items:
            return {"success": True, "processed": 0, "payments": [], "message": "No due recurring payments."}

        if limit:
            due_items = due_items[: int(limit)]

        processed = []
        skipped = []
        for item in due_items:
            recipient_info = self._resolve_saved_target(item.get("target_alias") or item.get("target_address"), "recipient")
            guardrails = self._evaluate_payment_guardrails(
                amount=float(item["amount"]),
                recipient_info=recipient_info,
                spend_type="transfer",
                budget_category=item.get("category", "transfer"),
                context_label=f"Recurring payment {item['id']}",
            )
            if guardrails["blockers"]:
                skipped.append({"recurring_id": item["id"], "reason": "; ".join(guardrails["blockers"])})
                continue

            memo = item.get("memo") or f"Recurring payment {item['id']}"
            result = await self._deposit_then_transfer(
                amount=float(item["amount"]),
                recipient_info=recipient_info,
                memo=memo,
            )
            self.profile.mark_recurring_executed(item["id"], result.get("tx_id", ""))
            self._record_payment(
                record_type="send",
                description=f"Recurring: {memo}",
                amount=float(item["amount"]),
                tx_id=result.get("tx_id", ""),
                recipient_info=recipient_info,
                budget_category=item.get("category", "transfer"),
                extra_metadata={"recurring_id": item["id"], "warnings": guardrails["warnings"]},
            )
            processed.append(
                {
                    "recurring_id": item["id"],
                    "tx_id": result.get("tx_id", ""),
                    "amount": float(item["amount"]),
                    "warnings": guardrails["warnings"],
                }
            )

        return {
            "success": True,
            "processed": len(processed),
            "payments": processed,
            "skipped": skipped,
            "message": f"Processed {len(processed)} recurring payments.",
        }

    async def _execute_tool(self, tool_name: str, args: dict) -> dict:
        logger.info(f"Tool: {tool_name}({args})")
        try:
            if tool_name == "get_balance":
                return await self.mb_client.get_balance()

            if tool_name == "save_contact":
                target = self._resolve_saved_target(args["address"], "contact")
                contact = self.profile.save_contact(
                    args["alias"],
                    target["address"],
                    args.get("note", ""),
                    wallet_user_id=target.get("wallet_user_id", ""),
                    wallet_username=target.get("wallet_username", ""),
                    wallet_display_name=target.get("wallet_display_name", ""),
                    is_internal_wallet=bool(target.get("is_internal_wallet", False)),
                )
                return {"success": True, "contact": contact}

            if tool_name == "list_contacts":
                return {"contacts": self.profile.get_contacts()}

            if tool_name == "remove_contact":
                removed = self.profile.remove_contact(args["alias"])
                return {"success": removed, "alias": args["alias"], "removed": removed}

            if tool_name == "save_merchant_profile":
                target = self._resolve_saved_target(args["address"], "merchant")
                merchant = self.profile.save_merchant(
                    alias=args["alias"],
                    address=target["address"],
                    category=args.get("category", "general"),
                    note=args.get("note", ""),
                    default_amount=float(args.get("default_amount", 0.0) or 0.0),
                    wallet_user_id=target.get("wallet_user_id", ""),
                    wallet_username=target.get("wallet_username", ""),
                    wallet_display_name=target.get("wallet_display_name", ""),
                    is_internal_wallet=bool(target.get("is_internal_wallet", False)),
                )
                return {"success": True, "merchant": merchant}

            if tool_name == "list_merchant_profiles":
                return {"merchants": self.profile.get_merchants()}

            if tool_name == "remove_merchant_profile":
                removed = self.profile.remove_merchant(args["alias"])
                return {"success": removed, "alias": args["alias"], "removed": removed}

            if tool_name == "create_payment_request":
                recipient_info = self._resolve_invoice_recipient(args)
                invoice = self.profile.create_invoice(
                    amount=float(args["amount"]),
                    description=args["description"],
                    recipient_address=recipient_info["address"],
                    recipient_alias=recipient_info.get("alias", ""),
                    due_date=args.get("due_date", ""),
                    note=args.get("note", ""),
                )
                return {
                    "success": True,
                    "invoice": invoice,
                    "share_code": invoice["share_code"],
                    "share_text": (
                        f"Payment request {invoice['id']}\n"
                        f"Amount: {invoice['amount']:.2f} USDC\n"
                        f"Recipient: {invoice['recipient_alias'] or invoice['recipient_address']}\n"
                        f"Description: {invoice['description']}\n"
                        f"Share code: {invoice['share_code']}"
                    ),
                }

            if tool_name == "list_payment_requests":
                return {"invoices": self.profile.get_invoices(status=args.get("status"))}

            if tool_name == "cancel_payment_request":
                cancelled = self.profile.cancel_invoice(args["invoice_id"])
                return {"success": cancelled, "invoice_id": args["invoice_id"], "cancelled": cancelled}

            if tool_name == "pay_payment_request":
                payload = UserProfileStorage.decode_payment_request(args["share_code"])
                recipient_info = self._resolve_saved_target(payload["recipient_address"], "invoice recipient")
                amount = float(payload["amount"])
                guardrails = self._evaluate_payment_guardrails(
                    amount=amount,
                    recipient_info=recipient_info,
                    spend_type="purchase",
                    budget_category="invoice",
                    context_label=f"Invoice {payload.get('invoice_id', 'request')}",
                )
                if guardrails["blockers"]:
                    return {"success": False, "error": "; ".join(guardrails["blockers"])}

                memo = payload.get("description", "Invoice payment")
                result = await self._deposit_then_transfer(
                    amount=amount,
                    recipient_info=recipient_info,
                    memo=memo,
                )
                self._record_payment(
                    record_type="purchase",
                    description=f"Invoice: {payload.get('description', 'Payment request')}",
                    amount=amount,
                    tx_id=result.get("tx_id", ""),
                    recipient_info=recipient_info,
                    budget_category="invoice",
                    extra_metadata={
                        "invoice_id": payload.get("invoice_id", ""),
                        "warnings": guardrails["warnings"],
                    },
                )
                local_invoice = self.profile.get_invoice(payload.get("invoice_id", ""))
                if local_invoice:
                    self.profile.update_invoice_status(
                        payload["invoice_id"],
                        status="paid",
                        paid_tx_id=result.get("tx_id", ""),
                        payer=self.wallet_mgr.get_wallet_info()["public_key"],
                    )
                return {
                    "success": True,
                    "tx_id": result.get("tx_id"),
                    "amount": amount,
                    "invoice_id": payload.get("invoice_id", ""),
                    "warnings": guardrails["warnings"],
                    "network": self.network_label,
                }

            if tool_name == "create_recurring_payment":
                recipient_info = self._resolve_saved_target(args["target"], "recurring target")
                recurring = self.profile.create_recurring_payment(
                    target_address=recipient_info["address"],
                    target_alias=recipient_info.get("alias", ""),
                    target_kind=recipient_info.get("kind", "address"),
                    amount=float(args["amount"]),
                    interval=args["interval"],
                    memo=args.get("memo", ""),
                    category=args.get("category") or recipient_info.get("category") or "transfer",
                    start_at=args.get("start_at", ""),
                )
                return {"success": True, "recurring": recurring}

            if tool_name == "list_recurring_payments":
                return {"recurring": self.profile.get_recurring_payments(active_only=bool(args.get("active_only", False)))}

            if tool_name == "pause_recurring_payment":
                recurring = self.profile.set_recurring_active(args["recurring_id"], False)
                return {"success": bool(recurring), "recurring": recurring}

            if tool_name == "resume_recurring_payment":
                recurring = self.profile.set_recurring_active(args["recurring_id"], True)
                return {"success": bool(recurring), "recurring": recurring}

            if tool_name == "delete_recurring_payment":
                removed = self.profile.delete_recurring_payment(args["recurring_id"])
                return {"success": removed, "recurring_id": args["recurring_id"], "removed": removed}

            if tool_name == "run_due_recurring_payments":
                return await self._run_due_recurring(limit=int(args["limit"]) if args.get("limit") else None)

            if tool_name == "set_budget":
                budget = self.profile.set_budget(
                    category=args["category"],
                    period=args["period"],
                    amount=float(args["amount"]),
                    strict=bool(args.get("strict", False)),
                )
                return {"success": True, "budget": budget}

            if tool_name == "list_budgets":
                return {"budgets": self.profile.get_budgets()}

            if tool_name == "remove_budget":
                removed = self.profile.remove_budget(args["budget_id"])
                return {"success": removed, "budget_id": args["budget_id"], "removed": removed}

            if tool_name == "get_budget_status":
                return {"budgets": self._get_budget_status_entries()}

            if tool_name == "set_risk_rules":
                normalized = {}
                for key in [
                    "max_single_payment",
                    "daily_spend_limit",
                    "monthly_spend_limit",
                    "require_known_contact_over",
                    "block_new_recipient_over",
                ]:
                    if key not in args:
                        continue
                    value = args.get(key)
                    normalized[key] = None if value in (None, 0, 0.0, "0", "0.0", "") else value
                rules = self.profile.update_risk_rules(normalized)
                return {"success": True, "risk_rules": rules}

            if tool_name == "get_risk_rules":
                return {"risk_rules": self.profile.get_risk_rules()}

            if tool_name == "private_transfer":
                amount = float(args["amount"])
                recipient_info = self._resolve_saved_target(args["recipient"], "recipient")
                guardrails = self._evaluate_payment_guardrails(
                    amount=amount,
                    recipient_info=recipient_info,
                    spend_type="transfer",
                    budget_category="transfer",
                    context_label="Transfer",
                )
                if guardrails["blockers"]:
                    return {"success": False, "error": "; ".join(guardrails["blockers"])}
                result = await self._deposit_then_transfer(
                    amount=amount,
                    recipient_info=recipient_info,
                    memo=args.get("memo", ""),
                )
                self._record_payment(
                    record_type="send",
                    description=args.get("memo", "Transfer"),
                    amount=amount,
                    tx_id=result.get("tx_id", ""),
                    recipient_info=recipient_info,
                    budget_category="transfer",
                    extra_metadata={"warnings": guardrails["warnings"]},
                )
                return {
                    "success": True,
                    "tx_id": result.get("tx_id"),
                    "amount": amount,
                    "network": self.network_label,
                    "warnings": guardrails["warnings"],
                    "note": (
                        "Funds sent to the recipient's private bot wallet balance."
                        if recipient_info.get("is_internal_wallet")
                        else "Funds sent privately to the recipient wallet address."
                    ),
                }

            if tool_name == "book_service":
                merchant_value = args.get("merchant_address") or config.DEMO_MERCHANT_ADDRESS
                if not merchant_value:
                    return {
                        "success": False,
                        "error": "No merchant address is available for this booking yet. Ask the user for a payment address or save a merchant alias.",
                    }
                recipient_info = self._resolve_saved_target(merchant_value, "merchant")
                amount = float(args["amount"])
                budget_category = recipient_info.get("category") or args.get("service_type", "booking")
                guardrails = self._evaluate_payment_guardrails(
                    amount=amount,
                    recipient_info=recipient_info,
                    spend_type="booking",
                    budget_category=budget_category,
                    context_label="Booking",
                )
                if guardrails["blockers"]:
                    return {"success": False, "error": "; ".join(guardrails["blockers"])}
                result = await self._deposit_then_transfer(
                    amount=amount,
                    recipient_info=recipient_info,
                    memo=f"Booking: {args['description']}",
                )
                self._record_payment(
                    record_type="booking",
                    description=args["description"],
                    amount=amount,
                    tx_id=result.get("tx_id", ""),
                    recipient_info=recipient_info,
                    budget_category=budget_category,
                    extra_metadata={
                        "service_type": args["service_type"],
                        "warnings": guardrails["warnings"],
                    },
                )
                return {
                    "success": True,
                    "booking_id": result.get("tx_id", "BK-DEMO"),
                    "amount": amount,
                    "network": self.network_label,
                    "warnings": guardrails["warnings"],
                }

            if tool_name == "buy_product":
                merchant_value = args.get("merchant_address") or args.get("store") or config.DEMO_MERCHANT_ADDRESS
                if not merchant_value:
                    return {
                        "success": False,
                        "error": "No merchant address is available for this purchase yet. Ask the user for a payment address or save a merchant alias.",
                    }
                recipient_info = self._resolve_saved_target(merchant_value, "merchant")
                amount = float(args["amount"])
                budget_category = recipient_info.get("category") or str(args.get("store", "purchase")).strip().lower() or "purchase"
                guardrails = self._evaluate_payment_guardrails(
                    amount=amount,
                    recipient_info=recipient_info,
                    spend_type="purchase",
                    budget_category=budget_category,
                    context_label="Purchase",
                )
                if guardrails["blockers"]:
                    return {"success": False, "error": "; ".join(guardrails["blockers"])}
                result = await self._deposit_then_transfer(
                    amount=amount,
                    recipient_info=recipient_info,
                    memo=f"Purchase: {args['product_name']}",
                )
                self._record_payment(
                    record_type="purchase",
                    description=f"Purchase: {args['product_name']}",
                    amount=amount,
                    tx_id=result.get("tx_id", ""),
                    recipient_info=recipient_info,
                    budget_category=budget_category,
                    extra_metadata={
                        "store": args.get("store", "unknown"),
                        "warnings": guardrails["warnings"],
                    },
                )
                return {
                    "success": True,
                    "order_id": result.get("tx_id", "ORD-DEMO"),
                    "product": args["product_name"],
                    "network": self.network_label,
                    "warnings": guardrails["warnings"],
                }

            if tool_name == "get_spending_history":
                records = self.storage.get_history(
                    period=args.get("period", "month"),
                    category=args.get("category"),
                )
                return {"records": records[:20], "stats": self.storage.get_stats()}

            if tool_name == "deposit_to_per":
                amount = float(args["amount"])
                result = await self.mb_client.deposit_to_per(amount)
                self.storage.add_record(
                    type="deposit",
                    description="Manual deposit to PER",
                    amount=amount,
                    tx_id=result.get("tx_id", ""),
                )
                result["network"] = self.network_label
                return result

            if tool_name == "withdraw_from_per":
                amount = float(args["amount"])
                result = await self.mb_client.withdraw_from_per(amount)
                self.storage.add_record(
                    type="withdraw",
                    description="Withdraw from PER",
                    amount=amount,
                    tx_id=result.get("tx_id", ""),
                )
                result["network"] = self.network_label
                return result

            return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}", exc_info=True)
            return {"error": str(e), "success": False}
