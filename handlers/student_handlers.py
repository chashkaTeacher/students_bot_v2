from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from core.database import Database, format_moscow_time
import os
import datetime
import pytz
from datetime import timedelta
from telegram.error import BadRequest
from handlers.common_handlers import handle_start
import logging

# Состояния для ConversationHandler
ENTER_PASSWORD = 0
ENTER_DISPLAY_NAME = 1

# Временное хранилище пользовательских настроек
user_settings = {}

temp_data = {}
EDIT_NAME = 1000
EDIT_LINK = 1001

RESCHEDULE_CHOOSE_LESSON, RESCHEDULE_CHOOSE_WEEK, RESCHEDULE_CHOOSE_DAY, RESCHEDULE_CHOOSE_TIME, RESCHEDULE_CONFIRM = range(5)

# Добавим универсальные словари для вложенных меню
student_menu_labels = {
    'back': {
        'classic': ('🔙', 'Назад'),
        'dark': ('🌑', 'Назад'),
        'cheese': ('🧀', 'Назад'),
        'cyber': ('⚡', 'Назад'),
        'games': ('🎮', 'Назад в лобби'),
        'anime': ('🍵', 'Назад в меню'),
        'jojo': ('🕺', 'Назад (Muda Muda)'),
    },
    'homework': {
        'classic': ('📚', 'Домашнее задание'),
        'dark': ('🛠', 'Задание из Тени'),
        'cheese': ('🧀', 'Задание на погрыз'),
        'cyber': ('🖥', 'КОД: Домашка'),
        'games': ('🎮', 'Журнал заданий'),
        'anime': ('🗾', '1000 лет боли в виде задач'),
        'jojo': ('☀️', 'Путь Хамона'),
    },
    'lesson': {
        'classic': ('🔗', 'Подключиться к занятию'),
        'dark': ('👁', 'Спиритический сеанс'),
        'cheese': ('🐾', 'Прыгнуть в урок'),
        'cyber': ('🛰', 'Подключиться [LIVE]'),
        'games': ('🕹', 'Зарегать катку'),
        'anime': ('📞', 'Звонок сенсею'),
        'jojo': ('🌈', 'Начать бизарное приключение'),
    },
    'notes': {
        'classic': ('📝', 'Конспекты'),
        'dark': ('📜', 'Свитки Знаний'),
        'cheese': ('💜', 'Шпаргалки'),
        'cyber': ('📁', 'Логи'),
        'games': ('📖', 'Лороведение'),
        'anime': ('📓', 'Хроники'),
        'jojo': ('📖', "Heaven's Door"),
    },
    'roadmap': {
        'classic': ('🗺️', 'Роадмап'),
        'dark': ('❄️', 'Шаги во Тьме'),
        'cheese': ('🧀', 'Сырная тропа'),
        'cyber': ('🛰', 'Протокол курса'),
        'games': ('💎', 'Гринд'),
        'anime': ('🗺️', 'Путь героя'),
        'jojo': ('⏳', 'To Be Continued'),
    },
    'schedule': {
        'classic': ('📅', 'Расписание'),
        'dark': ('⏳', 'Часы Судьбы'),
        'cheese': ('📅', 'Сырисание'),
        'cyber': ('⏱', 'Таймлайн'),
        'games': ('🎲', 'Ивенты'),
        'anime': ('🍵', 'Учёба и чай'),
        'jojo': ('🕰', 'Made in Heaven'),
    },
    'settings': {
        'classic': ('⚙️', 'Настройки'),
        'dark': ('🛡', 'Глубины Системы'),
        'cheese': ('🐱', 'Панель мышления'),
        'cyber': ('⚙️', 'Система ⚡'),
        'games': ('🛠', 'Меню билдов'),
        'anime': ('🤖', 'Меню Пилота EVA'),
        'jojo': ('🏢', 'Штаб фонда Спидвагона'),
    },
    'notifications': {
        'classic': ('🔔', 'Уведомления'),
        'dark': ('🧃', 'Зов Бездны'),
        'cheese': ('🧀', 'Пищалки'),
        'cyber': ('⚡', 'Сигналы'),
        'games': ('📜', 'Квесты'),
        'anime': ('😺', 'Ня!'),
        'jojo': ('💥', 'ORA! Alerts'),
    },
}

# Единый источник тем и названий для всех меню
THEME_EMOJIS = {
    "classic": {"homework": "📚", "lesson": "🔗", "notes": "📝", "schedule": "📅", "settings": "⚙️", "roadmap": "🗺️", "notifications": "🔔"},
    "dark": {"homework": "🛠", "lesson": "👁", "notes": "📜", "schedule": "⏳", "settings": "🛡", "roadmap": "❄️", "notifications": "🧃"},
    "cheese": {"homework": "🧀", "lesson": "🐾", "notes": "💜", "schedule": "📅", "settings": "🐱", "roadmap": "🧀", "notifications": "🧀"},
    "cyber": {"homework": "🖥", "lesson": "🛰", "notes": "📁", "schedule": "⏱", "settings": "⚙️", "roadmap": "🛰", "notifications": "⚡"}
}
THEME_NAMES = {
    "classic": {
        "homework": "Домашнее задание",
        "lesson": "Подключиться к занятию", 
        "notes": "Конспекты",
        "schedule": "Расписание",
        "settings": "Настройки",
        "roadmap": "Роадмап",
        "notifications": "Уведомления"
    },
    "dark": {
        "homework": "Задание из Тени",
        "lesson": "Спиритический сеанс",
        "notes": "Свитки Знаний", 
        "schedule": "Часы Судьбы",
        "settings": "Глубины Системы",
        "roadmap": "Шаги во Тьме",
        "notifications": "Зов Бездны"
    },
    "cheese": {
        "homework": "Задание на погрыз",
        "lesson": "Прыгнуть в урок",
        "notes": "Шпаргалки",
        "schedule": "Сырисание", 
        "settings": "Панель мышления",
        "roadmap": "Сырная тропа",
        "notifications": "Пищалки"
    },
    "cyber": {
        "homework": "КОД: Домашка",
        "lesson": "Подключиться [LIVE]",
        "notes": "Логи",
        "schedule": "Таймлайн",
        "settings": "Система ⚡",
        "roadmap": "Протокол курса",
        "notifications": "Сигналы"
    },
    "games": {
        "homework": "Журнал заданий",
        "lesson": "Зарегать катку",
        "notes": "Лороведение",
        "schedule": "Ивенты",
        "settings": "Меню билдов",
        "roadmap": "Гринд",
        "notifications": "Квесты"
    },
    "anime": {
        "homework": "1000 лет боли в виде задач",
        "lesson": "Звонок сенсею",
        "notes": "Хроники",
        "schedule": "Учёба и чай",
        "settings": "Меню Пилота EVA",
        "roadmap": "Путь героя",
        "notifications": "Ня!"
    },
    "jojo": {
        "homework": "Путь Хамона",
        "lesson": "Начать бизарное приключение",
        "notes": "Heaven's Door",
        "schedule": "Made in Heaven",
        "settings": "Штаб фонда Спидвагона",
        "roadmap": "To Be Continued",
        "notifications": "ORA! Alerts"
    }
}
THEME_AVATAR_NAMES = {
    "classic": {"title": "Выберите аватарку:", "back": "Назад"},
    "dark": {"title": "Выберите аватар:", "back": "Назад"},
    "cheese": {"title": "Выберите сырную аватарку:", "back": "Назад"},
    "cyber": {"title": "Выберите аватар профиля:", "back": "Назад"}
}
THEME_THEME_NAMES = {
    "classic": {"title": "Выберите тему оформления:", "back": "Назад"},
    "dark": {"title": "Выберите стиль оформления:", "back": "Назад"},
    "cheese": {"title": "Выберите сырную тему:", "back": "Назад"},
    "cyber": {"title": "Выберите конфигурацию интерфейса:", "back": "Назад"},
    "games": {"title": "Выберите геймерскую тему:", "back": "Назад в лобби"},
    "anime": {"title": "Выберите аниме-тему:", "back": "Назад в меню"},
    "jojo": {"title": "Выберите Jojo-тему:", "back": "Назад (Muda Muda)"},
}

THEME_SETTINGS_NAMES = {
    "classic": {
        "personalization": "Персонализация",
        "old_homework_show": "Показывать старые задания",
        "old_homework_hide": "Скрыть старые задания",
        "feedback": "Фидбек",
        "reset": "Сбросить настройки",
        "back": "Назад",
        "title": "Настройки"
    },
    "dark": {
        "personalization": "Кастомизация",
        "old_homework_show": "Отображать архив",
        "old_homework_hide": "Скрыть архив",
        "feedback": "Обратная связь",
        "reset": "Сброс параметров",
        "back": "Назад",
        "title": "Параметры"
    },
    "cheese": {
        "personalization": "Сырная персонализация",
        "old_homework_show": "Показывать старые сыры",
        "old_homework_hide": "Скрыть старые сыры",
        "feedback": "Сырный фидбек",
        "reset": "Сбросить сырные настройки",
        "back": "Назад",
        "title": "Сырные настройки"
    },
    "cyber": {
        "personalization": "Конфигурация профиля",
        "old_homework_show": "Отображать архивные данные",
        "old_homework_hide": "Скрыть архивные данные",
        "feedback": "Отчет об ошибках",
        "reset": "Сброс конфигурации",
        "back": "Назад",
        "title": "Конфигурация"
    }
}

