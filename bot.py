"""
🤖 Autonomous Consumer Agent Bot
"""

import logging
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
from storage import SpendingStorage
from wallet import WalletManager
from magicblock import MagicBlockClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
config = Config()

HISTORY_KEY = "chat_history"


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
        "📊 *Spending history* — yours only, not advertisers'\n\n"
        "Example commands:\n"
        "• `Book a hotel in London for 3 nights`\n"
        "• `Buy a gift for ~50 USDC`\n"
        "• `Send 10 USDC to address ABC...`\n"
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


# ─── Commands ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    wallet_mgr = WalletManager(user_id)

    if not wallet_mgr.has_wallet():
        wallet = wallet_mgr.create_wallet()
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
        "🔒 *Privacy:* All transfers go through Private Ephemeral Rollup (PER) by MagicBlock.\n\n"
        "📊 *Spending history* is stored only locally.\n\n"
        "🧠 *AI:* GitHub Models (free inference)",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wallet_mgr = WalletManager(user_id)

    if not wallet_mgr.has_wallet():
        await update.message.reply_text("❌ Wallet not found. Use /start")
        return

    msg = await update.message.reply_text("⏳ Fetching balance...")
    client = MagicBlockClient(wallet_mgr, config)

    try:
        balances = await client.get_balance()
        pk = wallet_mgr.get_wallet_info()["public_key"]
        cluster = "devnet" if config.USE_DEVNET else "mainnet"
        explorer_url = balances.get(
            "explorer_url",
            f"https://explorer.solana.com/address/{pk}?cluster={cluster}"
        )
        demo_note = "\n\n⚠️ _Demo mode — API unavailable_" if balances.get("demo_mode") else ""

        faucet_note = ""
        if balances["solana_usdc"] == 0.0 and balances["private_usdc"] == 0.0 and config.USE_DEVNET:
            faucet_note = (
                "\n\n💡 *Balance is 0?* Get free devnet USDC:\n"
                "[spl\\-token\\-faucet\\.com](https://spl-token-faucet.com/?token-name=USDC)\n"
                f"_Your address:_ `{pk}`"
            )

        per_prefix = "\\~" if balances.get("per_estimated") else ""
        per_note = " _(estimated)_" if balances.get("per_estimated") else ""
        await msg.edit_text(
            f"💰 *Your Balance*\n\n"
            f"🌐 Solana \\(public\\): `{balances['solana_usdc']:.4f} USDC`\n"
            f"🔒 Private PER: `{per_prefix}{balances['private_usdc']:.4f} USDC`{per_note}\\n\\n"
            f"📍 Wallet:\n`{pk}`\n\n"
            f"🔍 [View on Solana Explorer]({explorer_url})"
            + demo_note + faucet_note,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True
        )
    except Exception as e:
        await msg.edit_text(f"⚠️ Error fetching balance: {str(e)}")


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

    if not wallet_mgr.has_wallet():
        await update.message.reply_text("❌ Wallet not found. Use /start")
        return

    info = wallet_mgr.get_wallet_info()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Copy address", callback_data="copy_address")],
        [InlineKeyboardButton("💾 Export private key", callback_data="export_key")],
    ])
    await update.message.reply_text(
        f"⚙️ *Wallet Management*\n\n"
        f"📍 Address:\n`{info['public_key']}`\n\n"
        f"🌐 Network: {'Solana Devnet' if config.USE_DEVNET else 'Solana Mainnet'}\n\n"
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
    await update.message.reply_text(
        f"🤖 *Agent ready* — {status}\n\n"
        "Tell me what to do:\n"
        "• `Book a hotel in Paris for 2 nights`\n"
        "• `Send 20 USDC to Alex`\n"
        "• `How much did I spend this month?`\n"
        "• `Deposit 5 USDC to private balance`",
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

    thinking_msg = await update.message.reply_text("🤔 Thinking...")

    try:
        storage = SpendingStorage(user_id)
        agent = ConsumerAgent(user_id=user_id, wallet_mgr=wallet_mgr, storage=storage)
        history = get_history(context)
        result = await agent.process(text, history)

        set_history(context, result.get("history", history))

        # Сохраняем pending_tx если агент запросил подтверждение
        if result.get("awaiting_confirmation") and result.get("pending_tx"):
            context.user_data["pending_tx"] = result["pending_tx"]

        await thinking_msg.edit_text(
            result["message"],
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=result.get("keyboard")
        )

    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        await thinking_msg.edit_text(f"⚠️ Agent error: {str(e)}\n\nTry rephrasing your request.")


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
            agent = ConsumerAgent(user_id=user_id, wallet_mgr=wallet_mgr, storage=storage)

            result = await agent.resume_after_confirmation(
                tool_call_id=pending["tool_call_id"],
                messages=pending["messages"],
                history=get_history(context)
            )

            # Очищаем после оплаты
            set_history(context, result.get("history", []))
            context.user_data.pop("pending_tx", None)

            await query.edit_message_text(
                result["message"],
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=result.get("keyboard")
            )

        except Exception as e:
            logger.error(f"Payment failed: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ *Payment Failed*\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN
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
