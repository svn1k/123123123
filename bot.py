"""
🤖 Autonomous Consumer Agent Bot
Telegram bot powered by Claude AI + MagicBlock Private Payments API
- Книга, покупает, резервирует — автономно
- История трат хранится у вас, не у рекламодателей
"""

import asyncio
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes,
    filters
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

# Conversation states
AWAIT_WALLET_IMPORT, AWAIT_AMOUNT, AWAIT_RECIPIENT, AWAIT_CONFIRM = range(4)
AWAIT_BUDGET, AWAIT_TASK = range(4, 6)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💬 Агент"), KeyboardButton("💰 Баланс")],
        [KeyboardButton("📤 Перевести"), KeyboardButton("📋 История")],
        [KeyboardButton("⚙️ Кошелёк"), KeyboardButton("ℹ️ Помощь")],
    ], resize_keyboard=True)


def agent_intro():
    return (
        "🤖 *Autonomous Consumer Agent*\n\n"
        "Я ваш приватный ИИ-агент для покупок, бронирований и переводов.\n\n"
        "🔒 *Приватные платежи* через MagicBlock Private Ephemeral Rollup\n"
        "🧠 *Интеллект* от Claude AI (Anthropic)\n"
        "📊 *История трат* — только ваша, без рекламодателей\n\n"
        "Примеры команд:\n"
        "• `Забронируй отель в Москве на 3 ночи`\n"
        "• `Купи подарок другу за 50 USDC`\n"
        "• `Отправь 10 USDC на адрес ABC...`\n"
        "• `Покажи мои траты за неделю`\n"
        "• `Найди лучший рейс Москва — Дубай`\n\n"
        "💡 _Просто напишите что нужно сделать_"
    )