THEME_PERSONALIZATION_NAMES = {
    "classic": {
        "change_name": "Изменить имя",
        "choose_avatar": "Выбрать аватарку",
        "choose_theme": "Сменить тему",
        "back": "Назад",
        "title": "Персонализация"
    },
    "dark": {
        "change_name": "Изменить никнейм",
        "choose_avatar": "Выбрать аватар",
        "choose_theme": "Сменить стиль",
        "back": "Назад",
        "title": "Кастомизация"
    },
    "cheese": {
        "change_name": "Изменить сырное имя",
        "choose_avatar": "Выбрать сырную аватарку",
        "choose_theme": "Сменить сырную тему",
        "back": "Назад",
        "title": "Сырная персонализация"
    },
    "cyber": {
        "change_name": "Изменить идентификатор",
        "choose_avatar": "Выбрать аватар профиля",
        "choose_theme": "Сменить конфигурацию",
        "back": "Назад",
        "title": "Конфигурация профиля"
    }
}

# Функция для получения тематизированной кнопки
def themed_button(label_key, theme, callback_data):
    emoji, text = student_menu_labels[label_key][theme]
    return InlineKeyboardButton(f"{emoji} {text}", callback_data=callback_data)

def require_student(func):
    async def wrapper(update, context, *args, **kwargs):
        db = context.bot_data['db']
        user_id = update.effective_user.id
        student = db.get_student_by_telegram_id(user_id)
        if not student:
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(
                    text="❌ Ваш аккаунт был удалён или не найден."
                )
            else:
                await update.message.reply_text("❌ Ваш аккаунт был удалён или не найден.")
            # ЛЕНИВЫЙ ИМПОРТ, чтобы избежать циклического импорта
            await handle_start(update, context)
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper

