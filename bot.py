"""
🤖 Autonomous Consumer Agent Bot
"""

import logging
import re
from html import escape as html_escape
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
from config import Config
from agent import ConsumerAgent
from storage import SpendingStorage, UserProfileStorage
from wallet import WalletManager
from magicblock import MagicBlockClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
config = Config()

HISTORY_KEY = "chat_history"
NETWORK_KEY = "use_devnet"


def html_code(text: str) -> str:
    return f"<code>{html_escape(text)}</code>"


def sanitize_markdown_text(text: str) -> str:
    if not text:
        return text
    # GitHub/LLM output often uses **bold**, while Telegram Markdown expects *bold*.
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Escape underscores in @handles so saved aliases like @name_with_underscore don't break parsing.
    text = re.sub(
        r"@([A-Za-z0-9_]+)",
        lambda m: "@" + m.group(1).replace("_", r"\_"),
        text,
    )
    return text


async def safe_edit_message_text(message, text: str, **kwargs):
    rendered_text = text
    if kwargs.get("parse_mode") == ParseMode.MARKDOWN:
        rendered_text = sanitize_markdown_text(text)
    try:
        return await message.edit_text(rendered_text, **kwargs)
    except Exception as e:
        logger.warning(f"Formatted message failed, retrying without parse mode: {e}")
        fallback_kwargs = dict(kwargs)
        fallback_kwargs.pop("parse_mode", None)
        fallback_kwargs.pop("disable_web_page_preview", None)
        return await message.edit_text(text, **fallback_kwargs)


def network_name(use_devnet: bool) -> str:
    return "Solana Devnet" if use_devnet else "Solana Mainnet"


def decorate_with_network(message: str, use_devnet: bool) -> str:
    if not message:
        return message
    return f"🌐 *Network:* {network_name(use_devnet)}\n\n{message}"


def confirmation_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm", callback_data="confirm_tx:direct"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_tx"),
    ]])


def format_direct_tool_result(tool_name: str, result: dict) -> str:
    if not result.get("success", False):
        return f"❌ Operation failed\n\n{result.get('error', 'Unknown error')}"

    if tool_name == "pay_payment_request":
        warnings = result.get("warnings") or []
        warning_text = ""
        if warnings:
            warning_text = "\n\n⚠️ Warnings:\n" + "\n".join(f"• {w}" for w in warnings)
        return (
            "✅ Payment request paid successfully.\n\n"
            f"💵 Amount: *{float(result.get('amount', 0.0)):.2f} USDC*\n"
            f"🧾 Invoice: `{result.get('invoice_id', 'unknown')}`\n"
            f"🔗 Tx ID: `{result.get('tx_id', '')}`"
            + warning_text
        )

    if tool_name == "run_due_recurring_payments":
        payments = result.get("payments") or []
        skipped = result.get("skipped") or []
        lines = [
            "✅ Recurring payments processed.",
            "",
            f"🔁 Processed: *{int(result.get('processed', 0))}*",
        ]
        for payment in payments[:5]:
            lines.append(
                f"• `{payment.get('recurring_id', '')}` — {float(payment.get('amount', 0.0)):.2f} USDC — `{payment.get('tx_id', '')}`"
            )
        if skipped:
            lines.append("")
            lines.append(f"⚠️ Skipped: *{len(skipped)}*")
        return "\n".join(lines)

    return "✅ Done."


# ─── Keyboards ────────────────────────────────────────────────────────────────

def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💬 Agent"), KeyboardButton("💰 Balance")],
        [KeyboardButton("📤 Send"), KeyboardButton("📋 History")],
        [KeyboardButton("⚙️ Wallet"), KeyboardButton("ℹ️ Help")],
    ], resize_keyboard=True)


def agent_intro_text():
    return (
        "🤖 *Autonomous Consumer Agent*\n\n"
        "Your private AI agent for purchases, bookings, and transfers.\n\n"
        "🔒 *Private payments* via MagicBlock Private Ephemeral Rollup\n"
        "🧠 *Intelligence* from GitHub Models (free)\n"
        "📊 *Spending history* — yours only, not advertisers'\n"
        "🗂 *Contacts, merchants, invoices, recurring payments, budgets, risk rules*\n\n"
        "Example commands:\n"
        "• `Save Alex as 9xQeWv...`\n"
        "• `Create a 25 USDC payment request for dinner`\n"
        "• `Set a weekly food budget of 80 USDC`\n"
        "• `Create a monthly recurring payment of 15 USDC to rentwallet`\n"
        "• `Book a hotel in London for 3 nights`\n"
        "• `Buy a gift for ~50 USDC`\n"
        "• `Send 10 USDC to Alex`\n"
        "• `Show my spending this week`\n\n"
        "💡 _Just write what you need_"
    )