# ─── Command Handlers ─────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)

    storage = SpendingStorage(user_id)
    wallet_mgr = WalletManager(user_id)

    if not wallet_mgr.has_wallet():
        # First time — create wallet
        wallet = wallet_mgr.create_wallet()
        await update.message.reply_text(
            f"👋 Привет, *{user.first_name}*!\n\n"
            f"🆕 Создан новый кошелёк Solana:\n"
            f"`{wallet['public_key']}`\n\n"
            f"⚠️ *Сохраните секретную фразу:*\n"
            f"||`{wallet['mnemonic']}`||\n\n"
            f"_(нажмите чтобы показать)_\n\n"
            + agent_intro(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard()
        )
    else:
        wallet = wallet_mgr.get_wallet_info()
        await update.message.reply_text(
            f"👋 Снова привет, *{user.first_name}*!\n\n"
            f"🔑 Ваш кошелёк: `{wallet['public_key'][:8]}...{wallet['public_key'][-6:]}`\n\n"
            + agent_intro(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard()
        )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Команды бота:*\n\n"
        "/start — Запустить бота\n"
        "/balance — Проверить баланс\n"
        "/send — Отправить USDC приватно\n"
        "/history — История трат\n"
        "/wallet — Управление кошельком\n"
        "/deposit — Пополнить Private PER\n"
        "/withdraw — Вывести на Solana\n"
        "/agent — Запустить ИИ-агента\n\n"
        "🔒 *О приватности:*\n"
        "Все переводы проходят через Private Ephemeral Rollup (PER) от MagicBlock.\n"
        "Транзакции зашифрованы в TEE (Intel TDX). Нет on-chain связи между отправителем и получателем.\n\n"
        "📊 *История:* хранится только локально у вас.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wallet_mgr = WalletManager(user_id)

    if not wallet_mgr.has_wallet():
        await update.message.reply_text("❌ Кошелёк не найден. Используйте /start")
        return

    msg = await update.message.reply_text("⏳ Проверяю баланс...")
    
    from magicblock import MagicBlockClient
    client = MagicBlockClient(wallet_mgr)
    
    try:
        balances = await client.get_balance()
        
        text = (
            f"💰 *Ваш баланс*\n\n"
            f"🌐 Solana (публично): `{balances['solana_usdc']:.2f} USDC`\n"
            f"🔒 Private PER: `{balances['private_usdc']:.2f} USDC`\n\n"
            f"📍 Кошелёк:\n`{wallet_mgr.get_wallet_info()['public_key']}`\n\n"
            f"_Баланс PER виден только вам_"
        )
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"⚠️ Ошибка получения баланса: {str(e)}")


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    storage = SpendingStorage(user_id)
    
    records = storage.get_history(limit=10)
    
    if not records:
        await update.message.reply_text(
            "📋 *История трат пуста*\n\n"
            "Ваша история трат хранится только на вашем устройстве.\n"
            "Начните использовать агента для покупок и переводов!",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    lines = ["📊 *Последние транзакции*\n_(только вы видите это)_\n"]
    total = 0.0
    
    for r in records:
        emoji = "📤" if r["type"] == "send" else "📥" if r["type"] == "receive" else "🛒"
        lines.append(
            f"{emoji} *{r['description']}*\n"
            f"   💵 {r['amount']:.2f} USDC | {r['date']}\n"
            f"   🏷 `{r.get('tx_id', 'приватно')[:16]}...`"
        )
        total += r["amount"] if r["type"] == "send" else 0
    
    lines.append(f"\n💸 Всего потрачено: *{total:.2f} USDC*")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Полная статистика", callback_data="stats_full")],
        [InlineKeyboardButton("🗑 Очистить историю", callback_data="clear_history")]
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
        await update.message.reply_text("❌ Кошелёк не найден. /start")
        return
    
    info = wallet_mgr.get_wallet_info()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Скопировать адрес", callback_data="copy_address")],
        [InlineKeyboardButton("💾 Экспорт приватного ключа", callback_data="export_key")],
        [InlineKeyboardButton("🔄 Пополнить PER", callback_data="deposit_per")],
        [InlineKeyboardButton("⬆️ Вывести из PER", callback_data="withdraw_per")],
    ])
    
    await update.message.reply_text(
        f"⚙️ *Управление кошельком*\n\n"
        f"📍 Адрес:\n`{info['public_key']}`\n\n"
        f"🔒 Статус PER: {'✅ Активен' if info.get('per_active') else '❌ Не подключён'}\n"
        f"🌐 Сеть: Solana Mainnet\n\n"
        f"_Приватный ключ хранится зашифрованно на устройстве_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


async def deposit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 *Пополнение Private PER*\n\n"
        "Отправьте сумму в USDC для делегирования в Private Ephemeral Rollup.\n"
        "После пополнения переводы будут полностью приватными.\n\n"
        "Введите сумму (например: `50`):",
        parse_mode=ParseMode.MARKDOWN
    )
    return AWAIT_AMOUNT


async def send_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📤 *Приватный перевод USDC*\n\n"
        "Укажите сумму для перевода:",
        parse_mode=ParseMode.MARKDOWN
    )
    return AWAIT_AMOUNT


# ─── Agent Handler ─────────────────────────────────────────────────────────────

