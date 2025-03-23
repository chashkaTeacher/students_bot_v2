from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from handlers.admin_handlers import admin_menu
from handlers.student_handlers import student_menu, ENTER_PASSWORD
from core.database import Database

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Универсальная функция обработки команды /start.
    Проверяет статус пользователя и направляет в соответствующее меню.
    """
    user_id = update.effective_user.id
    db: Database = context.bot_data['db']
    
    # Проверяем, является ли пользователь администратором
    if db.is_admin(user_id):
        await admin_menu(update, context)
        return ConversationHandler.END
    
    # Проверяем, есть ли у пользователя привязанный аккаунт студента
    student = db.get_student_by_telegram_id(user_id)
    if student:
        await student_menu(update, context)
        return ConversationHandler.END
    
    # Если пользователь не авторизован, просим ввести пароль
    message = (
        "👋 Добро пожаловать!\n\n"
        "Для входа введите пароль, который вам выдал администратор.\n"
        "Для отмены используйте команду /cancel"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=message)
    else:
        await update.message.reply_text(text=message)
    
    return ENTER_PASSWORD 