# ─── History helpers ──────────────────────────────────────────────────────────

def get_history(context: ContextTypes.DEFAULT_TYPE) -> list:
    return context.user_data.get(HISTORY_KEY, [])

def set_history(context: ContextTypes.DEFAULT_TYPE, history: list):
    context.user_data[HISTORY_KEY] = history

def clear_history(context: ContextTypes.DEFAULT_TYPE):
    context.user_data[HISTORY_KEY] = []


def get_use_devnet(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return context.user_data.get(NETWORK_KEY, config.USE_DEVNET)


def set_use_devnet(context: ContextTypes.DEFAULT_TYPE, value: bool):
    context.user_data[NETWORK_KEY] = value


def sync_wallet_directory(update: Update, wallet_mgr: WalletManager):
    try:
        user = update.effective_user
        wallet_mgr.sync_directory(
            username=getattr(user, "username", "") or "",
            first_name=getattr(user, "first_name", "") or "",
            last_name=getattr(user, "last_name", "") or "",
        )
    except Exception as e:
        logger.warning(f"Failed to sync wallet directory for user {getattr(update.effective_user, 'id', 'unknown')}: {e}")


# ─── Commands ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    set_use_devnet(context, get_use_devnet(context))
    wallet_mgr = WalletManager(user_id)

    if not wallet_mgr.has_wallet():
        wallet = wallet_mgr.create_wallet()
        sync_wallet_directory(update, wallet_mgr)
        await update.message.reply_text(
            f"👋 Welcome, *{user.first_name}*!\n\n"
            f"🆕 New Solana wallet created:\n"
            f"`{wallet['public_key']}`\n\n"
            + agent_intro_text(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard()
        )
        prefix = "⚠️ Save your seed phrase — tap to reveal:\n\n"
        suffix = "\n\n🔐 Never share this with anyone. Delete this message after saving."
        mnemonic = wallet['mnemonic']
        full_text = prefix + mnemonic + suffix
        await update.message.reply_text(
            full_text,
            entities=[MessageEntity(
                type=MessageEntity.SPOILER,
                offset=len(prefix.encode('utf-16-le')) // 2,
                length=len(mnemonic.encode('utf-16-le')) // 2,
            )]
        )
    else:
        wallet = wallet_mgr.get_wallet_info()
        sync_wallet_directory(update, wallet_mgr)
        pk = wallet['public_key']
        await update.message.reply_text(
            f"👋 Welcome back, *{user.first_name}*!\n\n"
            f"🔑 Wallet: `{pk[:8]}...{pk[-6:]}`\n\n"
            + agent_intro_text(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard()
        )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Bot Commands*\n\n"
        "/start — Start the bot\n"
        "/balance — Check balance\n"
        "/history — Spending history\n"
        "/wallet — Wallet management\n"
        "/agent — Activate AI agent\n"
        "/clear — Clear conversation context\n\n"
        "Examples:\n"
        "• `Save Alice as SOLANA_ADDRESS`\n"
        "• `Create a 12 USDC invoice for coffee`\n"
        "• `Pay this request: PERPAY:...`\n"
        "• `Create a weekly recurring payment of 8 USDC to Alice`\n"
        "• `Set a monthly travel budget of 300 USDC`\n"
        "• `Set max single payment to 50 USDC`\n\n"
        "🔒 *Privacy:* All transfers go through Private Ephemeral Rollup (PER) by MagicBlock.\n\n"
        "📊 *Spending history* is stored only locally.\n\n"
        "🧠 *AI:* GitHub Models (free inference)",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wallet_mgr = WalletManager(user_id)
    use_devnet = get_use_devnet(context)

    if not wallet_mgr.has_wallet():
        await update.message.reply_text("❌ Wallet not found. Use /start")
        return

    msg = await update.message.reply_text("⏳ Fetching balance...")
    client = MagicBlockClient(wallet_mgr, config, use_devnet=use_devnet)

    try:
        balances = await client.get_balance()
        pk = wallet_mgr.get_wallet_info()["public_key"]
        cluster = "devnet" if use_devnet else "mainnet"
        solana_display = f"{balances['solana_usdc']:.4f} USDC"
        private_source = balances.get("private_balance_source", "unavailable")
        if private_source == "api":
            private_display = f"{balances['private_usdc']:.4f} USDC"
            per_note = ""
        elif private_source == "history":
            private_display = f"~{balances['private_usdc']:.4f} USDC"
            per_note = " <i>(estimated from local history)</i>"
        else:
            if use_devnet:
                private_display = f"~{balances['private_usdc']:.4f} USDC"
                per_note = " <i>(estimated from local history)</i>"
            else:
                private_display = "Unavailable"
                per_note = " <i>(MagicBlock auth required on mainnet)</i>"
        explorer_url = html_escape(
            balances.get(
                "explorer_url",
                f"https://explorer.solana.com/address/{pk}?cluster={cluster}"
            ),
            quote=True,
        )
        demo_note = "\n\n⚠️ <i>Demo mode: API unavailable</i>" if balances.get("demo_mode") else ""
        private_auth_note = ""
        if balances.get("needs_private_auth"):
            private_auth_note = "\n\nℹ️ <i>On mainnet, real Private PER balance requires a MagicBlock authorization token. Without it, the bot falls back to local history.</i>"
        auth_error_note = ""
        if balances.get("auth_error"):
            auth_error_note = f"\n\n⚠️ <i>MagicBlock auth status:</i>\n<code>{html_escape(str(balances['auth_error']))}</code>"

        faucet_note = ""
        if balances["solana_usdc"] == 0.0 and balances["private_usdc"] == 0.0 and use_devnet:
            faucet_note = (
                "\n\n💡 <b>Balance is 0?</b> Get free devnet USDC:\n"
                '<a href="https://spl-token-faucet.com/?token-name=USDC">spl-token-faucet.com</a>\n'
                f"Your address:\n{html_code(pk)}"
            )

        await safe_edit_message_text(
            msg,
            f"💰 <b>Your Balance</b>\n\n"
            f"🌐 Solana (public): {html_code(solana_display)}\n"
            f"🔒 Private PER: {html_code(private_display)}{per_note}\n\n"
            f"📍 Wallet:\n{html_code(pk)}\n\n"
            f'🔍 <a href="{explorer_url}">View on Solana Explorer</a>'
            + demo_note
            + private_auth_note
            + auth_error_note
            + faucet_note,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        await safe_edit_message_text(msg, f"⚠️ Error fetching balance: {str(e)}")


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    storage = SpendingStorage(user_id)
    records = storage.get_history(limit=10)

    if not records:
        await update.message.reply_text(
            "📋 *No spending history yet*\n\n"
            "Your history is stored only on your device.\n"
            "Start using the agent to make purchases and transfers!",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    lines = ["📊 *Recent Transactions*\n_Only you can see this_\n"]
    total = 0.0
    for r in records:
        emoji = {"send": "📤", "receive": "📥", "booking": "🏨", "purchase": "🛒"}.get(r["type"], "💳")
        lines.append(
            f"{emoji} *{r['description']}*\n"
            f"   💵 {r['amount']:.2f} USDC | {r['date']}\n"
            f"   🏷 `{r.get('tx_id', 'private')[:16]}...`"
        )
        if r["type"] in ("send", "booking", "purchase"):
            total += r["amount"]
    lines.append(f"\n💸 Total spent: *{total:.2f} USDC*")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Full stats", callback_data="stats_full")],
        [InlineKeyboardButton("🗑 Clear history", callback_data="clear_history")]
    ])
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


async def wallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wallet_mgr = WalletManager(user_id)
    use_devnet = get_use_devnet(context)

    if not wallet_mgr.has_wallet():
        await update.message.reply_text("❌ Wallet not found. Use /start")
        return

    info = wallet_mgr.get_wallet_info()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Copy address", callback_data="copy_address")],
        [InlineKeyboardButton("💾 Export private key", callback_data="export_key")],
        [InlineKeyboardButton("🌐 Switch to Mainnet" if use_devnet else "🧪 Switch to Devnet", callback_data="toggle_network")],
    ])
    await update.message.reply_text(
        f"⚙️ *Wallet Management*\n\n"
        f"📍 Address:\n`{info['public_key']}`\n\n"
        f"🌐 Network: {network_name(use_devnet)}\n\n"
        f"_Private key is encrypted and stored securely_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_history(context)
    context.user_data.pop("pending_tx", None)
    await update.message.reply_text(
        "🗑 *Conversation context cleared.*",
        parse_mode=ParseMode.MARKDOWN
    )


async def agent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = get_history(context)
    status = f"📝 {len(history)} messages in context" if history else "🆕 Fresh context"
    use_devnet = get_use_devnet(context)
    due_count = len(UserProfileStorage(str(update.effective_user.id)).get_due_recurring_payments())
    due_note = f"⏰ Due recurring payments: *{due_count}*\n\n" if due_count else ""
    await update.message.reply_text(
        f"🤖 *Agent ready* — {status}\n\n"
        f"🌐 Network: *{network_name(use_devnet)}*\n\n"
        f"{due_note}"
        "Tell me what to do:\n"
        "• `Save Bob as ADDRESS`\n"
        "• `Create a payment request for 18 USDC`\n"
        "• `Run recurring payments`\n"
        "• `Book a hotel in Paris for 2 nights`\n"
        "• `Send 20 USDC to Alex`\n"
        "• `How much did I spend this month?`\n"
        "• `Set a weekly shopping budget of 100 USDC`",
        parse_mode=ParseMode.MARKDOWN
    )


# ─── Main message handler ─────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.effective_user.id)

    shortcuts = {
        "💬 Agent": agent_cmd,
        "💰 Balance": balance_cmd,
        "📤 Send": lambda u, c: u.message.reply_text(
            "Send USDC — just tell the agent:\n`Send X USDC to <address>`",
            parse_mode=ParseMode.MARKDOWN
        ),
        "📋 History": history_cmd,
        "⚙️ Wallet": wallet_cmd,
        "ℹ️ Help": help_cmd,
    }
    if text in shortcuts:
        return await shortcuts[text](update, context)

    wallet_mgr = WalletManager(user_id)
    if not wallet_mgr.has_wallet():
        await update.message.reply_text("❌ Please run /start first")
        return
    sync_wallet_directory(update, wallet_mgr)

    thinking_msg = await update.message.reply_text("🤔 Thinking...")
    use_devnet = get_use_devnet(context)

    try:
        storage = SpendingStorage(user_id)
        agent = ConsumerAgent(user_id=user_id, wallet_mgr=wallet_mgr, storage=storage, use_devnet=use_devnet)
        profile = UserProfileStorage(user_id)

        lower_text = text.lower()
        payment_request_match = re.search(r"(PERPAY:[A-Za-z0-9_\-=]+)", text)
        if payment_request_match:
            try:
                share_code = payment_request_match.group(1).strip()
                payload = UserProfileStorage.decode_payment_request(share_code)
                context.user_data["pending_tx"] = {
                    "mode": "direct_tool",
                    "tool_name": "pay_payment_request",
                    "tool_args": {"share_code": share_code},
                    "use_devnet": use_devnet,
                }
                details = (
                    "⚠️ *Confirm Payment Request*\n\n"
                    f"🧾 Invoice: `{payload.get('invoice_id', 'unknown')}`\n"
                    f"🎯 Recipient: `{payload.get('recipient_alias') or payload.get('recipient_address', '')}`\n"
                    f"📝 Description: {payload.get('description', 'Payment request')}\n"
                    f"💵 Amount: *{float(payload.get('amount', 0.0)):.2f} USDC*"
                )
                await safe_edit_message_text(
                    thinking_msg,
                    decorate_with_network(details, use_devnet),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=confirmation_keyboard(),
                )
                return
            except Exception as e:
                await safe_edit_message_text(
                    thinking_msg,
                    decorate_with_network(f"❌ Invalid payment request\n\n{str(e)}", use_devnet),
                )
                return

        recurring_run_match = re.search(r"\b(run|process|pay)\s+(all\s+)?(due\s+)?recurring", lower_text)
        if recurring_run_match:
            due_items = profile.get_due_recurring_payments()
            if not due_items:
                await safe_edit_message_text(
                    thinking_msg,
                    decorate_with_network("ℹ️ No due recurring payments right now.", use_devnet),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            total_amount = sum(float(item.get("amount", 0.0) or 0.0) for item in due_items)
            context.user_data["pending_tx"] = {
                "mode": "direct_tool",
                "tool_name": "run_due_recurring_payments",
                "tool_args": {},
                "use_devnet": use_devnet,
            }
            details = (
                "⚠️ *Confirm Recurring Payments*\n\n"
                f"🔁 Due payments: *{len(due_items)}*\n"
                f"💵 Total amount: *{total_amount:.2f} USDC*\n\n"
                "Use this to process all currently due recurring payments."
            )
            await safe_edit_message_text(
                thinking_msg,
                decorate_with_network(details, use_devnet),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=confirmation_keyboard(),
            )
            return

        save_contact_match = re.search(
            r"^\s*save\s+(.+?)\s+as(?:\s+alias)?\s+(@?[A-Za-z0-9_]+|[1-9A-HJ-NP-Za-km-z]{32,44})\s*$",
            text,
            re.IGNORECASE,
        )
        if save_contact_match:
            alias = save_contact_match.group(1)
            address = save_contact_match.group(2)
            result = await agent._execute_tool("save_contact", {"alias": alias, "address": address})
            if result.get("success"):
                contact = result.get("contact", {})
                await safe_edit_message_text(
                    thinking_msg,
                    decorate_with_network(
                        (
                            f"✅ Saved alias *{contact.get('alias', alias)}*\n\n"
                            f"📍 Address: `{contact.get('address', address)}`"
                        ),
                        use_devnet,
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await safe_edit_message_text(
                    thinking_msg,
                    decorate_with_network(f"❌ Could not save alias\n\n{result.get('error', 'Unknown error')}", use_devnet),
                )
            return

        deposit_match = re.search(r"(deposit|top up|topup|add)\s+(\d+(?:\.\d+)?)\s*usdc", lower_text)
        withdraw_match = re.search(r"(withdraw|cash out|cashout|move)\s+(\d+(?:\.\d+)?)\s*usdc", lower_text)
        if deposit_match and ("per" in lower_text or "private" in lower_text):
            result = await agent._execute_tool("deposit_to_per", {"amount": float(deposit_match.group(2))})
            if result.get("success"):
                await safe_edit_message_text(
                    thinking_msg,
                    decorate_with_network(
                        f"✅ Deposit submitted successfully\\.\n\n💵 Amount: *{float(result['amount']):.2f} USDC*\n🧾 Tx ID: `{result['tx_id']}`",
                        use_devnet
                    ),
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                await safe_edit_message_text(
                    thinking_msg,
                    decorate_with_network(f"❌ Deposit failed\n\n{result.get('error', 'Unknown error')}", use_devnet)
                )
            return

        if withdraw_match and ("per" in lower_text or "private" in lower_text):
            result = await agent._execute_tool("withdraw_from_per", {"amount": float(withdraw_match.group(2))})
            if result.get("success"):
                await safe_edit_message_text(
                    thinking_msg,
                    decorate_with_network(
                        f"✅ Withdraw submitted successfully\\.\n\n💵 Amount: *{float(result['amount']):.2f} USDC*\n🧾 Tx ID: `{result['tx_id']}`",
                        use_devnet
                    ),
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                await safe_edit_message_text(
                    thinking_msg,
                    decorate_with_network(f"❌ Withdraw failed\n\n{result.get('error', 'Unknown error')}", use_devnet)
                )
            return

        history = get_history(context)
        result = await agent.process(text, history)
        due_items = profile.get_due_recurring_payments()

        set_history(context, result.get("history", history))

        # Сохраняем pending_tx если агент запросил подтверждение
        if result.get("awaiting_confirmation") and result.get("pending_tx"):
            result["pending_tx"]["use_devnet"] = use_devnet
            context.user_data["pending_tx"] = result["pending_tx"]

        message_text = result["message"]
        if due_items and not result.get("awaiting_confirmation"):
            message_text = (
                f"⏰ You have {len(due_items)} due recurring payments. Say `Run recurring payments` to process them.\n\n"
                f"{message_text}"
            )

        await safe_edit_message_text(
            thinking_msg,
            decorate_with_network(message_text, use_devnet),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=result.get("keyboard")
        )

    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        await safe_edit_message_text(thinking_msg, f"⚠️ Agent error: {str(e)}\n\nTry rephrasing your request.")


# ─── Callback Handler ─────────────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data

    # ── Отмена ───────────────────────────────────────────────────────────────
    if data == "cancel_tx":
        context.user_data.pop("pending_tx", None)
        await query.edit_message_text(
            "❌ *Payment cancelled.*",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # ── Подтверждение платежа ─────────────────────────────────────────────────
    if data.startswith("confirm_tx:"):
        pending = context.user_data.get("pending_tx")
        if not pending:
            await query.edit_message_text(
                "⚠️ *Session expired.* Please repeat your request.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        await query.edit_message_text(
            "🔒 *Processing private payment via MagicBlock PER...*",
            parse_mode=ParseMode.MARKDOWN
        )

        try:
            wallet_mgr = WalletManager(user_id)
            storage = SpendingStorage(user_id)
            use_devnet = pending.get("use_devnet", get_use_devnet(context))
            agent = ConsumerAgent(user_id=user_id, wallet_mgr=wallet_mgr, storage=storage, use_devnet=use_devnet)

            if pending.get("mode") == "direct_tool":
                result = await agent._execute_tool(
                    pending["tool_name"],
                    pending.get("tool_args", {}),
                )
                context.user_data.pop("pending_tx", None)
                await safe_edit_message_text(
                    query.message,
                    decorate_with_network(format_direct_tool_result(pending["tool_name"], result), use_devnet),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            result = await agent.resume_after_confirmation(
                tool_call_id=pending["tool_call_id"],
                messages=pending["messages"],
                history=get_history(context)
            )

            # Очищаем после оплаты
            set_history(context, result.get("history", []))
            context.user_data.pop("pending_tx", None)

            await safe_edit_message_text(
                query.message,
                decorate_with_network(result["message"], use_devnet),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=result.get("keyboard")
            )

        except Exception as e:
            logger.error(f"Payment failed: {e}", exc_info=True)
            await safe_edit_message_text(
                query.message,
                decorate_with_network(f"❌ Payment Failed\n\n{str(e)}", use_devnet)
            )
        return

    if data == "toggle_network":
        use_devnet = not get_use_devnet(context)
        set_use_devnet(context, use_devnet)
        wallet_mgr = WalletManager(user_id)
        info = wallet_mgr.get_wallet_info()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy address", callback_data="copy_address")],
            [InlineKeyboardButton("💾 Export private key", callback_data="export_key")],
            [InlineKeyboardButton("🌐 Switch to Mainnet" if use_devnet else "🧪 Switch to Devnet", callback_data="toggle_network")],
        ])
        await query.edit_message_text(
            f"⚙️ *Wallet Management*\n\n"
            f"📍 Address:\n`{info['public_key']}`\n\n"
            f"🌐 Network: {network_name(use_devnet)}\n\n"
            f"_Private key is encrypted and stored securely_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        return

    # ── Stats ─────────────────────────────────────────────────────────────────
    if data == "stats_full":
        storage = SpendingStorage(user_id)
        stats = storage.get_stats()
        await query.edit_message_text(
            f"📊 *Full Statistics*\n\n"
            f"💸 Total spent: *{stats['total_sent']:.2f} USDC*\n"
            f"📥 Total received: *{stats['total_received']:.2f} USDC*\n"
            f"📅 This week: *{stats['week_spent']:.2f} USDC*\n"
            f"🗓 This month: *{stats['month_spent']:.2f} USDC*\n\n"
            f"🛒 Purchases: {stats['purchases']}\n"
            f"🏨 Bookings: {stats['bookings']}\n"
            f"📤 Transfers: {stats['transfers']}\n"
            f"📋 Total records: {stats['total_records']}",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data == "clear_history":
        storage = SpendingStorage(user_id)
        storage.clear_history()
        await query.edit_message_text(
            "🗑 *Spending history cleared.*",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data == "copy_address":
        wallet_mgr = WalletManager(user_id)
        info = wallet_mgr.get_wallet_info()
        await query.edit_message_text(
            f"📋 *Your Solana address:*\n\n`{info['public_key']}`\n\n_Tap to copy_",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data == "export_key":
        await query.edit_message_text(
            "⚠️ *Security Warning*\n\n"
            "Private key export is disabled for your protection.\n"
            "Your key is encrypted and stored securely.",
            parse_mode=ParseMode.MARKDOWN
        )
        return


# ─── Error Handler ────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    import telegram
    if isinstance(context.error, telegram.error.Conflict):
        logger.warning("409 Conflict: another bot instance is running. Will recover.")
        return
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("wallet", wallet_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("agent", agent_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("🤖 Consumer Agent Bot started")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
