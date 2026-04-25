"""
🤖 Autonomous Consumer Agent Bot
Telegram bot with persistent conversation context.

Context lifecycle:
  - Created:  first message to agent
  - Grows:    every user/assistant exchange
  - Cleared:  only after a confirmed payment (or /clear command)
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
config = Config()

# context.user_data key for conversation history
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
        "• `Show my spending this week`\n"
        "• `Find the best flight to Dubai`\n\n"
        "💡 _Just write what you need_"
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_history(context: ContextTypes.DEFAULT_TYPE) -> list:
    return context.user_data.get(HISTORY_KEY, [])

def set_history(context: ContextTypes.DEFAULT_TYPE, history: list):
    context.user_data[HISTORY_KEY] = history

def clear_history(context: ContextTypes.DEFAULT_TYPE):
    context.user_data[HISTORY_KEY] = []


# ─── Command Handlers ─────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    wallet_mgr = WalletManager(user_id)

    if not wallet_mgr.has_wallet():
        wallet = wallet_mgr.create_wallet()
        await update.message.reply_text(
            f"\U0001f44b Welcome, *{user.first_name}*!\n\n"
            f"\U0001f195 New Solana wallet created:\n"
            f"`{wallet['public_key']}`\n\n"
            + agent_intro_text(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard()
        )
        # Seed phrase with spoiler via MessageEntity (no MarkdownV2 escaping needed)
        prefix = "\u26a0\ufe0f Save your seed phrase — tap to reveal:\n\n"
        suffix = "\n\n\U0001f512 Never share this with anyone. Delete this message after saving."
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
        "/send — Send USDC privately\n"
        "/history — Spending history\n"
        "/wallet — Wallet management\n"
        "/deposit — Deposit to Private PER\n"
        "/withdraw — Withdraw from PER to Solana\n"
        "/agent — Activate AI agent\n"
        "/clear — Clear conversation context\n\n"
        "🔒 *Privacy:*\n"
        "All transfers go through Private Ephemeral Rollup (PER) by MagicBlock.\n"
        "Transactions are encrypted inside TEE (Intel TDX). No on-chain link between sender and receiver.\n\n"
        "📊 *Spending history* is stored only locally on your device.\n\n"
        "🧠 *AI:* GitHub Models (free inference — just a GitHub PAT needed)",
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

    from magicblock import MagicBlockClient
    client = MagicBlockClient(wallet_mgr)

    try:
        balances = await client.get_balance()
        demo_note = "\n\n⚠️ _Demo mode — connect wallet for real balances_" if balances.get("demo_mode") else ""
        pk = wallet_mgr.get_wallet_info()["public_key"]
        await msg.edit_text(
            f"💰 *Your Balance*\n\n"
            f"🌐 Solana (public): `{balances['solana_usdc']:.4f} USDC`\n"
            f"🔒 Private PER: `{balances['private_usdc']:.4f} USDC`\n\n"
            f"📍 Wallet:\n`{pk}`"
            + demo_note,
            parse_mode=ParseMode.MARKDOWN
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
        [InlineKeyboardButton("🔄 Deposit to PER", callback_data="deposit_per")],
        [InlineKeyboardButton("⬆️ Withdraw from PER", callback_data="withdraw_per")],
    ])
    await update.message.reply_text(
        f"⚙️ *Wallet Management*\n\n"
        f"📍 Address:\n`{info['public_key']}`\n\n"
        f"🔒 PER status: {'✅ Active' if info.get('per_active') else '❌ Not connected'}\n"
        f"🌐 Network: {'Solana Devnet' if config.USE_DEVNET else 'Solana Mainnet'}\n\n"
        f"_Private key is encrypted and stored locally_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_history(context)
    await update.message.reply_text(
        "🗑 *Conversation context cleared.*\n\n"
        "Starting fresh — the agent no longer remembers previous messages.",
        parse_mode=ParseMode.MARKDOWN
    )


async def agent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = get_history(context)
    status = f"📝 {len(history)} messages in context" if history else "🆕 Fresh context"
    await update.message.reply_text(
        f"🤖 *Agent ready* — {status}\n\n"
        "Tell me what to do. I'll remember the context until a payment is made.\n\n"
        "Examples:\n"
        "• `Book a hotel in Paris for 2 nights`\n"
        "• `Send 20 USDC to Alex`\n"
        "• `How much did I spend this month?`\n"
        "• `Buy a Nintendo Switch`",
        parse_mode=ParseMode.MARKDOWN
    )


# ─── Main message handler ─────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.effective_user.id)

    # Keyboard shortcuts
    shortcuts = {
        "💬 Agent": agent_cmd,
        "💰 Balance": balance_cmd,
        "📤 Send": lambda u, c: u.message.reply_text("Send USDC — just tell the agent: `Send X USDC to <address>`", parse_mode=ParseMode.MARKDOWN),
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

        # Load persisted history and process
        history = get_history(context)
        result = await agent.process(text, history)

        # Save updated history
        set_history(context, result.get("history", history))

        await thinking_msg.edit_text(
            result["message"],
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=result.get("keyboard")
        )

        # Store pending tx data if awaiting confirmation
        if result.get("awaiting_confirmation"):
            context.user_data["pending_clear_on_confirm"] = result.get("clear_history_on_confirm", False)

    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        await thinking_msg.edit_text(f"⚠️ Agent error: {str(e)}\n\nTry rephrasing your request.")


# ─── Callback Handlers ────────────────────────────────────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the payment confirmation button (English version)."""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data

    if data == "pay_now":
        # Retrieve pending transaction data prepared by the Agent
        tx_data = context.user_data.get("pending_tx")
        if not tx_data:
            await query.edit_message_text(
                "⚠️ *Error:* Transaction data not found. Please try again.", 
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Initialize Wallet Manager and MagicBlock Client
        wm = WalletManager(user_id, config)
        mb = MagicBlockClient(wm, config)
        
        # Show processing status
        status_msg = await query.edit_message_text(
            "🔒 *Initializing private payment via MagicBlock PER...*", 
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Execute the real private transfer
            # No link between sender and receiver will be visible on the main chain
            result = await mb.private_transfer(
                recipient=tx_data["recipient"],
                amount=tx_data["amount"],
                memo=tx_data.get("details", "Private Agent Order")
            )

            # Success message
            await status_msg.edit_text(
                f"✅ *Payment Successful!*\n\n"
                f"💵 Amount: `{tx_data['amount']} USDC`\n"
                f"🛡️ Privacy: Confirmed in Private Rollup\n"
                f"🔗 TX ID: `{result.get('tx_id', 'hidden')[:16]}...`",
                parse_mode=ParseMode.MARKDOWN
            )

            # Clear conversation context and pending data after successful purchase
            context.user_data["history"] = []
            context.user_data["pending_tx"] = None

        except Exception as e:
            # Error handling (e.g. insufficient private balance)
            logger.error(f"Payment failed: {e}")
            await status_msg.edit_text(
                f"❌ *Payment Failed*\n\nReason: {str(e)}", 
                parse_mode=ParseMode.MARKDOWN
            )
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

    logger.info("🤖 Consumer Agent Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()