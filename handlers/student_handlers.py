from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from core.database import Database

# Состояния для ConversationHandler
ENTER_PASSWORD = 0
ENTER_DISPLAY_NAME = 1

# Временное хранилище пользовательских настроек
user_settings = {}

async def get_user_settings(user_id: int) -> dict:
    """Получает настройки пользователя или возвращает настройки по умолчанию"""
    if user_id not in user_settings:
        user_settings[user_id] = {
            "display_name": None,
            "greeting": None
        }
    return user_settings[user_id]

async def student_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню студента"""
    user_id = update.effective_user.id
    student = context.bot_data['db'].get_student_by_telegram_id(user_id)
    
    keyboard = [
        [
            InlineKeyboardButton("📚 Домашнее задание", callback_data="student_homework")
        ],
        [
            InlineKeyboardButton("📝 Конспекты", callback_data="student_notes")
        ],
        [
            InlineKeyboardButton("📅 Расписание", callback_data="student_schedule"),
            InlineKeyboardButton("🔗 Подключиться к занятию", callback_data="student_join_lesson")
        ],
        [
            InlineKeyboardButton("📄 Актуальный вариант", callback_data="student_current_variant")
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data="student_settings")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Используем отображаемое имя из базы данных
    display_name = student.display_name or student.name
    greeting = f"👋 Привет, {display_name}!"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=greeting,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=greeting,
            reply_markup=reply_markup
        )

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню настроек"""
    keyboard = [
        [
            InlineKeyboardButton("👤 Изменить отображаемое имя", callback_data="student_change_name")
        ],
        [
            InlineKeyboardButton("🔄 Сбросить настройки", callback_data="student_reset_settings")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="student_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text="⚙️ Настройки\nВыберите, что хотите изменить:",
        reply_markup=reply_markup
    )

async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод пароля"""
    db: Database = context.bot_data['db']
    password = update.message.text
    user_id = update.effective_user.id
    
    # Проверяем пароль
    student = db.get_student_by_password(password)
    if student:
        # Обновляем Telegram ID студента
        db.update_student_telegram_id(student.id, user_id)
        
        # Показываем меню студента
        await student_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ Неверный пароль. Пожалуйста, попробуйте еще раз или введите /cancel для отмены."
        )
        return ENTER_PASSWORD

async def handle_student_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None | int:
    """Обрабатывает действия студента"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "student_homework":
        await query.edit_message_text(
            text="📚 Раздел домашних заданий в разработке",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="student_back")
            ]])
        )
    elif query.data == "student_notes":
        await query.edit_message_text(
            text="📝 Раздел конспектов в разработке",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="student_back")
            ]])
        )
    elif query.data == "student_schedule":
        await query.edit_message_text(
            text="📅 Раздел расписания в разработке",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="student_back")
            ]])
        )
    elif query.data == "student_join_lesson":
        student = context.bot_data['db'].get_student_by_telegram_id(query.from_user.id)
        if student and student.lesson_link:
            await query.edit_message_text(
                text=f"🔗 Ссылка на ваше занятие:\n{student.lesson_link}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="student_back")
                ]])
            )
        else:
            await query.edit_message_text(
                text="⚠️ Ссылка на занятие не установлена. Обратитесь к администратору.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="student_back")
                ]])
            )
    elif query.data == "student_current_variant":
        await query.edit_message_text(
            text="📄 Раздел актуального варианта в разработке",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="student_back")
            ]])
        )
    elif query.data == "student_settings":
        await show_settings_menu(update, context)
    elif query.data == "student_change_name":
        await query.edit_message_text(
            text="👤 Введите новое отображаемое имя:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Отмена", callback_data="student_back_to_settings")
            ]])
        )
        return ENTER_DISPLAY_NAME
    elif query.data == "student_reset_settings":
        student = context.bot_data['db'].get_student_by_telegram_id(query.from_user.id)
        if student:
            context.bot_data['db'].reset_student_settings(student.id)
            await query.answer("✅ Настройки сброшены!")
        await student_menu(update, context)
    elif query.data == "student_back_to_settings":
        await show_settings_menu(update, context)
    elif query.data == "student_back":
        await student_menu(update, context)

async def handle_display_name_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает изменение отображаемого имени"""
    user_id = update.effective_user.id
    new_name = update.message.text
    
    student = context.bot_data['db'].get_student_by_telegram_id(user_id)
    if student:
        context.bot_data['db'].update_student_settings(student.id, display_name=new_name)
        
        # Отправляем подтверждение
        confirm_message = await update.message.reply_text("✅ Отображаемое имя успешно изменено!")
        
        # Показываем обновленное меню
        await student_menu(update, context)
        
        # Удаляем сообщение с подтверждением через 2 секунды
        import asyncio
        await asyncio.sleep(2)
        await confirm_message.delete()
    
    return ConversationHandler.END 