# Применяем декоратор к основным обработчикам меню ученика
@require_student
async def student_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню студента"""
    user_id = update.effective_user.id
    student = context.bot_data['db'].get_student_by_telegram_id(user_id)
    db = context.bot_data['db']
    unread_count = len(db.get_notifications(student.id, only_unread=True)) if student else 0
    
    # Используем отображаемое имя из базы данных
    display_name = student.display_name or student.name
    
    # Применяем аватарку и тему
    avatar_emoji = student.avatar_emoji or "👋"
    greeting = f"{avatar_emoji} Привет, {display_name}!"
    
    # Применяем тему к эмодзи в меню
    theme = student.theme or "classic"
    
    emojis = THEME_EMOJIS.get(theme, THEME_EMOJIS["classic"])
    names = THEME_NAMES.get(theme, THEME_NAMES["classic"])
    
    notif_text = f"{emojis['notifications']} {names['notifications']} ({unread_count})" if unread_count else f"{emojis['notifications']} {names['notifications']}"
    
    if student.exam_type.value == 'Школьная программа':
        keyboard = [
            [InlineKeyboardButton(f"{emojis['homework']} {names['homework']}", callback_data="student_homework")],
            [InlineKeyboardButton(f"{emojis['lesson']} {names['lesson']}", callback_data="student_join_lesson")],
            [InlineKeyboardButton(f"{emojis['notes']} {names['notes']}", callback_data="student_notes")],
            [
                InlineKeyboardButton(f"{emojis['schedule']} {names['schedule']}", callback_data="student_schedule"),
                InlineKeyboardButton(notif_text, callback_data="student_notifications")
            ],
            [InlineKeyboardButton(f"{emojis['settings']} {names['settings']}", callback_data="student_settings")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(f"{emojis['homework']} {names['homework']}", callback_data="student_homework_menu")],
            [InlineKeyboardButton(f"{emojis['lesson']} {names['lesson']}", callback_data="student_join_lesson")],
            [
                InlineKeyboardButton(f"{emojis['notes']} {names['notes']}", callback_data="student_notes"),
                InlineKeyboardButton(f"{emojis['roadmap']} {names['roadmap']}", callback_data="student_roadmap")
            ],
            [
                InlineKeyboardButton(f"{emojis['schedule']} {names['schedule']}", callback_data="student_schedule"),
                InlineKeyboardButton(notif_text, callback_data="student_notifications")
            ],
            [InlineKeyboardButton(f"{emojis['settings']} {names['settings']}", callback_data="student_settings")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        try:
            msg = await update.callback_query.edit_message_text(
                text=greeting,
                reply_markup=reply_markup
            )
            db.update_student_menu_message_id(student.id, msg.message_id)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass  # Игнорируем ошибку
            else:
                raise
    else:
        msg = await update.message.reply_text(
            text=greeting,
            reply_markup=reply_markup
        )
        db.update_student_menu_message_id(student.id, msg.message_id)

@require_student
async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню настроек"""
    user_id = update.effective_user.id
    student = context.bot_data['db'].get_student_by_telegram_id(user_id)
    
    # Применяем тему к названиям кнопок
    theme = student.theme or "classic"
    names = THEME_SETTINGS_NAMES.get(theme, THEME_SETTINGS_NAMES["classic"])
    show_old_text = f"👁️ {names['old_homework_hide']}" if student.show_old_homework else f"👁️ {names['old_homework_show']}"
    
    keyboard = [
        [InlineKeyboardButton(f"🎨 {names['personalization']}", callback_data="student_personalization")],
        [InlineKeyboardButton(show_old_text, callback_data="student_toggle_old_homework")],
        [InlineKeyboardButton(f"📝 {names['feedback']}", callback_data="student_feedback")],
        [InlineKeyboardButton(f"🔄 {names['reset']}", callback_data="student_reset_settings")],
        [InlineKeyboardButton(f"🔙 {names['back']}", callback_data="student_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text=f"⚙️ {names['title']}\nВыберите, что хотите изменить:",
        reply_markup=reply_markup
    )

@require_student
async def show_personalization_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает подменю персонализации"""
    user_id = update.effective_user.id
    student = context.bot_data['db'].get_student_by_telegram_id(user_id)
    
    # Применяем тему к названиям кнопок
    theme = student.theme or "classic"
    names = THEME_PERSONALIZATION_NAMES.get(theme, THEME_PERSONALIZATION_NAMES["classic"])
    
    keyboard = [
        [InlineKeyboardButton(f"👤 {names['change_name']}", callback_data="student_change_name")],
        [InlineKeyboardButton(f"🦊 {names['choose_avatar']}", callback_data="student_choose_avatar")],
        [InlineKeyboardButton(f"🌈 {names['choose_theme']}", callback_data="student_choose_theme")],
        [InlineKeyboardButton(f"🔙 {names['back']}", callback_data="student_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        text=f"🎨 {names['title']}\nВыберите, что хотите изменить:",
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
        # Получаем студента заново, чтобы декоратор увидел его
        student = db.get_student_by_telegram_id(user_id)
        from handlers.student_handlers import student_menu
        await student_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ Неверный пароль. Пожалуйста, попробуйте еще раз или введите /cancel для отмены."
        )
        return ENTER_PASSWORD

@require_student
async def handle_student_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None | int:
    query = update.callback_query
    if query.data == "student_feedback":
        msg = await query.edit_message_text(
            "✉️ Напишите ваше пожелание, замечание или баг одним сообщением.\n\nЕсли не хотите отправлять сообщение, нажмите 'Назад'.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="student_settings")]
            ])
        )
        context.user_data['awaiting_feedback'] = True
        context.user_data['feedback_menu_msg_id'] = msg.message_id
        return
    try:
        await query.answer()
    except Exception as e:
        pass
    db: Database = context.bot_data['db']
    user_id = query.from_user.id
    student = db.get_student_by_telegram_id(user_id)
    


    if query.data == "student_personalization":
        await show_personalization_menu(update, context)
        return
    elif query.data == "student_choose_avatar":
        await show_avatar_menu(update, context)
        return
    elif query.data == "student_choose_theme":
        await show_theme_menu(update, context)
        return
    elif query.data.startswith("set_avatar_"):
        emoji = query.data.replace("set_avatar_", "")
        db.set_student_avatar(student.id, emoji)
        await query.edit_message_text(
            f"Аватарка {emoji} успешно выбрана!", 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Персонализация", callback_data="student_personalization")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="student_back")]
            ])
        )
        return
    elif query.data.startswith("set_theme_"):
        theme = query.data.replace("set_theme_", "")
        db.set_student_theme(student.id, theme)
        theme_names = THEME_THEME_NAMES.get(theme, THEME_THEME_NAMES["classic"])
        await query.edit_message_text(
            f"Тема оформления {theme_names.get('title', theme)} успешно выбрана!", 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Персонализация", callback_data="student_personalization")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="student_back")]
            ])
        )
        return
    elif query.data == "student_homework":
        await show_student_homework_menu(update, context, student, page=int(context.user_data.get('homework_page', 0)))
        return
    elif query.data.startswith("student_hw_file_"):
        hw_id = int(query.data.split("_")[-1])
        hw = db.get_homework_by_id(hw_id)
        if not hw:
            await query.message.reply_text(f"❌ Задание не найдено (id={hw_id})")
        elif not hw.file_path:
            await query.message.reply_text(f"❌ У задания нет файла (id={hw_id})")
        else:
            # Используем относительный путь от корня проекта
            file_path = os.path.join(os.getcwd(), hw.file_path)
            if not os.path.exists(file_path):
                await query.message.reply_text(f"❌ Файл не найден: {hw.file_path}")
            else:
                # Сначала убираем меню (заменяем на "⏳ Отправка файла...")
                try:
                    await query.edit_message_text(text="⏳ Отправка файла...")
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        raise
                # Затем отправляем файл отдельным сообщением
                try:
                    await query.message.reply_document(document=file_path, caption=f"📝 {hw.title}")
                except Exception as e:
                    await query.message.reply_text(f"❌ Ошибка при отправке файла: {e}")
                # После файла возвращаем меню задания отдельным сообщением
                buttons = [[InlineKeyboardButton("Ссылка на задание", url=hw.link)]]
                if hw and hw.file_path:
                    buttons.append([InlineKeyboardButton("Скачать файл", callback_data=f"student_hw_file_{hw_id}")])
                buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_homework")])
                await query.message.reply_text(
                    text=f"📝 <b>{hw.title}</b>",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML
                )
        return
    elif query.data.startswith("student_hw_"):
        hw_id = int(query.data.split("_")[-1])
        hw = db.get_homework_by_id(hw_id)
        if not hw:
            await query.edit_message_text(
                text="❌ Задание не найдено.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_homework")]])
            )
            return
        
        # Определяем эмодзи по типу экзамена
        exam_emoji = {
            'ОГЭ': '📝',
            'ЕГЭ': '📚',
            'Школьная программа': '🏫',
        }
        emoji = exam_emoji.get(getattr(hw, 'exam_type', ''), '📖')
        
        # Формируем текст с красивым оформлением
        exam_type = getattr(hw, 'exam_type', '')
        exam_info = f"📝 Экзамен: {exam_type.value}\n" if exam_type else ""
        
        # Определяем, является ли это актуальным заданием
        homeworks_data = db.get_homeworks_for_student_with_filter(student.id, show_old=True)
        is_current = False
        if homeworks_data:
            # Сортируем по номеру задания (1, 2, 3, 11, 23...)
            homeworks_data.sort(key=lambda x: x[0].get_task_number())
            # Актуальным считается задание с самым большим номером
            is_current = homeworks_data[-1][0].id == hw_id
        
        # Статус задания
        status_text = "🆕 Актуальное задание" if is_current else "�� Пройденное задание"
        
        message_text = (
            f"{emoji} <b>{hw.title}</b>\n"
            f"{exam_info}"
            f"─────────────\n"
            f"{status_text}\n"
        )
        
        # Формируем кнопки для задания с эмодзи
        buttons = [[InlineKeyboardButton("🔗 Открыть онлайн", url=hw.link)]]
        if hw.file_path:
            buttons.append([InlineKeyboardButton("📎 Скачать файл", callback_data=f"student_hw_file_{hw_id}")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_homework")])
        
        try:
            await query.edit_message_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise
        return
    elif query.data == "student_notes":
        await show_student_notes_menu(update, context, student, page=int(context.user_data.get('notes_page', 0)))
        return
    elif query.data == "student_notes_prev":
        page = int(context.user_data.get('notes_page', 0))
        if page > 0:
            await show_student_notes_menu(update, context, student, page=page-1)
        else:
            await query.answer("Это первая страница")
        return
    elif query.data == "student_notes_next":
        student_notes = db.get_notes_for_student(student.id)
        page = int(context.user_data.get('notes_page', 0))
        per_page = 6  # Обновляем на 6, как в новой функции
        total = len(student_notes)
        max_page = (total + per_page - 1) // per_page - 1
        if page < max_page:
            await show_student_notes_menu(update, context, student, page=page+1)
        else:
            await query.answer("Это последняя страница")
        return
    elif query.data == "student_schedule":
        await show_student_schedule_menu(update, context, student)
    elif query.data == "student_reschedule":
        # Запускаем процесс переноса занятия
        await student_reschedule_menu(update, context)
        return RESCHEDULE_CHOOSE_LESSON
    elif query.data.startswith("reschedule_lesson_"):
        # Обработка выбора занятия для переноса
        await student_reschedule_start(update, context)
        return RESCHEDULE_CHOOSE_WEEK
    elif query.data.startswith("reschedule_week_"):
        # Обработка выбора недели
        await student_reschedule_choose_week(update, context)
        return RESCHEDULE_CHOOSE_DAY
    elif query.data.startswith("reschedule_day_"):
        # Обработка выбора дня
        await student_reschedule_choose_day(update, context)
        return RESCHEDULE_CHOOSE_TIME
    elif query.data.startswith("reschedule_time_"):
        # Обработка выбора времени
        await student_reschedule_choose_time(update, context)
        return RESCHEDULE_CHOOSE_TIME
    elif query.data == "reschedule_confirm":
        # Обработка подтверждения
        await student_reschedule_confirm(update, context)
        return ConversationHandler.END
    elif query.data == "student_menu":
        # Возврат в главное меню студента
        await student_menu(update, context)
        return
    elif query.data == "student_join_lesson":
        if student and student.lesson_link:
            # Получаем информацию о следующем занятии
            next_lesson = db.get_next_lesson(student.id)
            
            if next_lesson:
                next_date = format_moscow_time(next_lesson['date'], '%d.%m.%Y')
                lesson_text = (
                    f"📅 <b>Следующее занятие</b>\n\n"
                    f"🗓️ Дата: {next_date}\n"
                    f"📅 День: {next_lesson['day_name']}\n"
                    f"⏰ Время: {next_lesson['time']}\n"
                    f"⏱️ Длительность: {next_lesson['duration']} минут\n\n"
                    f"Нажмите кнопку ниже, чтобы подключиться к занятию:"
                )
            else:
                lesson_text = (
                    f"📅 <b>Подключение к занятию</b>\n\n"
                    f"🗓️ Дата: уточняется\n"
                    f"⏰ Время: уточняется\n\n"
                    f"Нажмите кнопку ниже, чтобы подключиться к занятию:"
                )
            
            await query.edit_message_text(
                text=lesson_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎥 Подключиться к занятию", url=student.lesson_link)],
                    [InlineKeyboardButton("🔙 Назад", callback_data="student_back")]
                ]),
                parse_mode=ParseMode.HTML
            )
        else:
            await query.edit_message_text(
                text="⚠️ Ссылка на занятие не установлена. Обратитесь к администратору.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="student_back")
                ]])
            )
    elif query.data == "student_current_variant":
        # Получаем актуальный вариант по экзамену ученика
        if not student or not student.exam_type:
            await query.edit_message_text(
                text="❌ Не удалось определить ваш тип экзамена. Обратитесь к администратору.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
            )
            return
        variant = db.get_latest_variant(student.exam_type)
        if not variant:
            await query.edit_message_text(
                text="📄 Актуальный вариант пока не выдан.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
            )
            return
        # Оформляем дату выдачи
        issued_date = format_moscow_time(variant.created_at, '%d.%m.%Y') if variant.created_at else "-"
        # Вычисляем ближайший следующий понедельник
        dt = variant.created_at or datetime.datetime.now()
        days_ahead = 0 if dt.weekday() == 0 else 7 - dt.weekday()
        next_monday = dt + datetime.timedelta(days=days_ahead)
        deadline = format_moscow_time(next_monday, '%d.%m.%Y')
        # Текст сообщения
        text = (
            "📄 <b>Актуальный вариант</b>\n\n"
            f"🗓️ Выдан: {issued_date}\n"
            f"⏰ Дедлайн: {deadline} (понедельник)\n\n"
            "Если возникнут вопросы — <a href=\"https://t.me/ChashkaDurashka\">пиши Саше</a>."
        )
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Открыть вариант", url=variant.link)],
                [InlineKeyboardButton("🔙 Назад", callback_data="student_back")]
            ]),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False
        )
        return
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
        if student:
            context.bot_data['db'].reset_student_settings(student.id)
            await query.answer("✅ Настройки сброшены!")
        await student_menu(update, context)
    elif query.data == "student_toggle_old_homework":
        if student:
            # Переключаем настройку
            new_setting = not student.show_old_homework
            context.bot_data['db'].update_student_show_old_homework(student.id, new_setting)
            
            # Показываем обновленное меню настроек
            await show_settings_menu(update, context)
            
            # Показываем уведомление
            status_text = "включен" if new_setting else "отключен"
            await query.answer(f"✅ Показ старых заданий {status_text}!")
        return
    elif query.data == "student_back_to_settings":
        await show_settings_menu(update, context)
    elif query.data == "student_back":
        await student_menu(update, context)
    elif query.data == "student_notifications":
        # Сброс страницы при открытии уведомлений
        context.user_data['notif_page'] = 0
        notifications = db.get_notifications(student.id)
        if not notifications:
            await query.edit_message_text(
                text="🔔 Нет новых уведомлений.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
            )
            return
        # Пагинация: показываем только 5 последних уведомлений
        page = int(context.user_data.get('notif_page', 0))
        per_page = 5
        total = len(notifications)
        max_page = (total + per_page - 1) // per_page - 1
        page_notifications = notifications[page * per_page:min(page * per_page + per_page, total)]
        notif_texts = []
        for i, notif in enumerate(page_notifications, 1):
            status = "🆕 " if not notif.is_read else "📋 "
            dt = format_moscow_time(notif.created_at)
            # Тип уведомления на кириллице с эмодзи
            if notif.type == 'homework':
                notif_type = "📚 Домашнее задание"
            elif notif.type == 'variant':
                notif_type = "📄 Вариант"
            elif notif.type == 'schedule':
                notif_type = "📅 Расписание"
            else:
                notif_type = "📢 Уведомление"
            
            # Форматируем текст уведомления
            text = f"<b>{status}{notif_type}</b>\n"
            text += f"📅 <i>{dt}</i>\n\n"
            text += f"📝 {notif.text}"
            
            if notif.link:
                text += f"\n🔗 <a href='{notif.link}'>Открыть ссылку</a>"
            
            # Добавляем разделитель между уведомлениями (кроме последнего)
            if i < len(page_notifications):
                text += "\n─────────────"
            
            notif_texts.append(text)
        
        text = "\n\n".join(notif_texts)
        db.mark_notifications_read(student.id)
        buttons = []
        
        # Показываем навигацию только если есть больше одной страницы
        if max_page > 0:
            nav_row = []
            if page > 0:
                nav_row.append(InlineKeyboardButton("◀️", callback_data="notif_prev"))
            nav_row.append(InlineKeyboardButton(f"{page+1}/{max_page+1}", callback_data="noop"))
            if page < max_page:
                nav_row.append(InlineKeyboardButton("▶️", callback_data="notif_next"))
            buttons.append(nav_row)
        
        buttons.append([InlineKeyboardButton("🗑️ Очистить все", callback_data="notif_clear")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_back")])
        
        # Красивый заголовок с информацией о страницах только если есть больше одной страницы
        header = f"🔔 <b>Ваши уведомления</b>\n"
        header += f"📊 Всего: {total}\n"
        header += "─────────────\n\n"
        
        await query.edit_message_text(
            text=header + text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    elif query.data == "notif_next":
        context.user_data['notif_page'] = context.user_data.get('notif_page', 0) + 1
        # Показываем уведомления с обновленной страницей
        notifications = db.get_notifications(student.id)
        if not notifications:
            await query.edit_message_text(
                text="🔔 Нет новых уведомлений.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
            )
            return
        # Пагинация: показываем только 5 последних уведомлений
        page = int(context.user_data.get('notif_page', 0))
        per_page = 5
        total = len(notifications)
        max_page = (total + per_page - 1) // per_page - 1
        page_notifications = notifications[page * per_page:min(page * per_page + per_page, total)]
        notif_texts = []
        for i, notif in enumerate(page_notifications, 1):
            status = "🆕 " if not notif.is_read else "📋 "
            dt = format_moscow_time(notif.created_at)
            # Тип уведомления на кириллице с эмодзи
            if notif.type == 'homework':
                notif_type = "📚 Домашнее задание"
            elif notif.type == 'variant':
                notif_type = "📄 Вариант"
            elif notif.type == 'schedule':
                notif_type = "📅 Расписание"
            else:
                notif_type = "📢 Уведомление"
            
            # Форматируем текст уведомления
            text = f"<b>{status}{notif_type}</b>\n"
            text += f"📅 <i>{dt}</i>\n\n"
            text += f"📝 {notif.text}"
            
            if notif.link:
                text += f"\n🔗 <a href='{notif.link}'>Открыть ссылку</a>"
            
            # Добавляем разделитель между уведомлениями (кроме последнего)
            if i < len(page_notifications):
                text += "\n─────────────"
            
            notif_texts.append(text)
        
        text = "\n\n".join(notif_texts)
        db.mark_notifications_read(student.id)
        buttons = []
        
        # Показываем навигацию только если есть больше одной страницы
        if max_page > 0:
            nav_row = []
            if page > 0:
                nav_row.append(InlineKeyboardButton("◀️", callback_data="notif_prev"))
            nav_row.append(InlineKeyboardButton(f"{page+1}/{max_page+1}", callback_data="noop"))
            if page < max_page:
                nav_row.append(InlineKeyboardButton("▶️", callback_data="notif_next"))
            buttons.append(nav_row)
        
        buttons.append([InlineKeyboardButton("🗑️ Очистить все", callback_data="notif_clear")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_back")])
        
        # Красивый заголовок с информацией о страницах только если есть больше одной страницы
        header = f"🔔 <b>Ваши уведомления</b>\n"
        header += f"📊 Всего: {total}\n"
        header += "─────────────\n\n"
        
        await query.edit_message_text(
            text=header + text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    elif query.data == "notif_prev":
        context.user_data['notif_page'] = max(0, context.user_data.get('notif_page', 0) - 1)
        # Показываем уведомления с обновленной страницей
        notifications = db.get_notifications(student.id)
        if not notifications:
            await query.edit_message_text(
                text="🔔 Нет новых уведомлений.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
            )
            return
        # Пагинация: показываем только 5 последних уведомлений
        page = int(context.user_data.get('notif_page', 0))
        per_page = 5
        total = len(notifications)
        max_page = (total + per_page - 1) // per_page - 1
        page_notifications = notifications[page * per_page:min(page * per_page + per_page, total)]
        notif_texts = []
        for i, notif in enumerate(page_notifications, 1):
            status = "🆕 " if not notif.is_read else "📋 "
            dt = format_moscow_time(notif.created_at)
            # Тип уведомления на кириллице с эмодзи
            if notif.type == 'homework':
                notif_type = "📚 Домашнее задание"
            elif notif.type == 'variant':
                notif_type = "📄 Вариант"
            elif notif.type == 'schedule':
                notif_type = "📅 Расписание"
            else:
                notif_type = "📢 Уведомление"
            
            # Форматируем текст уведомления
            text = f"<b>{status}{notif_type}</b>\n"
            text += f"📅 <i>{dt}</i>\n\n"
            text += f"📝 {notif.text}"
            
            if notif.link:
                text += f"\n🔗 <a href='{notif.link}'>Открыть ссылку</a>"
            
            # Добавляем разделитель между уведомлениями (кроме последнего)
            if i < len(page_notifications):
                text += "\n─────────────"
            
            notif_texts.append(text)
        
        text = "\n\n".join(notif_texts)
        db.mark_notifications_read(student.id)
        buttons = []
        
        # Показываем навигацию только если есть больше одной страницы
        if max_page > 0:
            nav_row = []
            if page > 0:
                nav_row.append(InlineKeyboardButton("◀️", callback_data="notif_prev"))
            nav_row.append(InlineKeyboardButton(f"{page+1}/{max_page+1}", callback_data="noop"))
            if page < max_page:
                nav_row.append(InlineKeyboardButton("▶️", callback_data="notif_next"))
            buttons.append(nav_row)
        
        buttons.append([InlineKeyboardButton("🗑️ Очистить все", callback_data="notif_clear")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_back")])
        
        # Красивый заголовок с информацией о страницах только если есть больше одной страницы
        header = f"🔔 <b>Ваши уведомления</b>\n"
        header += f"📊 Всего: {total}\n"
        header += "─────────────\n\n"
        
        await query.edit_message_text(
            text=header + text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    elif query.data == "notif_clear":
        # Удаляем все уведомления через метод базы
        db.clear_notifications(student.id)
        # Удаляем все push-уведомления из чата
        push_msgs = db.get_push_messages(student.id)
        for push in push_msgs:
            try:
                await context.bot.delete_message(chat_id=student.telegram_id, message_id=push.message_id)
            except Exception:
                pass  # Игнорируем ошибки (например, если сообщение уже удалено)
        db.clear_push_messages(student.id)
        context.user_data['notif_page'] = 0
        await query.edit_message_text(
            text="🔔 Все уведомления удалены!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
        )
        return
    elif query.data.startswith("student_note_file_"):
        note_id = int(query.data.split("_")[-1])
        note = db.get_note_by_id(note_id)
        if not note:
            await query.message.reply_text(f"❌ Конспект не найден (id={note_id})")
        elif not note.file_path:
            await query.message.reply_text(f"❌ У конспекта нет файла (id={note_id})")
        else:
            # Используем относительный путь от корня проекта
            file_path = os.path.join(os.getcwd(), note.file_path)
            if not os.path.exists(file_path):
                await query.message.reply_text(f"❌ Файл не найден: {note.file_path}")
            else:
                # Сначала убираем меню (заменяем на "⏳ Отправка файла...")
                try:
                    await query.edit_message_text(text="⏳ Отправка файла...")
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        raise
                # Затем отправляем файл отдельным сообщением
                try:
                    await query.message.reply_document(document=file_path, caption=f"📚 {note.title}")
                except Exception as e:
                    await query.message.reply_text(f"❌ Ошибка при отправке файла: {e}")
                # После файла возвращаем меню конспекта отдельным сообщением
                buttons = [[InlineKeyboardButton("🔗 Открыть онлайн", url=note.link)]]
                if note and note.file_path:
                    buttons.append([InlineKeyboardButton("📎 Скачать файл", callback_data=f"student_note_file_{note_id}")])
                buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_notes")])
                await query.message.reply_text(
                    text=f"📚 <b>{note.title}</b>",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML
                )
        return
    elif query.data.startswith("student_note_"):
        note_id = int(query.data.split("_")[-1])
        note = db.get_note_by_id(note_id)
        if not note:
            await query.edit_message_text(
                text="❌ Конспект не найден.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_notes")]])
            )
            return
        
        # Определяем эмодзи по типу экзамена
        exam_emoji = {
            'ОГЭ': '📝',
            'ЕГЭ': '📚',
            'Школьная программа': '🏫',
        }
        emoji = exam_emoji.get(getattr(note, 'exam_type', ''), '📖')
        
        # Получаем номер задания, если есть
        task_number = note.get_task_number()
        task_info = f"#️⃣ Задание: №{task_number}\n" if task_number != float('inf') else ""
        
        # Формируем текст с красивым оформлением
        exam_type = getattr(note, 'exam_type', '')
        exam_info = f"📝 Экзамен: {exam_type.value}\n" if exam_type else ""
        
        message_text = (
            f"{emoji} <b>{note.title}</b>\n"
            f"{exam_info}"
            f"{task_info}"
            f"─────────────\n"
        )
        
        # Формируем кнопки для конспекта с эмодзи
        buttons = [[InlineKeyboardButton("🔗 Открыть онлайн", url=note.link)]]
        if note.file_path:
            buttons.append([InlineKeyboardButton("📎 Скачать файл", callback_data=f"student_note_file_{note_id}")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_notes")])
        
        try:
            await query.edit_message_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise
        return
    elif query.data == "student_homework_prev":
        page = int(context.user_data.get('homework_page', 0))
        if page > 0:
            await show_student_homework_menu(update, context, student, page=page-1)
        else:
            await query.answer("Это первая страница")
        return
    elif query.data == "student_homework_next":
        # Простая проверка страницы - логика уже в show_student_homework_menu
        page = int(context.user_data.get('homework_page', 0))
        await show_student_homework_menu(update, context, student, page=page+1)
        return
    elif query.data == "student_roadmap":
        # Показываем роадмап для текущего ученика
        await show_student_roadmap(update, context, student, page=int(context.user_data.get('roadmap_page', 0)))
        return
    elif query.data.startswith("roadmap_page_"):
        # Обработка навигации по страницам роадмапа
        page = int(query.data.split("_")[-1])
        context.user_data['roadmap_page'] = page
        await show_student_roadmap(update, context, student, page=page)
        return
    elif query.data == "student_homework_menu":
        buttons = [
            [InlineKeyboardButton("📋 Задачи", callback_data="student_homework")],
            [InlineKeyboardButton("📄 Актуальный вариант", callback_data="student_current_variant")],
            [InlineKeyboardButton("🔙 Назад", callback_data="student_back")]
        ]
        await query.edit_message_text(
            text="📚 Домашнее задание\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

@require_student
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

@require_student
async def show_student_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает меню управления учениками"""
    query = update.callback_query
    
    keyboard = [
        [
            InlineKeyboardButton("📝 Добавить ученика", callback_data="student_add"),
            InlineKeyboardButton("📋 Список учеников", callback_data="student_list")
        ],
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data="student_edit"),
            InlineKeyboardButton("❌ Удалить", callback_data="student_delete")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ]

@require_student
async def handle_student_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    
    try:
        await query.answer()
    except Exception as e:
        pass
    
    action, student_id = query.data.split("_")[1:]  # student_edit_123 -> ["student", "edit", "123"]
    
    if action == "edit":
        keyboard = [
            [
                InlineKeyboardButton("📝 Изменить имя", callback_data=f"student_edit_name_{student_id}"),
                InlineKeyboardButton("🔗 Изменить ссылку", callback_data=f"student_edit_link_{student_id}")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
        ]

@require_student
async def handle_student_edit_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор действия при редактировании"""
    query = update.callback_query
    
    try:
        await query.answer()
    except Exception as e:
        pass
    
    parts = query.data.split("_")  # student_edit_link_123 -> ["student", "edit", "link", "123"]
    action = parts[2]
    student_id = int(parts[3])
    
    user_id = update.effective_user.id
    if user_id not in temp_data:
        temp_data[user_id] = {}
    temp_data[user_id]["student_id"] = student_id
    
    db = Database()
    student = db.get_student_by_id(student_id)
    
    if action == "link":
        await query.edit_message_text(
            text=f"🔗 Введите новую ссылку для ученика:\n"
                 f"Текущая ссылка: {student.lesson_link}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
            ]])
        )
        return EDIT_LINK
    else:  # action == "name"
        await query.edit_message_text(
            text=f"📝 Введите новое имя для ученика:\n"
                 f"Текущее имя: {student.name}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
            ]])
        )
        return EDIT_NAME

@require_student
async def handle_student_link_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает изменение ссылки ученика"""
    user_id = update.effective_user.id
    if user_id not in temp_data or "student_id" not in temp_data[user_id]:
        await update.message.reply_text(
            text="❌ Ошибка: данные о студенте не найдены",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    student_id = temp_data[user_id]["student_id"]
    new_link = update.message.text
    
    db = Database()
    student = db.get_student_by_id(student_id)
    if not student:
        await update.message.reply_text(
            text="❌ Ошибка: ученик не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    # Обновляем ссылку в базе данных
    db.update_student_lesson_link(student_id, new_link)
    
    # Отправляем подтверждение
    await update.message.reply_text(
        text=f"✅ Ссылка успешно обновлена!\n\n"
             f"👤 Ученик: {student.name}\n"
             f"🔗 Новая ссылка: {new_link}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
        ]])
    )
    return ConversationHandler.END 

@require_student
async def send_student_menu_by_chat_id(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    db = context.bot_data['db']
    student = db.get_student_by_telegram_id(chat_id)
    if not student:
        return
    # Удаляем предыдущее меню, если оно есть
    last_menu_id = db.get_student_menu_message_id(student.id)
    if last_menu_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_menu_id)
        except Exception:
            pass
    unread_count = len(db.get_notifications(student.id, only_unread=True))
    display_name = student.display_name or student.name
    avatar_emoji = student.avatar_emoji or "👋"
    greeting = f"{avatar_emoji} Привет, {display_name}!"
    theme = student.theme or "classic"
    emojis = THEME_EMOJIS.get(theme, THEME_EMOJIS["classic"])
    names = THEME_NAMES.get(theme, THEME_NAMES["classic"])
    notif_text = f"{emojis['notifications']} {names['notifications']} ({unread_count})" if unread_count else f"{emojis['notifications']} {names['notifications']}"
    if student.exam_type.value == 'Школьная программа':
        keyboard = [
            [InlineKeyboardButton(f"{emojis['homework']} {names['homework']}", callback_data="student_homework")],
            [InlineKeyboardButton(f"{emojis['lesson']} {names['lesson']}", callback_data="student_join_lesson")],
            [InlineKeyboardButton(f"{emojis['notes']} {names['notes']}", callback_data="student_notes")],
            [
                InlineKeyboardButton(f"{emojis['schedule']} {names['schedule']}", callback_data="student_schedule"),
                InlineKeyboardButton(notif_text, callback_data="student_notifications")
            ],
            [InlineKeyboardButton(f"{emojis['settings']} {names['settings']}", callback_data="student_settings")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(f"{emojis['homework']} {names['homework']}", callback_data="student_homework_menu")],
            [InlineKeyboardButton(f"{emojis['lesson']} {names['lesson']}", callback_data="student_join_lesson")],
            [
                InlineKeyboardButton(f"{emojis['notes']} {names['notes']}", callback_data="student_notes"),
                InlineKeyboardButton(f"{emojis['roadmap']} {names['roadmap']}", callback_data="student_roadmap")
            ],
            [
                InlineKeyboardButton(f"{emojis['schedule']} {names['schedule']}", callback_data="student_schedule"),
                InlineKeyboardButton(notif_text, callback_data="student_notifications")
            ],
            [InlineKeyboardButton(f"{emojis['settings']} {names['settings']}", callback_data="student_settings")]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await context.bot.send_message(chat_id=chat_id, text=greeting, reply_markup=reply_markup)
    db.update_student_menu_message_id(student.id, msg.message_id)

@require_student
async def show_student_notes_menu(update, context, student, page=0):
    db = context.bot_data['db']
    theme = student.theme or 'classic'
    student_notes = db.get_notes_for_student(student.id)
    if not student_notes:
        await update.callback_query.edit_message_text(
            text=f"{student_menu_labels['notes'][theme][0]} У вас пока нет выданных конспектов.",
            reply_markup=InlineKeyboardMarkup([[themed_button('back', theme, 'student_back')]])
        )
        return
    per_page = 6  # 3 строки по 2 конспекта
    total = len(student_notes)
    max_page = (total + per_page - 1) // per_page - 1
    page = max(0, min(page, max_page))
    context.user_data['notes_page'] = page
    start = page * per_page
    end = start + per_page
    notes_on_page = student_notes[start:end]
    keyboard = []
    exam_emoji = {
        'ОГЭ': '📝',
        'ЕГЭ': '📚',
        'Школьная программа': '🏫',
    }
    for i in range(0, len(notes_on_page), 2):
        row = []
        for j in range(2):
            if i + j < len(notes_on_page):
                note = notes_on_page[i + j]
                # Определяем эмодзи по типу экзамена
                emoji = exam_emoji.get(getattr(note, 'exam_type', ''), '📖')
                # Краткое описание (первые 20 символов)
                short_descr = note.title[:20] + ('…' if len(note.title) > 20 else '')
                button_text = f"{emoji} {short_descr}"
                row.append(InlineKeyboardButton(button_text, callback_data=f"student_note_{note.id}"))
        if row:
            keyboard.append(row)
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️", callback_data="student_notes_prev"))
    nav_row.append(InlineKeyboardButton(f"{page+1}/{max_page+1}", callback_data="noop"))
    if page < max_page:
        nav_row.append(InlineKeyboardButton("▶️", callback_data="student_notes_next"))
    if len(nav_row) > 1:
        keyboard.append(nav_row)
    keyboard.append([themed_button('back', theme, 'student_back')])
    header = f"{student_menu_labels['notes'][theme][0]} <b>Ваши {student_menu_labels['notes'][theme][1].lower()}</b>\n"
    header += "─────────────\n"
    try:
        await update.callback_query.edit_message_text(
            text=header,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    except Exception as e:
        if "Message is not modified" not in str(e):
            raise

@require_student
async def show_student_homework_menu(update, context, student, page=0):
    db = context.bot_data['db']
    exam_type = student.exam_type
    
    # Получаем все задания студента с датами выдачи
    homeworks_data = db.get_homeworks_for_student_with_filter(student.id, show_old=True)
    
    if not homeworks_data:
        await update.callback_query.edit_message_text(
            text=f"{student_menu_labels['homework'][student.theme or 'classic'][0]} У вас пока нет выданных домашних заданий.",
            reply_markup=InlineKeyboardMarkup([[themed_button('back', student.theme or 'classic', 'student_back')]])
        )
        return
    
    # Сортируем по дате выдачи (самое новое первым)
    homeworks_data.sort(key=lambda x: x[1], reverse=True)
    
    # Новое задание — самое последнее по дате
    new_homework, new_assigned_at = homeworks_data[0]
    
    # Старые задания — все остальные, сортируем их по номеру
    old_homeworks_data = homeworks_data[1:]
    # Фильтруем по статусу: только 'пройдено' или 'в процессе'
    allowed_statuses = {'completed', 'Пройдено', 'in_progress', 'В процессе'}
    filtered_old_homeworks = []
    for homework, assigned_at in old_homeworks_data:
        # Получаем статус последнего назначения этого задания
        status = None
        with db.Session() as session:
            from core.database import StudentHomework
            shw = session.query(StudentHomework).filter_by(student_id=student.id, homework_id=homework.id).order_by(StudentHomework.assigned_at.desc()).first()
            if shw:
                status = shw.status
                logging.warning(f"[STUDENT] Фильтрация старых: student_id={student.id}, homework_id={homework.id}, status={status}")
        if status and status.strip() in allowed_statuses:
            filtered_old_homeworks.append((homework, assigned_at))
    old_homeworks_data = filtered_old_homeworks
    old_homeworks_data.sort(key=lambda x: x[0].get_task_number())
    
    # Если скрывать старые задания — не показываем их
    if not student.show_old_homework:
        old_homeworks_data = []
    
    # Пагинация для старых заданий
    per_page = 4
    total = len(old_homeworks_data)
    max_page = (total + per_page - 1) // per_page - 1 if total > 0 else 0
    page = max(0, min(page, max_page))
    context.user_data['homework_page'] = page
    start = page * per_page
    end = start + per_page
    homeworks_on_page = old_homeworks_data[start:end]
    
    keyboard = []
    
    # Кнопки по 2 в строке для старых заданий
    for i in range(0, len(homeworks_on_page), 2):
        row = []
        for j in range(2):
            if i + j < len(homeworks_on_page):
                homework, assigned_at = homeworks_on_page[i + j]
                short_title = homework.title[:20] + ('…' if len(homework.title) > 20 else '')
                button_text = f"📚 {short_title}"
                row.append(InlineKeyboardButton(button_text, callback_data=f"student_hw_{homework.id}"))
        if row:
            keyboard.append(row)
    
    # Кнопки навигации
    nav_buttons = []
    if student.show_old_homework:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data="student_homework_prev"))
        nav_buttons.append(InlineKeyboardButton(f"{page+1}/{max_page+1}", callback_data="noop"))
        if end < total:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data="student_homework_next"))
        if nav_buttons:
            keyboard.append(nav_buttons)
    
    # Кнопка нового задания (после пагинации, перед кнопкой назад)
    if new_homework:
        short_title = new_homework.title[:40] + ('…' if len(new_homework.title) > 40 else '')
        keyboard.append([InlineKeyboardButton(f"🆕 {short_title}", callback_data=f"student_hw_{new_homework.id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="student_back")])
    
    # Формируем заголовок
    header = f"📚 <b>Ваши домашние задания</b>\n"
    header += "─────────────\n"
    
    await update.callback_query.edit_message_text(
        text=header,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

@require_student
async def show_student_roadmap(update, context, student, page=0):
    db = context.bot_data['db']
    theme = student.theme or 'classic'
    exam_type = student.exam_type
    exam_label = 'ЕГЭ' if exam_type.value == 'ЕГЭ' else 'ОГЭ'
    
    # --- Роадмап для ЕГЭ ---
    if exam_type.value == 'ЕГЭ':
        roadmap = [
            (1, '🖊️'), (4, '🖊️'), (11, '🖊️💻'), (7, '🖊️💻'), (10, '📝'), (3, '📊'), (18, '📊'), (22, '📊'),
            (9, '📊💻'), ('Python', '🐍'), (2, '🐍'), (15, '🐍'), (6, '🐍'), (14, '🐍'), (5, '🐍'), (12, '🐍'),
            (8, '🐍'), (13, '🐍'), (16, '🐍'), (23, '🐍'), ('19-21', '🖊️💻'), (25, '🐍'), (27, '🐍'), (24, '🐍'), (26, '📊💻')
        ]
        real_statuses = db.get_homework_status_for_student(student.id, exam_type)
        tasks = []
        primary_score = 0
        for num, emoji in roadmap:
            status = real_statuses.get(num)
            if status == 'completed' or status == 'Пройдено':
                status = 'Пройдено'
            elif status == 'in_progress' or status == 'В процессе':
                status = 'В процессе'
            else:
                status = 'Не пройдено'
            note_line = ''
            if status in ('Пройдено', 'В процессе'):
                notes = db.get_notes_by_exam(exam_type)
                note = next((n for n in notes if n.get_task_number() == num), None)
                if note:
                    note_line = f"└─ <a href='{note.link}'>Конспект</a>"
            if num in (26, 27):
                max_score = 2
            elif isinstance(num, int) and 1 <= num <= 25:
                max_score = 1
            else:
                max_score = 0
            if num == 'Python' or num == '19-21':
                title = f"{emoji} {num}"
            else:
                title = f"{emoji} Задание {num}"
            if status == 'Пройдено':
                primary_score += max_score
                status_emoji = '✅'
            elif status == 'В процессе':
                status_emoji = '🔄'
            else:
                status_emoji = '❌'
            status_text = f'{status} {status_emoji}'
            task_block = f"{title}\n"
            if note_line:
                task_block += note_line + "\n"
            task_block += f"└─ Статус: {status_text}"
            tasks.append(task_block)
        
        primary_to_test = {
            1: 7, 2: 14, 3: 20, 4: 27, 5: 34, 6: 40, 7: 43, 8: 46, 9: 48, 10: 51, 11: 54, 12: 56, 13: 59, 14: 62, 15: 64, 16: 67, 17: 70, 18: 72, 19: 75, 20: 78, 21: 80, 22: 83, 23: 85, 24: 88, 25: 90, 26: 93, 27: 95, 28: 98, 29: 100
        }
        test_score = primary_to_test.get(primary_score, 0)
        
        # Пагинация
        per_page = 5
        total_pages = (len(tasks) - 1) // per_page + 1
        start = page * per_page
        end = start + per_page
        page_tasks = tasks[start:end]
        tasks_text = "\n\n".join(page_tasks)
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"roadmap_page_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"roadmap_page_{page+1}"))
        
        progress_text = (
            f"<b>Роадмап подготовки:</b>\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>🏅 Первичный балл: {primary_score}</b>\n"
            f"<b>🎯 Тестовый балл: {test_score}</b>\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"{tasks_text}"
        )
        
    # --- Роадмап для ОГЭ ---
    elif exam_type.value == 'ОГЭ':
        roadmap = [
            (1, '🖊️'), (2, '🖊️'), (4, '🖊️'), (9, '🖊️'), (7, '🖊️'), (8, '🖊️'), (10, '🖊️'), (5, '🖊️'), (3, '🖊️'), (6, '🖊️'),
            (11, '📁'), (12, '📁'), ('13.1', '🗂️'), ('13.2', '🗂️'), (14, '🗂️'), (15, '🐍'), ('Python', '🐍'), (16, '🐍')
        ]
        real_statuses = db.get_homework_status_for_student(student.id, exam_type)
        tasks = []
        score = 0
        passed_13 = False
        for num, emoji in roadmap:
            status = real_statuses.get(num)
            if status == 'completed' or status == 'Пройдено':
                status = 'Пройдено'
            elif status == 'in_progress' or status == 'В процессе':
                status = 'В процессе'
            else:
                status = 'Не пройдено'
            note_line = ''
            if status in ('Пройдено', 'В процессе'):
                notes = db.get_notes_by_exam(exam_type)
                note = next((n for n in notes if n.get_task_number() == num), None)
                if note:
                    note_line = f"└─ <a href='{note.link}'>Конспект</a>"
            if num == 'Python':
                title = f"{emoji} Python"
                if status == 'Пройдено':
                    score += 2
            elif num in ('13.1', '13.2'):
                title = f"{emoji} Задание {num}"
                if status == 'Пройдено':
                    passed_13 = True
            elif num == 14:
                title = f"{emoji} Задание {num}"
                if status == 'Пройдено':
                    score += 3
            elif num in (15, 16):
                title = f"{emoji} Задание {num}"
                if status == 'Пройдено':
                    score += 2
            else:
                title = f"{emoji} Задание {num}"
                if status == 'Пройдено':
                    score += 1
            if status == 'Пройдено':
                status_emoji = '✅'
            elif status == 'В процессе':
                status_emoji = '🔄'
            else:
                status_emoji = '❌'
            status_text = f'{status} {status_emoji}'
            task_block = f"{title}\n"
            if note_line:
                task_block += note_line + "\n"
            task_block += f"└─ Статус: {status_text}"
            tasks.append(task_block)
        
        if passed_13:
            score += 2
        if score <= 4:
            grade = '2'
        elif score <= 10:
            grade = '3'
        elif score <= 16:
            grade = '4'
        else:
            grade = '5'
        
        # Пагинация
        per_page = 5
        total_pages = (len(tasks) - 1) // per_page + 1
        start = page * per_page
        end = start + per_page
        page_tasks = tasks[start:end]
        tasks_text = "\n\n".join(page_tasks)
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"roadmap_page_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"roadmap_page_{page+1}"))
        
        progress_text = (
            f"<b>Ваш роадмап подготовки:</b>\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>🏅 Текущий балл: {score}</b>\n"
            f"<b>📊 Оценка: {grade}</b>\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"{tasks_text}"
        )
    else:
        progress_text = "Роадмап доступен только для ОГЭ и ЕГЭ."
        nav_buttons = []
    
    # Формируем клавиатуру
    keyboard = []
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([themed_button('back', theme, 'student_back')])
    
    await update.callback_query.edit_message_text(
        text=progress_text,
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard)
    ) 

# --- Новый обработчик старта переноса ---
@require_student
async def student_reschedule_start(update, context):
    query = update.callback_query
    await query.answer()
    
    # Сохраняем ID занятия
    context.user_data['reschedule_schedule_id'] = int(query.data.split('_')[-1])
    
    # Показываем выбор недели
    buttons = [
        [InlineKeyboardButton("Текущая неделя", callback_data="reschedule_week_0")],
        [InlineKeyboardButton("Следующая неделя", callback_data="reschedule_week_1")],
        [InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")]
    ]
    
    await query.edit_message_text(
        text="На какую неделю перенести занятие?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return RESCHEDULE_CHOOSE_WEEK

@require_student
async def student_reschedule_choose_week(update, context):
    query = update.callback_query
    await query.answer()
    
    # Проверяем наличие schedule_id
    if 'reschedule_schedule_id' not in context.user_data:
        await query.edit_message_text(
            text="❌ Ошибка: не выбрано занятие для переноса. Попробуйте снова.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")]])
        )
        return ConversationHandler.END
    
    week_offset = int(query.data.split('_')[-1])
    context.user_data['reschedule_week_offset'] = week_offset
    
    # Получаем доступные дни для выбранной недели
    db = context.bot_data['db']
    schedule_id = context.user_data['reschedule_schedule_id']
    schedule = db.get_schedule_by_id(schedule_id)
    lesson_duration = schedule.duration
    
    # Определяем начало недели
    today = datetime.datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    
    # Получаем доступные дни недели
    days = db.get_available_days_for_week(datetime.datetime.combine(start_of_week, datetime.datetime.min.time()), lesson_duration)
    
    if not days:
        await query.edit_message_text(
            text="Нет доступных дней для переноса на выбранной неделе.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")]])
        )
        return ConversationHandler.END
    
    buttons = [[InlineKeyboardButton(f"{d['day_name']} {d['date'].strftime('%d.%m.%Y')}", callback_data=f"reschedule_day_{d['date'].weekday()}")] for d in days]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")])
    
    await query.edit_message_text(
        text="Выберите день для переноса:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return RESCHEDULE_CHOOSE_DAY

@require_student
async def student_reschedule_choose_day(update, context):
    query = update.callback_query
    await query.answer()
    
    # Проверяем наличие schedule_id
    if 'reschedule_schedule_id' not in context.user_data:
        await query.edit_message_text(
            text="❌ Ошибка: не выбрано занятие для переноса. Попробуйте снова.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")]])
        )
        return ConversationHandler.END
    
    day_of_week = int(query.data.split('_')[-1])
    week_offset = context.user_data.get('reschedule_week_offset', 0)
    
    # Вычисляем дату для выбранного дня недели
    today = datetime.datetime.now()
    target_date = today + timedelta(weeks=week_offset)
    
    # Находим ближайший выбранный день недели
    while target_date.weekday() != day_of_week:
        target_date += timedelta(days=1)
    
    context.user_data['reschedule_date'] = target_date
    
    # Получаем доступные слоты времени
    db = context.bot_data['db']
    schedule_id = context.user_data['reschedule_schedule_id']
    schedule = db.get_schedule_by_id(schedule_id)
    lesson_duration = schedule.duration
    slots = db.get_available_slots_for_day(target_date, lesson_duration)
    
    if not slots:
        await query.edit_message_text(
            text="Нет доступных слотов на выбранный день.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")]])
        )
        return ConversationHandler.END
    
    # Сбрасываем страницу для времени
    context.user_data['reschedule_time_page'] = 0
    
    # Пагинация слотов по 6 на страницу
    page = 0
    per_page = 6
    total = len(slots)
    max_page = (total + per_page - 1) // per_page - 1
    page_slots = slots[page * per_page:min(page * per_page + per_page, total)]
    slot_buttons = [[InlineKeyboardButton(slot['display'], callback_data=f"reschedule_time_{slot['time']}")] for slot in page_slots]
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data="reschedule_time_prev"))
    if page < max_page:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data="reschedule_time_next"))
    slot_buttons.append(nav_buttons)
    slot_buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")])
    await query.edit_message_text(
        text="Выберите время для переноса:",
        reply_markup=InlineKeyboardMarkup(slot_buttons)
    )
    return RESCHEDULE_CHOOSE_TIME

