import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

from config import Config
from wallet import WalletManager
from agent import ConsumerAgent
from storage import SpendingStorage
from magicblock import MagicBlockClient

logging.basicConfig(level=logging.INFO)
config = Config()

def main_menu():
    return ReplyKeyboardMarkup([['💬 Агент', '💰 Баланс'], ['📋 История', '⚙️ Кошелёк']], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wm = WalletManager(update.effective_user.id)
    if not wm.has_wallet():
        w = wm.create_wallet()
        text = f"👋 Кошелёк создан!\nАдрес: `{w['public_key']}`"
    else:
        text = "👋 С возвращением! Я готов к вашим поручениям."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Кнопки меню
    if text == "💰 Баланс":
        b = await MagicBlockClient(WalletManager(user_id)).get_balance()
        return await update.message.reply_text(f"💳 Баланс: {b['total']} USDC")
    elif text == "📋 История":
        h = SpendingStorage(user_id).get_history()
        return await update.message.reply_text("История пуста" if not h else str(h))

    # Работа с ИИ-Агентом
    if 'history' not in context.user_data: context.user_data['history'] = []
    
    wait = await update.message.reply_text("🤔...")
    agent = ConsumerAgent(user_id, WalletManager(user_id), SpendingStorage(user_id))
    
    try:
        res = await agent.process(text, context.user_data['history'])
        context.user_data['history'] = res['history']

        kb = None
        if "confirm_data" in res:
            context.user_data['pending_tx'] = res['confirm_data']
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Подтвердить", callback_data="tx_ok"),
                InlineKeyboardButton("❌ Отмена", callback_data="tx_no")
            ]])

        await wait.edit_text(res['text'], parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception as e:
        await wait.edit_text(f"❌ Ошибка: {e}")

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "tx_ok":
        tx = context.user_data.get('pending_tx')
        if tx:
            # Оплата
            SpendingStorage(query.from_user.id).add_record("buy", tx['action'], tx['amount'])
            
            # СТИРАЕМ ИСТОРИЮ ПОСЛЕ ОПЛАТЫ
            context.user_data['history'] = [] 
            context.user_data.pop('pending_tx', None)
            
            await query.edit_message_text(f"✅ Успешно оплачено: {tx['amount']} USDC\nПамять очищена.")
    elif query.data == "tx_no":
        await query.edit_message_text("❌ Отменено. Контекст сохранен, можем продолжить.")

if __name__ == "__main__":
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling()