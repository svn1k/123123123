"""
🤖 Consumer Agent Bot
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

from config import Config
from agent import ConsumerAgent
from storage import SpendingStorage
from wallet import WalletManager

logging.basicConfig(level=logging.INFO)
config = Config()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text

    # Инициализация истории
    if 'history' not in context.user_data:
        context.user_data['history'] = []

    wallet_mgr = WalletManager(user_id)
    storage = SpendingStorage(user_id)
    agent = ConsumerAgent(user_id, wallet_mgr, storage)

    thinking = await update.message.reply_text("🤔...")
    
    try:
        # Передаем старую историю в агент
        result = await agent.process(text, chat_history=context.user_data['history'])
        
        # Сохраняем новую историю
        context.user_data['history'] = result.get("new_history", [])

        if result.get("awaiting_confirmation"):
            context.user_data["pending_tx"] = result.get("pending_tx_data")

        await thinking.edit_text(result["message"], parse_mode=ParseMode.MARKDOWN, reply_markup=result.get("keyboard"))
    except Exception as e:
        await thinking.edit_text(f"❌ Ошибка: {e}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(query.from_user.id)

    if data.startswith("confirm_tx:"):
        tx_data = context.user_data.get("pending_tx")
        if tx_data:
            # Тут выполняется реальный перевод через mb_client...
            # Если успешно:
            await query.edit_message_text(f"✅ Оплачено {tx_data['amount']} USDC! Память агента очищена для новой задачи.")
            
            # ОЧИСТКА КОНТЕКСТА ПОСЛЕ ОПЛАТЫ
            context.user_data['history'] = [] 
            context.user_data.pop("pending_tx", None)
        else:
            await query.edit_message_text("❌ Ошибка: Транзакция не найдена.")

    elif data == "cancel_tx":
        # При отмене контекст НЕ стираем, чтобы пользователь мог уточнить детали
        await query.edit_message_text("❌ Транзакция отменена. Вы можете продолжить обсуждение.")

# (Остальные хендлеры: start, balance и запуск main - без изменений)