@require_student
async def student_reschedule_choose_time(update, context):
    query = update.callback_query
    await query.answer()
    
    # Проверяем наличие schedule_id
    if 'reschedule_schedule_id' not in context.user_data:
        await query.edit_message_text(
            text="❌ Ошибка: не выбрано занятие для переноса. Попробуйте снова.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")]])
        )
        return ConversationHandler.END
    
    # Обработка пагинации
    if query.data == "reschedule_time_prev":
        page = int(context.user_data.get('reschedule_time_page', 0))
        if page > 0:
            context.user_data['reschedule_time_page'] = page - 1
        # Показываем слоты с обновленной страницей
        date = context.user_data['reschedule_date']
        db = context.bot_data['db']
        schedule_id = context.user_data['reschedule_schedule_id']
        schedule = db.get_schedule_by_id(schedule_id)
        lesson_duration = schedule.duration
        slots = db.get_available_slots_for_day(date, lesson_duration)
        
        if not slots:
            await query.edit_message_text(
                text="Нет доступных слотов на выбранный день.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")]])
            )
            return ConversationHandler.END
        
        page = int(context.user_data.get('reschedule_time_page', 0))
        per_page = 6
        total = len(slots)
        max_page = (total + per_page - 1) // per_page - 1
        page_slots = slots[page * per_page:min(page * per_page + per_page, total)]
        slot_buttons = [[InlineKeyboardButton(slot['display'], callback_data=f"reschedule_time_{slot['time']}")] for slot in page_slots]
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data="reschedule_time_prev"))
        if page < max_page:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data="reschedule_time_next"))
        slot_buttons.append(nav_buttons)
        slot_buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")])
        await query.edit_message_text(
            text="Выберите время для переноса:",
            reply_markup=InlineKeyboardMarkup(slot_buttons)
        )
        return RESCHEDULE_CHOOSE_TIME
    
    elif query.data == "reschedule_time_next":
        page = int(context.user_data.get('reschedule_time_page', 0))
        context.user_data['reschedule_time_page'] = page + 1
        # Показываем слоты с обновленной страницей
        date = context.user_data['reschedule_date']
        db = context.bot_data['db']
        schedule_id = context.user_data['reschedule_schedule_id']
        schedule = db.get_schedule_by_id(schedule_id)
        lesson_duration = schedule.duration
        slots = db.get_available_slots_for_day(date, lesson_duration)
        
        if not slots:
            await query.edit_message_text(
                text="Нет доступных слотов на выбранный день.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")]])
            )
            return ConversationHandler.END
        
        page = int(context.user_data.get('reschedule_time_page', 0))
        per_page = 6
        total = len(slots)
        max_page = (total + per_page - 1) // per_page - 1
        page_slots = slots[page * per_page:min(page * per_page + per_page, total)]
        slot_buttons = [[InlineKeyboardButton(slot['display'], callback_data=f"reschedule_time_{slot['time']}")] for slot in page_slots]
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data="reschedule_time_prev"))
        if page < max_page:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data="reschedule_time_next"))
        slot_buttons.append(nav_buttons)
        slot_buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")])
        await query.edit_message_text(
            text="Выберите время для переноса:",
            reply_markup=InlineKeyboardMarkup(slot_buttons)
        )
        return RESCHEDULE_CHOOSE_TIME
    
    # Обработка выбора времени
    time_str = query.data.split('_')[-1]
    if ':' not in time_str:  # Это не время, а команда пагинации
        return RESCHEDULE_CHOOSE_TIME
    
    # Сохраняем выбранное время
    context.user_data['reschedule_time'] = time_str
    
    # Показываем подтверждение
    schedule_id = context.user_data['reschedule_schedule_id']
    db = context.bot_data['db']
    schedule = db.get_schedule_by_id(schedule_id)
    student = db.get_student_by_id(schedule.student_id)
    
    # Получаем информацию о текущем занятии
    days_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    current_day = days_ru[schedule.day_of_week]
    current_time = schedule.time
    current_duration = schedule.duration
    # Дата текущего занятия (берём ближайшую дату в будущем по дню недели)
    today = datetime.datetime.now().date()
    current_date = today + datetime.timedelta((schedule.day_of_week - today.weekday()) % 7)
    current_date_str = current_date.strftime('%d.%m.%Y')

    # Получаем информацию о новом времени
    new_date = context.user_data['reschedule_date']
    new_day = days_ru[new_date.weekday()]
    new_time = time_str
    new_date_str = new_date.strftime('%d.%m.%Y')

    confirmation_text = (
        f"📅 <b>Подтверждение переноса</b>\n\n"
        f"📚 <b>Текущее занятие:</b> {current_day}, {current_date_str} в {current_time}\n\n"
        f"🔄 <b>Новое время:</b> {new_day}, {new_date_str} в {new_time}\n\n"
        f"Подтверждаете перенос?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="reschedule_confirm")],
        [InlineKeyboardButton("❌ Отменить", callback_data="student_reschedule")]
    ]
    
    await query.edit_message_text(
        text=confirmation_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return RESCHEDULE_CONFIRM

@require_student
async def student_reschedule_confirm(update, context):
    query = update.callback_query
    await query.answer()
    
    # Проверяем наличие необходимых данных
    if 'reschedule_schedule_id' not in context.user_data:
        await query.edit_message_text(
            text="❌ Ошибка: не выбрано занятие для переноса. Попробуйте снова.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_reschedule")]])
        )
        return ConversationHandler.END
    
    if query.data == "reschedule_confirm":
        # Создаем запрос на перенос
        schedule_id = context.user_data['reschedule_schedule_id']
        new_date = context.user_data['reschedule_date']
        new_time = context.user_data['reschedule_time']
        
        db = context.bot_data['db']
        schedule = db.get_schedule_by_id(schedule_id)
        student = db.get_student_by_id(schedule.student_id)
        
        # Создаем запрос на перенос
        reschedule_request = db.create_reschedule_request(
            student_id=student.id,
            schedule_id=schedule_id,
            requested_date=new_date,
            requested_time=new_time,
            status='pending'
        )
        
        if reschedule_request:
            # Отправляем уведомление администратору
            admin_ids = db.get_admin_ids()
            for admin_id in admin_ids:
                try:
                    admin = db.get_admin_by_telegram_id(admin_id)
                    if admin:
                        days_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
                        today = datetime.datetime.now().date()
                        current_date_obj = today + datetime.timedelta((schedule.day_of_week - today.weekday()) % 7)
                        current_date_str = current_date_obj.strftime('%d.%m.%Y')
                        current_day_ru = days_ru[schedule.day_of_week]
                        new_day_ru = days_ru[new_date.weekday()]
                        new_date_str = new_date.strftime('%d.%m.%Y')
                        notification_text = (
                            f"👤 <b>Студент:</b> {student.name}\n\n"
                            f"📚 <b>Текущее занятие:</b> {current_day_ru}, {current_date_str} в {schedule.time}\n\n"
                            f"🔄 <b>Запрошенное время:</b> {new_day_ru}, {new_date_str} в {new_time}"
                        )
                        db.add_admin_notification(admin.id, 'reschedule', notification_text)
                    # 1. Push-уведомление
                    push_msg = await context.bot.send_message(
                        chat_id=admin_id,
                        text="🔔 Новый запрос на перенос занятия! Откройте меню для подробностей.",
                    )
                    # Сохраняем ID push-сообщения для возможности удаления
                    if admin:
                        db.add_admin_push_message(admin.id, push_msg.message_id)
                    # 2. Обновление меню администратора с актуальным счетчиком уведомлений
                    from handlers.admin_handlers import send_admin_menu_by_chat_id
                    await send_admin_menu_by_chat_id(context, admin_id)
                except Exception as e:
                    print(f"Ошибка отправки уведомления админу {admin_id}: {e}")
            # Подтверждаем студенту
            await query.edit_message_text(
                text="✅ Запрос на перенос отправлен! Ожидайте подтверждения от преподавателя.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Вернуться в меню", callback_data="student_menu")]])
            )
        else:
            await query.edit_message_text(
                text="❌ Ошибка при создании запроса на перенос. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Вернуться в меню", callback_data="student_menu")]])
            )
    else:
        # Отмена - возвращаемся к расписанию
        await show_student_schedule_menu(update, context)
        return ConversationHandler.END
    return ConversationHandler.END