async def agent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Агент активирован*\n\n"
        "Напишите задачу — я выполню её используя приватные платежи.\n\n"
        "Примеры:\n"
        "• `Забронируй отель в Питере на выходные`\n"
        "• `Купи Nintendo Switch в лучшем магазине`\n"
        "• `Отправь 20 USDC Алексу`\n"
        "• `Какой мой бюджет на еду в этом месяце?`",
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route keyboard buttons and natural language to agent."""
    text = update.message.text
    user_id = str(update.effective_user.id)

    # Keyboard shortcuts
    if text == "💬 Агент":
        return await agent_cmd(update, context)
    elif text == "💰 Баланс":
        return await balance_cmd(update, context)
    elif text == "📤 Перевести":
        return await send_cmd(update, context)
    elif text == "📋 История":
        return await history_cmd(update, context)
    elif text == "⚙️ Кошелёк":
        return await wallet_cmd(update, context)
    elif text == "ℹ️ Помощь":
        return await help_cmd(update, context)

    # Natural language → Claude Agent
    wallet_mgr = WalletManager(user_id)
    storage = SpendingStorage(user_id)

    if not wallet_mgr.has_wallet():
        await update.message.reply_text("❌ Сначала запустите /start")
        return

    thinking_msg = await update.message.reply_text("🤔 Думаю над задачей...")

    try:
        agent = ConsumerAgent(
            user_id=user_id,
            wallet_mgr=wallet_mgr,
            storage=storage
        )
        result = await agent.process(text)
        
        await thinking_msg.edit_text(
            result["message"],
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=result.get("keyboard")
        )
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        await thinking_msg.edit_text(
            f"⚠️ Ошибка агента: {str(e)}\n\nПопробуйте переформулировать запрос."
        )


# ─── Callback Handlers ────────────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data

    if data == "stats_full":
        storage = SpendingStorage(user_id)
        stats = storage.get_stats()
        await query.edit_message_text(
            f"📈 *Полная статистика*\n\n"
            f"💸 Всего отправлено: *{stats['total_sent']:.2f} USDC*\n"
            f"📥 Всего получено: *{stats['total_received']:.2f} USDC*\n"
            f"🛒 Покупок: *{stats['purchases']}*\n"
            f"🏨 Бронирований: *{stats['bookings']}*\n"
            f"📤 Переводов: *{stats['transfers']}*\n\n"
            f"📅 За 30 дней: *{stats['month_spent']:.2f} USDC*\n"
            f"📅 За 7 дней: *{stats['week_spent']:.2f} USDC*\n\n"
            f"_🔒 Эти данные хранятся только у вас_",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "clear_history":
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_clear"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_clear"),
        ]])
        await query.edit_message_text(
            "⚠️ *Подтверждение*\n\nУдалить всю историю трат?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

    elif data == "confirm_clear":
        SpendingStorage(user_id).clear_history()
        await query.edit_message_text("✅ История удалена.")

    elif data == "cancel_clear":
        await query.edit_message_text("❌ Отменено.")

    elif data == "export_key":
        wallet_mgr = WalletManager(user_id)
        info = wallet_mgr.get_wallet_info()
        await query.message.reply_text(
            f"🔑 *Приватный ключ (Base58):*\n\n"
            f"||`{info.get('private_key_b58', 'недоступно')}`||\n\n"
            f"⚠️ *Никому не передавайте этот ключ!*",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data.startswith("confirm_tx:"):
        # Agent-initiated transaction confirmation
        tx_data = context.user_data.get("pending_tx")
        if tx_data:
            from magicblock import MagicBlockClient
            wallet_mgr = WalletManager(user_id)
            client = MagicBlockClient(wallet_mgr)
            storage = SpendingStorage(user_id)
            
            msg = await query.edit_message_text("⏳ Выполняю транзакцию...")
            try:
                result = await client.private_transfer(
                    recipient=tx_data["recipient"],
                    amount=tx_data["amount"],
                    memo=tx_data.get("memo", "")
                )
                storage.add_record(
                    type=tx_data.get("record_type", "send"),
                    description=tx_data.get("description", "Перевод"),
                    amount=tx_data["amount"],
                    tx_id=result.get("tx_id", ""),
                    metadata=tx_data
                )
                await msg.edit_text(
                    f"✅ *Транзакция выполнена!*\n\n"
                    f"💵 Сумма: *{tx_data['amount']} USDC*\n"
                    f"📍 Получатель: `{tx_data['recipient'][:8]}...`\n"
                    f"🔒 TX ID: `{result.get('tx_id', 'приватно')[:16]}...`\n\n"
                    f"_Транзакция приватна — нет on-chain связи_",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                await msg.edit_text(f"❌ Ошибка: {str(e)}")
        else:
            await query.edit_message_text("❌ Данные транзакции не найдены.")

    elif data == "cancel_tx":
        context.user_data.pop("pending_tx", None)
        await query.edit_message_text("❌ Транзакция отменена.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    config = Config()
    
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("wallet", wallet_cmd))
    app.add_handler(CommandHandler("deposit", deposit_cmd))
    app.add_handler(CommandHandler("send", send_cmd))
    app.add_handler(CommandHandler("agent", agent_cmd))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    # Natural language fallback
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Consumer Agent Bot запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
