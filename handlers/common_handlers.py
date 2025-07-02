from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
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
        from handlers.admin_handlers import admin_menu
        await admin_menu(update, context)
        return ConversationHandler.END
    
    # Проверяем, есть ли у пользователя привязанный аккаунт студента
    student = db.get_student_by_telegram_id(user_id)
    if student:
        from handlers.student_handlers import student_menu
        await student_menu(update, context)
        return ConversationHandler.END
    
    # Если пользователь не авторизован, показываем главное меню
    keyboard = [
        [InlineKeyboardButton("📚 Подготовка к экзаменам", callback_data="exam_preparation")],
        [InlineKeyboardButton("👤 Личный кабинет", callback_data="personal_cabinet")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "👋 Добро пожаловать в бот для подготовки к экзаменам!\n\n"
        "Выберите, что вас интересует:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=message, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def handle_exam_preparation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Подготовка к экзаменам'"""
    query = update.callback_query
    await query.answer()
    
    message = (
        "🚧 Раздел «Подготовка к экзаменам» скоро появится!\n\n"
        "А пока можешь подписаться на канал с разборами заданий, полезностями и мемами по информатике:\n"
        "👉 [Сырная информатика](https://t.me/cupteacher)\n\n"
        "💡 Следи за обновлениями — будет интересно!"
    )
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")
    return ConversationHandler.END

async def handle_personal_cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Личный кабинет'"""
    query = update.callback_query
    await query.answer()
    
    message = (
        "👤 Для входа в личный кабинет введите ваш персональный пароль.\n\n"
        "🔑 Если у вас его нет, вы всегда можете записаться на занятия к [Саше](https://t.me/ChashkaDurashka) — и получить свой доступ!\n\n"
        "👇 Просто введите пароль или нажмите «🔙 Назад», если передумали."
    )
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")
    from handlers.student_handlers import ENTER_PASSWORD
    return ENTER_PASSWORD

async def handle_back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Назад'"""
    query = update.callback_query
    await query.answer()
    
    # Возвращаемся к главному меню
    await handle_start(update, context)
    return ConversationHandler.END 