@require_student
async def student_reschedule_send(update, context):
    # Эта функция больше не используется, логика перенесена в student_reschedule_confirm
    pass

@require_student
async def student_reschedule_menu(update, context):
    """Показывает меню переносов занятий"""
    query = update.callback_query
    await query.answer()
    
    # Очищаем данные предыдущего переноса
    reschedule_keys = ['reschedule_schedule_id', 'reschedule_week_offset', 'reschedule_date', 'reschedule_time', 'reschedule_time_page']
    for key in reschedule_keys:
        if key in context.user_data:
            del context.user_data[key]
    
    # Получаем студента из базы данных
    db = context.bot_data['db']
    user_id = query.from_user.id
    
    student = db.get_student_by_telegram_id(user_id)
    
    if not student:
        await query.edit_message_text(
            text="❌ Студент не найден в базе данных.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
        )
        return ConversationHandler.END
    
    schedules = db.get_student_schedule(student.id)
    
    if not schedules:
        await query.edit_message_text(
            text="❌ У вас нет занятий для переноса.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
        )
        return ConversationHandler.END
    
    # Выбор занятия
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    try:
        buttons = [[InlineKeyboardButton(f"{days[s.day_of_week]} {s.time}", callback_data=f"reschedule_lesson_{s.id}")] for s in schedules]
    except Exception as e:
        await query.edit_message_text(
            text=f"❌ Техническая ошибка при формировании меню переноса.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
        )
        return ConversationHandler.END
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_back")])
    
    await query.edit_message_text(
        text="Выберите занятие, которое хотите перенести:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return RESCHEDULE_CHOOSE_LESSON

@require_student
async def show_student_schedule_menu(update, context, student=None):
    """
    Показывает меню расписания ученика.
    Если student не передан, берётся из context.user_data['student'] или из базы данных.
    """
    # Очищаем данные предыдущего переноса
    reschedule_keys = ['reschedule_schedule_id', 'reschedule_week_offset', 'reschedule_date', 'reschedule_time', 'reschedule_time_page']
    for key in reschedule_keys:
        if key in context.user_data:
            del context.user_data[key]
    query = update.callback_query
    db = context.bot_data['db']
    if student is None:
        student = context.user_data.get('student')
        if student is None:
            # Если студент не найден в context, ищем по telegram_id
            user_id = query.from_user.id
            student = db.get_student_by_telegram_id(user_id)
            if student is None:
                await query.edit_message_text(
                    text="❌ Студент не найден в базе данных.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
                )
                return
    schedules = db.get_student_schedule(student.id)
    next_lesson = db.get_next_lesson(student.id)
    if not schedules:
        await query.edit_message_text(
            text="📅 <b>Ваше расписание</b>\n\n❌ Расписание не настроено.\n\nОбратитесь к администратору для настройки расписания.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]]),
            parse_mode=ParseMode.HTML
        )
        return
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    theme = student.theme or 'classic'
    schedule_text = "📅 <b>Ваше расписание</b>\n\n"
    for schedule in schedules:
        day_name = days[schedule.day_of_week]
        schedule_text += f"📅 <b>{day_name}</b> в {schedule.time}\n"
    if next_lesson:
        next_date = format_moscow_time(next_lesson['date'], '%d.%m.%Y')
        schedule_text += f"\n🎯 <b>Следующее занятие:</b>\n"
        schedule_text += f"📅 {next_lesson['day_name']}, {next_date}\n"
        schedule_text += f"⏰ Время: {next_lesson['time']}\n"
        schedule_text += f"⏱️ Длительность: {next_lesson['duration']} минут"
    buttons = [
        [InlineKeyboardButton(f"🔄 Перенести занятие", callback_data="student_reschedule")],
        [themed_button('back', theme, 'student_back')]
    ]
    await query.edit_message_text(
        text=schedule_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@require_student
async def show_avatar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора аватарки"""
    user_id = update.effective_user.id
    student = context.bot_data['db'].get_student_by_telegram_id(user_id)
    
    # Применяем тему к названиям
    theme = student.theme or "classic"
    names = THEME_AVATAR_NAMES.get(theme, THEME_AVATAR_NAMES["classic"])
    
    emoji_list = ["🦊", "🐼", "🦉", "🐧", "🦁", "🐸", "🐻", "🐨", "🐯", "🐰", "🦄", "🐙", "🐢", "🐥", "🦋"]
    keyboard = []
    row = []
    for i, emoji in enumerate(emoji_list, 1):
        row.append(InlineKeyboardButton(emoji, callback_data=f"set_avatar_{emoji}"))
        if i % 5 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(f"🔙 {names['back']}", callback_data="student_personalization")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        text=f"🦊 {names['title']}",
        reply_markup=reply_markup
    )

@require_student
async def show_theme_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора темы"""
    user_id = update.effective_user.id
    student = context.bot_data['db'].get_student_by_telegram_id(user_id)
    theme = student.theme or "classic"
    names = THEME_THEME_NAMES.get(theme, THEME_THEME_NAMES["classic"])
    themes = [
        ("🌞 Классика", "classic"),
        ("🌚 Тёмная", "dark"),
        ("🧀 Сырная", "cheese"),
        ("🤖 Киберпанк", "cyber"),
        ("🎮 Игры", "games"),
        ("🗾 Аниме", "anime"),
        ("🕺 Jojo", "jojo"),
    ]
    keyboard = []
    row = []
    for i, (name, code) in enumerate(themes, 1):
        row.append(InlineKeyboardButton(name, callback_data=f"set_theme_{code}"))
        if i % 2 == 0:  # Каждые 2 кнопки - новый ряд
            keyboard.append(row)
            row = []
    if row:  # Если остались кнопки в неполном ряду
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(f"🔙 {names['back']}", callback_data="student_personalization")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        text=f"🌈 {names['title']}",
        reply_markup=reply_markup
    )

@require_student
async def handle_student_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод фидбека"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "✉️ Напишите ваше пожелание, замечание или баг одним сообщением.\n\nЕсли не хотите отправлять сообщение, нажмите 'Назад'.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="student_settings")]
        ])
    )
    # Сохраняем флаг ожидания фидбека
    context.user_data['awaiting_feedback'] = True
    return

@require_student
async def handle_student_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('awaiting_feedback'):
        db = context.bot_data['db']
        student = db.get_student_by_telegram_id(update.effective_user.id)
        feedback = update.message.text
        # Получаем id админа (или список)
        admin_ids = db.get_admin_ids() if hasattr(db, 'get_admin_ids') else [db.get_admin_telegram_id()]
        for admin_id in admin_ids:
            admin = db.get_admin_by_telegram_id(admin_id) if hasattr(db, 'get_admin_by_telegram_id') else None
            if admin:
                notif_text = f"Фидбек от {student.name}:\n\n{feedback}"
                db.add_admin_notification(admin.id, 'feedback', notif_text)
                # Push-уведомление админу
                try:
                    msg = await context.bot.send_message(
                        chat_id=admin_id,
                        text="🔔 У вас новое уведомление! Откройте меню 'Уведомления'."
                    )
                    db.add_admin_push_message(admin.id, msg.message_id)
                    # Обновляем меню администратора под push-уведомлением
                    from handlers.admin_handlers import send_admin_menu_by_chat_id
                    await send_admin_menu_by_chat_id(context, admin_id)
                except Exception:
                    pass
        # Удаляем старое меню, если оно есть
        msg_id = context.user_data.pop('feedback_menu_msg_id', None)
        if msg_id:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            except Exception:
                pass
        await update.message.reply_text(
            "Спасибо за ваш фидбек! Он отправлен администратору.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В меню настроек", callback_data="student_settings")]
            ])
        )
        context.user_data['awaiting_feedback'] = False
        return
    # Если не ждем фидбека, ничего не делаем или обработка других текстов