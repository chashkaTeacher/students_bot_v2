from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from core.database import Database, ExamType, PendingNoteAssignment, Schedule, Homework
from handlers.student_handlers import THEME_EMOJIS, THEME_NAMES
import os
import uuid
import json
import asyncio
from datetime import datetime, timedelta
import pytz
import logging

# Состояния для ConversationHandler
ENTER_NAME, CHOOSE_EXAM, ENTER_LINK, CONFIRM_DELETE, EDIT_NAME, EDIT_EXAM, EDIT_STUDENT_LINK, ADD_NOTE = range(8)

# Временное хранилище данных о новых студентах
student_data = {}
# Временное хранилище для удаления студента
delete_data = {}
# Временное хранилище для редактирования студента
edit_data = {}
# Временное хранилище для хранения ID студента при редактировании
temp_data = {}

GIVE_HOMEWORK_CHOOSE_EXAM, GIVE_HOMEWORK_CHOOSE_STUDENT, GIVE_HOMEWORK_CHOOSE_TASK = range(100, 103)

# Состояние для выбора статуса домашнего задания
GIVE_HOMEWORK_STATUS = 103

# Состояние для меню выдачи домашнего задания
GIVE_HOMEWORK_MENU = 99

# Новые состояния для школьной программы
SCHOOL_HOMEWORK_CHOICE, SCHOOL_HOMEWORK_TITLE, SCHOOL_HOMEWORK_LINK, SCHOOL_HOMEWORK_FILE, SCHOOL_NOTE_CHOICE, SCHOOL_NOTE_TITLE, SCHOOL_NOTE_LINK, SCHOOL_NOTE_FILE = range(104, 112)

give_homework_temp = {}

GIVE_VARIANT_CHOOSE_EXAM, GIVE_VARIANT_ENTER_LINK = 200, 201

give_variant_temp = {}

# Новые состояния для статистики
STATISTICS_CHOOSE_EXAM, STATISTICS_CHOOSE_STUDENT = 2000, 2001

EDIT_TASK_STATUS = 3000

def convert_status_from_db(status):
    """Преобразует статус из базы данных в отображаемый"""
    if status == "completed":
        return "Пройдено"
    elif status == "in_progress":
        return "В процессе"
    elif status == "not_passed":
        return "Не пройдено"
    else:
        return status

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> int:
    # Получаем количество непрочитанных уведомлений для админа
    db = context.bot_data['db']
    user_id = update.effective_user.id if hasattr(update, 'effective_user') else update.callback_query.from_user.id
    admin = db.get_admin_by_telegram_id(user_id)
    unread_count = 0
    if admin:
        unread_count = len(db.get_admin_notifications(admin.id, only_unread=True))
    
    notif_text = f"🔔 Уведомления ({unread_count})" if unread_count else "🔔 Уведомления"
    
    keyboard = [
        [
            InlineKeyboardButton("🎯 Выдать домашнее задание", callback_data="admin_give_homework")
        ],
        [
            InlineKeyboardButton("👥 Управление учениками", callback_data="admin_students"),
            InlineKeyboardButton("📚 Управление заданиями", callback_data="admin_homework")
        ],
        [
            InlineKeyboardButton("📝 Управление конспектами", callback_data="admin_notes"),
            InlineKeyboardButton("📅 Управление расписанием", callback_data="admin_schedule")
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(notif_text, callback_data="admin_notifications")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.edit_text(
            "🔑 Панель управления администратора\n"
            "Выберите раздел:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "🔑 Панель управления администратора\n"
            "Выберите раздел:",
            reply_markup=reply_markup
        )
    return ConversationHandler.END

async def students_menu(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> None:
    """Показать меню управления учениками"""
    keyboard = [
        [
            InlineKeyboardButton("📝 Добавить ученика", callback_data="admin_add_student"),
            InlineKeyboardButton("❌ Удалить ученика", callback_data="admin_delete")
        ],
        [
            InlineKeyboardButton("✏️ Внести изменения", callback_data="admin_edit"),
            InlineKeyboardButton("👥 Информация о учениках", callback_data="admin_students_info")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.message.edit_text(
        "👥 Управление учениками\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def notes_menu(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> None:
    """Показать меню управления конспектами"""
    keyboard = [
        [
            InlineKeyboardButton("📝 Добавить конспект", callback_data="admin_add_note"),
            InlineKeyboardButton("❌ Удалить конспект", callback_data="admin_delete_note")
        ],
        [
            InlineKeyboardButton("📚 Список конспектов", callback_data="admin_list_notes"),
            InlineKeyboardButton("✏️ Редактировать", callback_data="admin_edit_note")
        ],
        [
            InlineKeyboardButton("🔍 Проверить невыданные", callback_data="admin_check_unassigned_notes")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.message.edit_text(
        "📝 Управление конспектами\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> None:
    """Показать меню управления заданиями"""
    from handlers.homework_handlers import show_homework_menu
    await show_homework_menu(update, context)

async def start_add_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления студента"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not context.bot_data['db'].is_admin(user_id):
        await query.message.reply_text("⚠️ У вас нет прав для выполнения этой команды")
        return ConversationHandler.END
    
    await query.message.reply_text(
        "Введите имя и фамилию студента:"
    )
    return ENTER_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного имени"""
    name = update.message.text
    user_id = update.effective_user.id
    
    # Сохраняем имя во временное хранилище
    student_data[user_id] = {"name": name}
    
    # Показываем кнопки выбора экзамена
    keyboard = [
        [
            InlineKeyboardButton("📝 ОГЭ", callback_data="student_exam_OGE"),
            InlineKeyboardButton("🎓 ЕГЭ", callback_data="student_exam_EGE")
        ],
        [InlineKeyboardButton("📖 Школьная программа", callback_data="student_exam_SCHOOL")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        text="📚 Выберите тип экзамена:",
        reply_markup=reply_markup
    )
    
    return CHOOSE_EXAM

async def choose_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор экзамена"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_add":
        await admin_menu(update, context)
        return ConversationHandler.END
    
    user_id = query.from_user.id
    exam_type = query.data.split("_")[-1]  # Получаем тип экзамена (OGE/EGE/SCHOOL)
    
    # Сохраняем тип экзамена
    student_data[user_id]["exam_type"] = ExamType[exam_type]
    
    await query.message.edit_text(
        "Введите ссылку для подключения:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_add")
        ]])
    )
    return ENTER_LINK

async def enter_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылки на занятие"""
    link = update.message.text.strip()
    user_id = update.effective_user.id
    
    if user_id not in student_data:
        await update.message.reply_text("❌ Ошибка: данные о студенте не найдены. Начните сначала.")
        await admin_menu(update, context)
        return ConversationHandler.END
    
    # Валидация URL
    from core.database import is_valid_url
    if not is_valid_url(link):
        await update.message.reply_text(
            "❌ Неверный формат ссылки!\n\n"
            "Ссылка должна быть в формате:\n"
            "• https://example.com\n"
            "• http://example.com\n"
            "• https://t.me/username\n\n"
            "Попробуйте еще раз:"
        )
        return ENTER_LINK
    
    # Получаем все данные из временного хранилища
    student_info = student_data[user_id]
    
    try:
        # Создаем студента со всеми данными
        student_data_dict = context.bot_data['db'].create_student(
            name=student_info["name"],
            exam_type=student_info["exam_type"],
            lesson_link=link
        )
        
        await update.message.reply_text(
            f"✅ Студент успешно добавлен!\n\n"
            f"👤 Имя: {student_data_dict['name']}\n"
            f"📚 Экзамен: {student_data_dict['exam_type']}\n"
            f"🔗 Ссылка: {student_data_dict['lesson_link']}\n"
            f"🔑 Пароль для входа: `{student_data_dict['password']}`",
            parse_mode='Markdown'
        )
        
        # Очищаем временные данные
        del student_data[user_id]
        
        # Возвращаемся в меню администратора
        await admin_menu(update, context)
        
        return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Произошла ошибка при добавлении студента: {str(e)}\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )
        if user_id in student_data:
            del student_data[user_id]
        await admin_menu(update, context)
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена процесса добавления студента"""
    user_id = update.effective_user.id
    if user_id in student_data:
        del student_data[user_id]
    
    await update.message.reply_text("❌ Процесс добавления студента отменен.")
    
    # Возвращаемся в меню администратора
    await admin_menu(update, context)
    
    return ConversationHandler.END

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает действия администратора"""
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        pass
    # Логгирование всех callback_data
    logging.warning(f"[handle_admin_actions] callback_data: {query.data}")

    # --- ВАЖНО: сначала обрабатываем все edit_task_status... ---
    if query.data.startswith("edit_task_status_set_"):
        logging.warning(f"[handle_admin_actions] edit_task_status_set_ callback_data: {query.data}")
        parts = query.data.split("_")
        logging.warning(f"[handle_admin_actions] parts: {parts}")
        student_id = int(parts[4])
        task_num = json.loads(parts[5])
        status = parts[6]
        logging.warning(f"[handle_admin_actions] student_id: {student_id}, task_num: {task_num}, status: {status}")
        db = context.bot_data['db']
        student = db.get_student_by_id(student_id)
        status_map = {
            "completed": "Пройдено",
            "in_progress": "В процессе",
            "not_completed": "Не пройдено"
        }
        status_text = status_map.get(status, status)
        if student:
            # Найти Homework по номеру и exam_type
            session = db.Session()
            try:
                homeworks = session.query(Homework).filter(Homework.exam_type == student.exam_type).all()
                homework = next((hw for hw in homeworks if hw.get_task_number() == task_num), None)
                if not homework:
                    # Если не найдено — создаём виртуальное задание
                    title = f"Задание {task_num}"
                    link = ""
                    homework = Homework(title=title, link=link, exam_type=student.exam_type)
                    session.add(homework)
                    session.commit()
                    session.refresh(homework)  # Получаем id до закрытия сессии
                homework_id = homework.id
            finally:
                session.close()
            if homework:
                db.update_homework_status(student.id, homework_id, status)
                await query.edit_message_text(
                    f"Статус задания {task_num} успешно изменён на: {status_text}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Назад", callback_data=f"edit_task_status_{student_id}")]
                    ])
                )
            else:
                await query.edit_message_text(
                    f"❌ Не удалось создать задание с номером {task_num}.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Назад", callback_data=f"edit_task_status_{student_id}")]
                    ])
                )
        else:
            await query.edit_message_text(
                "❌ Студент не найден."
            )
        return EDIT_TASK_STATUS

    elif query.data.startswith("edit_task_select_"):
        logging.warning(f"[handle_admin_actions] edit_task_select_ callback_data: {query.data}")
        parts = query.data.split("_")
        logging.warning(f"[handle_admin_actions] parts: {parts}")
        student_id = int(parts[3])
        task_num = json.loads(parts[4])
        logging.warning(f"[handle_admin_actions] student_id: {student_id}, task_num: {task_num}")
        await show_task_status_menu(update, context, student_id, task_num)
        return EDIT_TASK_STATUS

    elif query.data.startswith("edit_task_status_"):
        logging.warning(f"[handle_admin_actions] edit_task_status_ callback_data: {query.data}")
        parts = query.data.split("_")
        logging.warning(f"[handle_admin_actions] parts: {parts}")
        student_id = int(parts[3])
        page = 0
        if len(parts) > 4 and parts[4] == "page":
            page = int(parts[5])
        logging.warning(f"[handle_admin_actions] student_id: {student_id}, page: {page}")
        db = context.bot_data['db']
        student = db.get_student_by_id(student_id)
        if not student:
            await query.message.edit_text("❌ Студент не найден!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_edit")]]))
            return EDIT_TASK_STATUS
        if student.exam_type.value == 'ЕГЭ':
            roadmap = [
                (1, '🖊️'), (4, '🖊️'), (11, '🖊️💻'), (7, '🖊️💻'), (10, '📝'), (3, '📊'), (18, '📊'), (22, '📊'),
                (9, '📊💻'), ('Python', '🐍'), (2, '🐍'), (15, '🐍'), (6, '🐍'), (14, '🐍'), (5, '🐍'), (12, '🐍'),
                (8, '🐍'), (13, '🐍'), (16, '🐍'), (23, '🐍'), ('19-21', '🖊️💻'), (25, '🐍'), (27, '🐍'), (24, '🐍'), (26, '📊💻')
            ]
        elif student.exam_type.value == 'ОГЭ':
            roadmap = [
                (1, '🖊️'), (2, '🖊️'), (4, '🖊️'), (9, '🖊️'), (7, '🖊️'), (8, '🖊️'), (10, '🖊️'), (5, '🖊️'), (3, '🖊️'), (6, '🖊️'),
                (11, '📁'), (12, '📁'), ('13.1', '🗂️'), ('13.2', '🗂️'), (14, '🗂️'), (15, '🐍'), ('Python', '🐍'), (16, '🐍')
            ]
        else:
            await query.message.edit_text("Для школьной программы изменение статусов недоступно.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"edit_student_{student_id}")]]))
            return EDIT_TASK_STATUS
        # Получаем статусы из базы
        statuses = db.get_homework_status_for_student(student_id, student.exam_type)
        per_page = 8
        total = len(roadmap)
        max_page = (total + per_page - 1) // per_page - 1
        page = max(0, min(page, max_page))
        start = page * per_page
        end = start + per_page
        roadmap_page = roadmap[start:end]
        keyboard = []
        for i in range(0, len(roadmap_page), 2):
            row = []
            for j in range(2):
                if i + j < len(roadmap_page):
                    num, emoji = roadmap_page[i + j]
                    status = statuses.get(num)
                    if status is None:
                        status = statuses.get(str(num))
                    if status is None:
                        status = "Не пройдено"
                    status = convert_status_from_db(status)
                    if status == "Пройдено":
                        status_emoji = "✅"
                    elif status == "В процессе":
                        status_emoji = "🔄"
                    else:
                        status_emoji = "❌"
                    button_text = f"Задание {num} {status_emoji}"
                    row.append(InlineKeyboardButton(button_text, callback_data=f"edit_task_select_{student_id}_{json.dumps(str(num))}_page_{page}"))
            keyboard.append(row)
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️", callback_data=f"edit_task_status_{student_id}_page_{page-1}"))
        nav_row.append(InlineKeyboardButton(f"{page+1}/{max_page+1}", callback_data="noop"))
        if page < max_page:
            nav_row.append(InlineKeyboardButton("▶️", callback_data=f"edit_task_status_{student_id}_page_{page+1}"))
        keyboard.append(nav_row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"edit_student_{student_id}")])
        await query.message.edit_text(
            f"Выберите задание для изменения статуса:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return EDIT_TASK_STATUS

    if query.data == "admin_stats":
        return await show_statistics_menu(update, context)
    elif query.data == "admin_schedule":
        await show_schedule_menu(update, context)
        return ConversationHandler.END
    elif query.data.startswith("schedule_exam_"):
        # Новый формат: schedule_exam_view, schedule_exam_add, etc.
        parts = query.data.split("_")
        if len(parts) >= 4:
            action = parts[2]  # view, add, edit, delete
            exam_type = parts[3]  # OGE, EGE, SCHOOL
            await show_schedule_student_selection(update, context, action, exam_type)
            return ConversationHandler.END
        else:
            # Старый формат для обратной совместимости
            action = parts[2]  # view, add, edit, delete
            await show_schedule_exam_selection(update, context, action)
            return ConversationHandler.END
    elif query.data.startswith("admin_view_schedule"):
        await show_schedule_exam_selection(update, context, "view")
        return ConversationHandler.END
    elif query.data.startswith("admin_add_schedule"):
        await show_schedule_exam_selection(update, context, "add")
        return ConversationHandler.END
    elif query.data.startswith("admin_edit_schedule"):
        await show_schedule_exam_selection(update, context, "edit")
        return ConversationHandler.END
    elif query.data.startswith("admin_delete_schedule"):
        await show_schedule_exam_selection(update, context, "delete")
        return ConversationHandler.END
    elif query.data.startswith("schedule_view_student_"):
        student_id = int(query.data.split("_")[-1])
        await show_student_schedule(update, context, student_id)
        return ConversationHandler.END
    elif query.data.startswith("schedule_add_student_"):
        student_id = int(query.data.split("_")[-1])
        return await show_add_schedule_form(update, context, student_id)
    elif query.data.startswith("schedule_edit_student_"):
        student_id = int(query.data.split("_")[-1])
        await show_schedule_edit_menu(update, context, student_id)
        return SCHEDULE_CHOOSE_DAY
    elif query.data.startswith("schedule_delete_student_"):
        student_id = int(query.data.split("_")[-1])
        await show_schedule_delete_menu(update, context, student_id)
        return SCHEDULE_CHOOSE_DAY
    elif query.data.startswith("schedule_day_"):
        day_of_week = int(query.data.split("_")[-1])
        context.user_data['schedule_day'] = day_of_week
        
        await query.edit_message_text(
            "⏰ Введите время занятия в формате ЧЧ:ММ (например, 14:30):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return SCHEDULE_ENTER_TIME
    elif query.data.startswith("schedule_duration_"):
        return await handle_schedule_duration(update, context)
    elif query.data.startswith("schedule_edit_"):
        schedule_id = int(query.data.split("_")[-1])
        await show_schedule_edit_form(update, context, schedule_id)
        return SCHEDULE_EDIT_DAY
    elif query.data.startswith("schedule_delete_"):
        schedule_id = int(query.data.split("_")[-1])
        await handle_schedule_delete(update, context, schedule_id)
        return ConversationHandler.END
    elif query.data == "edit_schedule_day":
        return await show_schedule_edit_day_form(update, context)
    elif query.data == "edit_schedule_time":
        return await show_schedule_edit_time_form(update, context)
    elif query.data == "edit_schedule_duration":
        return await show_schedule_edit_duration_form(update, context)
    elif query.data.startswith("edit_schedule_day_"):
        day_of_week = int(query.data.split("_")[-1])
        return await handle_schedule_edit_day(update, context, day_of_week)
    elif query.data.startswith("edit_schedule_duration_"):
        duration = int(query.data.split("_")[-1])
        return await handle_schedule_edit_duration(update, context, duration)
    
    # Обработчики настроек переносов
    elif query.data == "reschedule_settings":
        await show_reschedule_settings(update, context)
        return ConversationHandler.END
    elif query.data == "reschedule_settings_hours":
        await show_reschedule_hours_settings(update, context)
        return ConversationHandler.END
    elif query.data.startswith("reschedule_start_"):
        await show_reschedule_end_hours_settings(update, context)
        return ConversationHandler.END
    elif query.data.startswith("reschedule_end_"):
        await save_reschedule_hours(update, context)
        return ConversationHandler.END
    elif query.data == "reschedule_settings_days":
        await show_reschedule_days_settings(update, context)
        return ConversationHandler.END
    elif query.data.startswith("reschedule_day_"):
        await toggle_reschedule_day(update, context)
        return ConversationHandler.END
    elif query.data == "reschedule_settings_interval":
        await show_reschedule_interval_settings(update, context)
        return ConversationHandler.END
    elif query.data.startswith("reschedule_interval_"):
        await save_reschedule_interval(update, context)
        return ConversationHandler.END
    
    if query.data.startswith("edit_name_"):
        student_id = int(query.data.split("_")[-1])
        temp_data[update.effective_user.id] = {"student_id": student_id}
        
        db = context.bot_data['db']
        student = db.get_student_by_id(student_id)
        
        await query.edit_message_text(
            text=f"Введите новое имя для ученика:\nТекущее имя: {student.name}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_back")
            ]])
        )
        return EDIT_NAME
        
    elif query.data.startswith("edit_link_"):
        student_id = int(query.data.split("_")[-1])
        temp_data[update.effective_user.id] = {"student_id": student_id}
        
        db = context.bot_data['db']
        student = db.get_student_by_id(student_id)
        
        await query.edit_message_text(
            text=f"Введите новую ссылку для ученика:\nТекущая ссылка: {student.lesson_link}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_back")
            ]])
        )
        return EDIT_STUDENT_LINK

    if not context.bot_data['db'].is_admin(query.from_user.id):
        await query.message.edit_text("⚠️ У вас нет прав для выполнения этой команды")
        return ConversationHandler.END

    if query.data == "admin_students":
        await students_menu(update, context)
        return ConversationHandler.END
    elif query.data == "admin_give_homework":
        await give_homework_menu(update, context)
        return ConversationHandler.END
    elif query.data == "admin_give_homework_variant":
        await handle_give_homework_variant(update, context)
        return ConversationHandler.END
    elif query.data == "admin_notes":
        await notes_menu(update, context)
        return ConversationHandler.END
    elif query.data == "admin_check_unassigned_notes":
        await check_unassigned_notes(update, context)
        return ConversationHandler.END
    elif query.data == "admin_notifications":
        await show_admin_notifications(update, context)
        return ConversationHandler.END
    elif query.data in ["admin_notif_prev", "admin_notif_next", "admin_notif_clear"]:
        await handle_admin_notification_actions(update, context)
        return ConversationHandler.END
    elif query.data == "admin_homework":
        from handlers.homework_handlers import show_homework_menu
        await show_homework_menu(update, context)
        return ConversationHandler.END
    elif query.data == "admin_stats":
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "📊 Статистика пока недоступна",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    elif query.data == "admin_students_info":
        keyboard = [
            [
                InlineKeyboardButton("📝 ОГЭ", callback_data="info_type_OGE"),
                InlineKeyboardButton("🎓 ЕГЭ", callback_data="info_type_EGE")
            ],
            [
                InlineKeyboardButton("📖 Школьная программа", callback_data="info_type_SCHOOL")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_students")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "👥 Выберите тип экзамена для просмотра информации:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    elif query.data.startswith("info_type_"):
        exam_type = query.data.split("_")[2]
        students = context.bot_data['db'].get_students_by_exam_type(ExamType[exam_type])
        
        if not students:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_students_info")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                f"❌ Нет студентов, сдающих {ExamType[exam_type].value}!",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        keyboard = []
        for i in range(0, len(students), 2):
            row = []
            for j in range(2):
                if i + j < len(students):
                    student = students[i + j]
                    note_text = f" ({student.notes})" if student.notes else ""
                    row.append(InlineKeyboardButton(
                        f"👤 {student.name}{note_text}",
                        callback_data=f"student_info_{student.id}"
                    ))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_students_info")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"📚 Студенты, сдающие {ExamType[exam_type].value}:\n"
            "Выберите студента для просмотра подробной информации:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
        
    elif query.data.startswith("student_info_"):
        student_id = int(query.data.split("_")[2])
        student = context.bot_data['db'].get_student_by_id(student_id)
        
        if not student:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_students_info")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                "❌ Студент не найден!",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=f"info_type_{student.exam_type.name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Собираем данные для красивого вывода
        name = student.name or '—'
        exam = student.exam_type.value if student.exam_type else '—'
        telegram_id = student.telegram_id or '—'
        password = student.password or '—'
        lesson_link = student.lesson_link or ''
        lesson_link_block = f'<a href="{lesson_link}">Ссылка</a>' if lesson_link else '—'
        lesson_date = getattr(student, 'lesson_date', None) or '—'
        description = getattr(student, 'description', None) or '—'

        # Получаем актуальное домашнее задание
        db = context.bot_data['db']
        homeworks = db.get_homeworks_for_student_with_filter(student.id)
        if homeworks:
            hw = homeworks[-1][0]
            hw_link = hw.link or ''
            homework_block = f'<a href="{hw_link}">Ссылка</a>' if hw_link else '—'
        else:
            homework_block = '—'

        info_text = (
            f'<b>👤 Информация об ученике</b>\n'
            f'━━━━━━━━━━━━━━\n'
            f'📝 <b>Имя:</b> {name}\n'
            f'📚 <b>Экзамен:</b> {exam}\n'
            f'🆔 <b>Telegram ID:</b> {telegram_id}\n'
            f'🔑 <b>Пароль:</b> <code>{password}</code>\n'
            f'━━━━━━━━━━━━━━\n'
            f'🔗 <b>Ссылка на занятие:</b> {lesson_link_block}\n'
            f'📅 <b>Дата занятия:</b> {lesson_date}\n'
            f'📝 <b>Описание:</b> {description}\n'
            f'📋 <b>Домашнее задание:</b> {homework_block}'
        )
        await query.message.edit_text(
            info_text,
            reply_markup=reply_markup,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        return ConversationHandler.END
    elif query.data.startswith("delete_type_"):
        exam_type = query.data.split("_")[2]
        students = context.bot_data['db'].get_students_by_exam_type(ExamType[exam_type])
        
        if not students:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_delete")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                f"❌ Нет студентов, сдающих {ExamType[exam_type].value}!",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        keyboard = []
        for i in range(0, len(students), 2):
            row = []
            for j in range(2):
                if i + j < len(students):
                    student = students[i + j]
                    note_text = f" ({student.notes})" if student.notes else ""
                    row.append(InlineKeyboardButton(
                        f"❌ {student.name}{note_text}",
                        callback_data=f"delete_{student.id}"
                    ))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_delete")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"Студенты, сдающие {ExamType[exam_type].value}:\n"
            "Выберите студента для удаления:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
        
    elif query.data == "admin_delete":
        keyboard = [
            [
                InlineKeyboardButton("📝 ОГЭ", callback_data="delete_type_OGE"),
                InlineKeyboardButton("🎓 ЕГЭ", callback_data="delete_type_EGE")
            ],
            [
                InlineKeyboardButton("📖 Школьная программа", callback_data="delete_type_SCHOOL")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "Выберите тип экзамена для удаления студента:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
        
    elif query.data.startswith("delete_"):
        # Проверяем, является ли это удалением заметки
        if query.data.startswith("delete_note_"):
            student_id = int(query.data.split("_")[2])
            student = context.bot_data['db'].get_student_by_id(student_id)
            if student:
                if context.bot_data['db'].delete_student_note(student_id):
                    await query.answer("✅ Заметка успешно удалена!")
                else:
                    await query.answer("❌ Ошибка при удалении заметки")
                
                # Возвращаемся к меню редактирования студента
                await query.edit_message_text(
                    f"Выберите, что хотите изменить для студента {student.name}:",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("👤 Изменить имя", callback_data=f"edit_name_{student_id}"),
                            InlineKeyboardButton("📚 Изменить экзамен", callback_data=f"edit_exam_{student_id}")
                        ],
                        [
                            InlineKeyboardButton("🔗 Изменить ссылку", callback_data=f"edit_link_{student_id}"),
                            InlineKeyboardButton("📝 Добавить заметку", callback_data=f"add_note_{student_id}")
                        ],
                        [InlineKeyboardButton("🔙 Назад", callback_data=f"edit_type_{student.exam_type.name}")]
                    ])
                )
            else:
                await query.answer("❌ Студент не найден")
                await admin_menu(update, context)
            return ConversationHandler.END
        
        # Обработка удаления студента
        student_id = int(query.data.split("_")[1])
        student = context.bot_data['db'].get_student_by_id(student_id)
        if student:
            delete_data[query.from_user.id] = {"student_id": student_id, "exam_type": student.exam_type}
            keyboard = [
                [
                    InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_delete"),
                    InlineKeyboardButton("❌ Нет, отменить", callback_data="cancel_delete")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                f"⚠️ Вы уверены, что хотите удалить студента {student.name}?\n"
                f"Это действие нельзя отменить!",
                reply_markup=reply_markup
            )
            return CONFIRM_DELETE
        await query.message.edit_text("❌ Студент не найден!")
        await admin_menu(update, context)
        return ConversationHandler.END
        
    elif query.data == "confirm_delete":
        if query.from_user.id in delete_data:
            student_id = delete_data[query.from_user.id]["student_id"]
            context.bot_data['db'].delete_student(student_id)
            del delete_data[query.from_user.id]
            await query.answer("✅ Студент успешно удален!")
        await admin_menu(update, context)
        return ConversationHandler.END
        
    elif query.data == "cancel_delete":
        if query.from_user.id in delete_data:
            del delete_data[query.from_user.id]
            await query.answer("❌ Удаление отменено")
        await admin_menu(update, context)
        return ConversationHandler.END
    elif query.data == "admin_back":
        await admin_menu(update, context)
        return ConversationHandler.END
    
    elif query.data == "admin_edit":
        keyboard = [
            [
                InlineKeyboardButton("📝 ОГЭ", callback_data="edit_type_OGE"),
                InlineKeyboardButton("🎓 ЕГЭ", callback_data="edit_type_EGE")
            ],
            [
                InlineKeyboardButton("📖 Школьная программа", callback_data="edit_type_SCHOOL")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "Выберите тип экзамена для редактирования данных студента:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    elif query.data.startswith("edit_type_"):
        exam_type = query.data.split("_")[2]
        students = context.bot_data['db'].get_students_by_exam_type(ExamType[exam_type])
        
        if not students:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_edit")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                f"❌ Нет студентов, сдающих {ExamType[exam_type].value}!",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        keyboard = []
        for i in range(0, len(students), 2):
            row = []
            for j in range(2):
                if i + j < len(students):
                    student = students[i + j]
                    note_text = f" ({student.notes})" if student.notes else ""
                    row.append(InlineKeyboardButton(
                        f"✏️ {student.name}{note_text}",
                        callback_data=f"edit_student_{student.id}"
                    ))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_edit")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"Студенты, сдающие {ExamType[exam_type].value}:\n"
            "Выберите студента для редактирования:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    elif query.data.startswith("edit_student_"):
        student_id = int(query.data.split("_")[2])
        student = context.bot_data['db'].get_student_by_id(student_id)
        
        if not student:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_edit")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                "❌ Студент не найден!",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        keyboard = [
            [
                InlineKeyboardButton("👤 Изменить имя", callback_data=f"edit_name_{student_id}"),
                InlineKeyboardButton("🎓 Изменить экзамен", callback_data=f"edit_exam_{student_id}")
            ],
            [
                InlineKeyboardButton("🔗 Изменить ссылку", callback_data=f"edit_link_{student_id}"),
                InlineKeyboardButton("📝 Добавить заметку", callback_data=f"add_note_{student_id}")
            ],
            [
                InlineKeyboardButton("🗺️ Изменить статус задания", callback_data=f"edit_task_status_{student_id}")
            ]
        ]
        
        # Добавляем кнопку удаления заметки только если она есть
        if student.notes:
            keyboard.append([
                InlineKeyboardButton("❌ Удалить заметку", callback_data=f"delete_note_{student_id}")
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"edit_type_{student.exam_type.name}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"Выберите, что хотите изменить для студента {student.name}:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    elif query.data.startswith("edit_exam_"):
        student_id = int(query.data.split("_")[2])
        student = context.bot_data['db'].get_student_by_id(student_id)
        if student:
            edit_data[query.from_user.id] = {"student_id": student_id, "type": "exam"}
            await show_exam_buttons_edit(update, student_id)
            return EDIT_EXAM
        await admin_menu(update, context)
        return ConversationHandler.END

    elif query.data.startswith("add_note_"):
        student_id = int(query.data.split("_")[2])
        student = context.bot_data['db'].get_student_by_id(student_id)
        if student:
            edit_data[query.from_user.id] = {"student_id": student_id, "type": "note"}
            await query.message.edit_text(
                f"Введите заметку для студента {student.name}:"
            )
            return ADD_NOTE
        await admin_menu(update, context)
        return ConversationHandler.END

    elif query.data.startswith("delete_note_"):
        student_id = int(query.data.split("_")[2])
        student = context.bot_data['db'].get_student_by_id(student_id)
        if student:
            if context.bot_data['db'].delete_student_note(student_id):
                await query.answer("✅ Заметка успешно удалена!")
            else:
                await query.answer("❌ Ошибка при удалении заметки")
            
            # Возвращаемся к меню редактирования студента
            await query.edit_message_text(
                f"Выберите, что хотите изменить для студента {student.name}:",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("👤 Изменить имя", callback_data=f"edit_name_{student_id}"),
                        InlineKeyboardButton("�� Изменить экзамен", callback_data=f"edit_exam_{student_id}")
                    ],
                    [
                        InlineKeyboardButton("🔗 Изменить ссылку", callback_data=f"edit_link_{student_id}"),
                        InlineKeyboardButton("📝 Добавить заметку", callback_data=f"add_note_{student_id}")
                    ],
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"edit_type_{student.exam_type.name}")]
                ])
            )
        else:
            await query.answer("❌ Студент не найден")
            await admin_menu(update, context)
        return ConversationHandler.END

    # Обработчики для конспектов
    elif query.data.startswith("assign_unassigned_note_"):
        note_id = int(query.data.split("_")[-1])
        db = context.bot_data['db']
        note = db.get_note_by_id(note_id)
        if not note:
            await query.edit_message_text("❌ Конспект не найден.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_check_unassigned_notes")]]))
            return ConversationHandler.END
        matching_students = db.get_students_with_matching_homework(note)
        unassigned_students = [s for s in matching_students if not db.is_note_assigned_to_student(s.id, note.id)]
        if not unassigned_students:
            await query.edit_message_text("❌ Нет учеников для выдачи этого конспекта.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_check_unassigned_notes")]]))
            return ConversationHandler.END
        process_id = str(uuid.uuid4())
        db.add_pending_note_assignment_with_process(process_id, update.effective_user.id, note_id=note_id, step='choose_student')
        exam_type = note.exam_type.value if hasattr(note.exam_type, 'value') else str(note.exam_type)
        student_names = ', '.join([s.name for s in unassigned_students])
        homeworks = db.get_homework_by_exam(note.exam_type)
        hw_titles = ', '.join([hw.title for hw in homeworks if note.get_task_number() == hw.get_task_number()])
        if not hw_titles:
            hw_titles = 'Нет точных совпадений по номеру задания'
        message_text = (
            f"📚 <b>{note.title}</b>\n"
            f"Экзамен: <b>{exam_type}</b>\n"
            f"🔗 <a href='{note.link}'>Ссылка на конспект</a>\n\n"
            f"<b>Ученики, которым можно выдать:</b>\n{student_names}\n\n"
            f"<b>Подходит к заданиям:</b>\n{hw_titles}"
        )
        keyboard = []
        for i in range(0, len(unassigned_students), 2):
            row = []
            for j in range(2):
                if i + j < len(unassigned_students):
                    student = unassigned_students[i + j]
                    row.append(InlineKeyboardButton(student.name, callback_data=f"assign_note_to_student_{process_id}_{student.id}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_check_unassigned_notes")])
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML',
            disable_web_page_preview=False
        )
        return ConversationHandler.END

    elif query.data.startswith("assign_note_to_student_"):
        parts = query.data.split("_")
        process_id = parts[-2]
        student_id = int(parts[-1])
        user_id = update.effective_user.id
        db = context.bot_data['db']
        db.update_pending_note_assignment(process_id, student_id=student_id, step='choose_note')
        pending = db.get_pending_note_assignment_by_process(process_id)
        note_id = pending.note_id
        exam_type = db.get_student_by_id(student_id).exam_type
        available_notes = db.get_notes_by_exam(exam_type)
        if not available_notes:
            await query.edit_message_text("❌ Нет доступных конспектов для этого типа экзамена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_check_unassigned_notes")]]))
            db.delete_pending_note_assignment_by_process(process_id)
            return ConversationHandler.END
        keyboard = []
        for i in range(0, len(available_notes), 2):
            row = []
            for j in range(2):
                if i + j < len(available_notes):
                    note = available_notes[i + j]
                    is_assigned = db.is_note_assigned_to_student(student_id, note.id)
                    prefix = "✅" if is_assigned else "📚"
                    row.append(InlineKeyboardButton(f"{prefix} {note.title}", callback_data=f"assign_note_{note.id}_{process_id}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("📋 Выбрать из всех конспектов", callback_data=f"manual_select_notes_{process_id}")])
        keyboard.append([InlineKeyboardButton("❌ Не выдавать конспект", callback_data=f"skip_note_assignment_{process_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_check_unassigned_notes")])
        student = db.get_student_by_id(student_id)
        await query.edit_message_text(f"📚 Выберите конспект для ученика {student.name}:\n✅ - уже выдан\n📚 - доступен для выдачи", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    elif query.data.startswith("assign_note_"):
        parts = query.data.split("_")
        note_id = int(parts[2])
        process_id = parts[3]
        user_id = update.effective_user.id
        db = context.bot_data['db']
        pending = db.get_pending_note_assignment_by_process(process_id)
        if pending:
            student_id = pending.student_id
        else:
            await query.edit_message_text("❌ Ошибка: данные не найдены. Начните процесс заново.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_check_unassigned_notes")]]))
            return ConversationHandler.END
        success = db.assign_note_to_student(student_id, note_id)
        if success:
            note = db.get_note_by_id(note_id)
            student = db.get_student_by_id(student_id)
            await query.edit_message_text(f"✅ Конспект '{note.title}' успешно выдан ученику {student.name}!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_check_unassigned_notes")]]))
        else:
            await query.edit_message_text("❌ Ошибка при выдаче конспекта", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_check_unassigned_notes")]]))
        db.delete_pending_note_assignment_by_process(process_id)
        return ConversationHandler.END

    elif query.data.startswith("manual_select_notes_"):
        process_id = query.data.split("_")[-1]
        user_id = update.effective_user.id
        db = context.bot_data['db']
        pending = db.get_pending_note_assignment_by_process(process_id)
        if not pending:
            await query.edit_message_text("❌ Ошибка: данные не найдены. Начните процесс заново.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_check_unassigned_notes")]]))
            return ConversationHandler.END
        student_id = pending.student_id
        exam_type = db.get_student_by_id(student_id).exam_type
        available_notes = db.get_notes_by_exam(exam_type)
        if not available_notes:
            back_cb = "admin_give_homework" if pending.origin == 'give_homework' else "admin_check_unassigned_notes"
            await query.edit_message_text("❌ Нет доступных конспектов для этого типа экзамена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=back_cb)]]))
            db.delete_pending_note_assignment_by_process(process_id)
            return ConversationHandler.END
        keyboard = []
        for i in range(0, len(available_notes), 2):
            row = []
            for j in range(2):
                if i + j < len(available_notes):
                    note = available_notes[i + j]
                    is_assigned = db.is_note_assigned_to_student(student_id, note.id)
                    prefix = "✅" if is_assigned else "📚"
                    row.append(InlineKeyboardButton(f"{prefix} {note.title}", callback_data=f"assign_note_{note.id}_{process_id}"))
            keyboard.append(row)
        back_cb = "admin_give_homework" if pending.origin == 'give_homework' else "admin_check_unassigned_notes"
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=back_cb)])
        student = db.get_student_by_id(student_id)
        await query.edit_message_text(f"📚 Выберите конспект для ученика {student.name}:\n✅ - уже выдан\n📚 - доступен для выдачи", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    elif query.data.startswith("skip_note_assignment_"):
        process_id = query.data.split("_")[-1]
        user_id = update.effective_user.id
        db = context.bot_data['db']
        pending = db.get_pending_note_assignment_by_process(process_id)
        db.delete_pending_note_assignment_by_process(process_id)
        # Всегда возвращаем в главное меню ученика
        await query.edit_message_text("✅ Домашнее задание выдано без конспекта", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_menu")]]))
        return ConversationHandler.END

    elif query.data.startswith("assign_note_homework_"):
        # assign_note_homework_{homework_id}_{student_id}
        parts = query.data.split("_")
        homework_id = int(parts[3])
        student_id = int(parts[4])
        user_id = update.effective_user.id
        db = context.bot_data['db']
        process_id = str(uuid.uuid4())
        db.add_pending_note_assignment_with_process(process_id, user_id, student_id=student_id, step='choose_note')
        exam_type = db.get_student_by_id(student_id).exam_type
        available_notes = db.get_notes_by_exam(exam_type)
        if not available_notes:
            await query.edit_message_text("❌ Нет доступных конспектов для этого типа экзамена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]]))
            db.delete_pending_note_assignment_by_process(process_id)
            return ConversationHandler.END
        keyboard = []
        for i in range(0, len(available_notes), 2):
            row = []
            for j in range(2):
                if i + j < len(available_notes):
                    note = available_notes[i + j]
                    is_assigned = db.is_note_assigned_to_student(student_id, note.id)
                    prefix = "✅" if is_assigned else "📚"
                    row.append(InlineKeyboardButton(f"{prefix} {note.title}", callback_data=f"assign_note_{note.id}_{process_id}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("📋 Выбрать из всех конспектов", callback_data=f"manual_select_notes_{process_id}")])
        keyboard.append([InlineKeyboardButton("❌ Не выдавать конспект", callback_data=f"skip_note_assignment_{process_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")])
        student = db.get_student_by_id(student_id)
        await query.edit_message_text(f"📚 Выберите конспект для ученика {student.name}:\n✅ - уже выдан\n📚 - доступен для выдачи", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    # Для всех остальных случаев
    return ConversationHandler.END

async def handle_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает изменение имени ученика"""
    user_id = update.effective_user.id
    if user_id not in temp_data:
        await update.message.reply_text("❌ Ошибка: данные не найдены")
        return ConversationHandler.END
    
    student_id = temp_data[user_id]["student_id"]
    new_name = update.message.text
    
    db = context.bot_data['db']
    db.update_student_name(student_id, new_name)
    
    await update.message.reply_text(
        f"✅ Имя успешно изменено на: {new_name}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
        ]])
    )
    return ConversationHandler.END

async def handle_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает изменение ссылки ученика"""
    user_id = update.effective_user.id
    if user_id not in temp_data:
        await update.message.reply_text("❌ Ошибка: данные не найдены")
        return ConversationHandler.END
    
    student_id = temp_data[user_id]["student_id"]
    new_link = update.message.text.strip()
    
    # Валидация URL
    from core.database import is_valid_url
    if not is_valid_url(new_link):
        await update.message.reply_text(
            "❌ Неверный формат ссылки!\n\n"
            "Ссылка должна быть в формате:\n"
            "• https://example.com\n"
            "• http://example.com\n"
            "• https://t.me/username\n\n"
            "Попробуйте еще раз:"
        )
        return EDIT_STUDENT_LINK
    
    db = context.bot_data['db']
    db.update_student_link(student_id, new_link)
    
    await update.message.reply_text(
        f"✅ Ссылка успешно изменена на: {new_link}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
        ]])
    )
    return ConversationHandler.END

async def handle_add_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка новой заметки"""
    user_id = update.effective_user.id
    if user_id not in edit_data or edit_data[user_id]["type"] != "note":
        await update.message.reply_text("❌ Ошибка добавления заметки. Начните сначала.")
        await admin_menu(update, context)
        return ConversationHandler.END
        
    note_text = update.message.text
    student_id = edit_data[user_id]["student_id"]
    context.bot_data['db'].add_student_note(student_id, note_text)
    
    await update.message.reply_text("✅ Заметка успешно добавлена!")
    del edit_data[user_id]
    
    await admin_menu(update, context)
    return ConversationHandler.END

async def show_exam_buttons_edit(update: Update, student_id: int) -> None:
    """Показывает кнопки выбора экзамена для редактирования"""
    keyboard = [
        [
            InlineKeyboardButton("📝 ОГЭ", callback_data=f"student_new_exam_OGE"),
            InlineKeyboardButton("🎓 ЕГЭ", callback_data=f"student_new_exam_EGE")
        ],
        [InlineKeyboardButton("📖 Школьная программа", callback_data=f"student_new_exam_SCHOOL")],
        [InlineKeyboardButton("❌ Отмена", callback_data="edit_cancel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text="📚 Выберите новый тип экзамена:",
            reply_markup=reply_markup
        )

async def handle_edit_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор нового типа экзамена"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_cancel":
        await admin_menu(update, context)
        return ConversationHandler.END
    
    user_id = query.from_user.id
    if user_id not in edit_data or edit_data[user_id]["type"] != "exam":
        await query.message.edit_text("❌ Ошибка редактирования. Начните сначала.")
        await admin_menu(update, context)
        return ConversationHandler.END
    
    exam_type = query.data.split("_")[-1]
    student_id = edit_data[user_id]["student_id"]
    
    try:
        old_exam_type = context.bot_data['db'].get_student_by_id(student_id).exam_type
        context.bot_data['db'].update_student_exam_type(student_id, ExamType[exam_type])
        
        # Формируем сообщение в зависимости от того, изменился ли тип экзамена
        if old_exam_type != ExamType[exam_type]:
            message_text = f"✅ Тип экзамена изменен с {old_exam_type.value} на {ExamType[exam_type].value}!\n\n⚠️ Старые назначения домашних заданий и конспектов были очищены."
        else:
            message_text = "✅ Тип экзамена успешно изменен!"
        
        await query.message.edit_text(message_text)
        del edit_data[user_id]
        await admin_menu(update, context)
        return ConversationHandler.END
    except Exception as e:
        await query.message.edit_text(
            f"❌ Произошла ошибка при изменении типа экзамена: {str(e)}\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )
        if user_id in edit_data:
            del edit_data[user_id]
        await admin_menu(update, context)
        return ConversationHandler.END

async def give_homework_menu(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> int:
    """Меню выдачи домашнего задания или варианта"""
    keyboard = [
        [
            InlineKeyboardButton("👤 Ученику", callback_data="admin_give_homework"),
            InlineKeyboardButton("📄 Вариант", callback_data="admin_give_homework_variant")
        ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data="admin_back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(
        "Выберите действие:",
        reply_markup=reply_markup
    )
    return GIVE_HOMEWORK_MENU

async def handle_give_homework_variant(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> int:
    keyboard = [
        [InlineKeyboardButton("📝 ОГЭ", callback_data="give_variant_exam_OGE"), InlineKeyboardButton("🎓 ЕГЭ", callback_data="give_variant_exam_EGE")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(
        "Выберите тип экзамена для выдачи варианта:",
        reply_markup=reply_markup
    )
    return GIVE_VARIANT_CHOOSE_EXAM

async def handle_give_variant_choose_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    exam_type = query.data.split('_')[-1]
    user_id = query.from_user.id
    give_variant_temp[user_id] = {"exam_type": exam_type}
    await query.message.edit_text(
        "Отправьте ссылку на вариант:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]])
    )
    return GIVE_VARIANT_ENTER_LINK

async def handle_give_variant_enter_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    link = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Валидация URL
    from core.database import is_valid_url
    if not is_valid_url(link):
        await update.message.reply_text(
            "❌ Неверный формат ссылки!\n\n"
            "Ссылка должна быть в формате:\n"
            "• https://example.com\n"
            "• http://example.com\n"
            "• https://t.me/username\n\n"
            "Попробуйте еще раз:"
        )
        return GIVE_VARIANT_ENTER_LINK
    
    exam_type = give_variant_temp[user_id]["exam_type"]
    db = context.bot_data['db']
    db.add_variant(ExamType[exam_type], link)
    # Рассылаем всем ученикам этого экзамена уведомление и меню
    students = db.get_students_by_exam_type(ExamType[exam_type])
    for student in students:
        if student.telegram_id:
            db.add_notification(student.id, 'variant', "Актуальный вариант!", link)
            msg = await context.bot.send_message(
                chat_id=student.telegram_id,
                text="🔔 У вас новое уведомление! Откройте меню 'Уведомления'."
            )
            db.add_push_message(student.id, msg.message_id)
            # После push отправляем меню корректно по chat_id
            await send_student_menu_by_chat_id(context, student.telegram_id)
    await update.message.reply_text(
        "✅ Вариант успешно выдан всем ученикам этого экзамена!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]])
    )
    give_variant_temp.pop(user_id, None)
    return ConversationHandler.END

async def give_homework_choose_exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("📝 ОГЭ", callback_data="give_hw_exam_OGE"),
            InlineKeyboardButton("🎓 ЕГЭ", callback_data="give_hw_exam_EGE")
        ],
        [InlineKeyboardButton("📖 Школьная программа", callback_data="give_hw_exam_SCHOOL")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(
        "Выберите тип экзамена:",
        reply_markup=reply_markup
    )
    return GIVE_HOMEWORK_CHOOSE_EXAM

async def give_homework_choose_student(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    exam_type = update.callback_query.data.split('_')[-1]
    user_id = update.effective_user.id
    give_homework_temp[user_id] = {"exam_type": exam_type}
    db = Database()
    students = db.get_students_by_exam_type(ExamType[exam_type])
    if not students:
        await update.callback_query.message.edit_text(
            "Нет учеников для этого экзамена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]])
        )
        return ConversationHandler.END
    
    # Для школьной программы показываем выбор ученика
    if exam_type == "SCHOOL":
        keyboard = []
        for i in range(0, len(students), 2):
            row = []
            for j in range(2):
                if i + j < len(students):
                    student = students[i + j]
                    row.append(InlineKeyboardButton(student.name, callback_data=f"school_hw_student_{student.id}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text(
            "Выберите ученика для выдачи домашнего задания:",
            reply_markup=reply_markup
        )
        return GIVE_HOMEWORK_CHOOSE_STUDENT
    else:
        # Для ОГЭ и ЕГЭ оставляем старую логику
        keyboard = []
        for i in range(0, len(students), 2):
            row = []
            for j in range(2):
                if i + j < len(students):
                    student = students[i + j]
                    row.append(InlineKeyboardButton(student.name, callback_data=f"give_hw_student_{student.id}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text(
            "Выберите ученика:",
            reply_markup=reply_markup
        )
        return GIVE_HOMEWORK_CHOOSE_STUDENT

async def give_homework_choose_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    student_id = int(update.callback_query.data.split('_')[-1])
    user_id = update.effective_user.id
    give_homework_temp[user_id]["student_id"] = student_id
    db = Database()
    exam_type = give_homework_temp[user_id]["exam_type"]
    homeworks = db.get_homework_by_exam(exam_type)
    if not homeworks:
        await update.callback_query.message.edit_text(
            "Нет домашних заданий для этого экзамена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]])
        )
        return ConversationHandler.END
    keyboard = []
    for i in range(0, len(homeworks), 2):
        row = []
        for j in range(2):
            if i + j < len(homeworks):
                hw = homeworks[i + j]
                row.append(InlineKeyboardButton(hw.title, callback_data=f"give_hw_task_{hw.id}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(
        "Выберите задание для выдачи:",
        reply_markup=reply_markup
    )
    return GIVE_HOMEWORK_CHOOSE_TASK

async def give_homework_assign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    homework_id = int(update.callback_query.data.split('_')[-1])
    user_id = update.effective_user.id
    student_id = give_homework_temp[user_id]["student_id"]
    db = Database()
    
    # Проверяем, было ли задание уже назначено
    was_assigned = db.is_homework_assigned_to_student(student_id, homework_id)
    success = db.assign_homework_to_student(student_id, homework_id)
    
    if success:
        student = db.get_student_by_id(student_id)
        homework = db.get_homework_by_id(homework_id)
        
        # Сохраняем данные для следующего шага
        give_homework_temp[user_id]["homework_id"] = homework_id
        
        if was_assigned:
            message_text = "✅ Домашнее задание повторно выдано (обновлена дата назначения)!"
        else:
            message_text = "✅ Домашнее задание успешно выдано!"
        
        # Добавляем уведомление в БД
        if student:
            notif_text = f"Новое домашнее задание: {homework.title}" if homework else "Новое домашнее задание!"
            db.add_notification(student.id, 'homework', notif_text, homework.link if homework else None)
            # Push только если есть непрочитанные уведомления
            if db.has_unread_notifications(student.id):
                try:
                    msg = await context.bot.send_message(
                        chat_id=student.telegram_id,
                        text="🔔 У вас новое уведомление! Откройте меню 'Уведомления'."
                    )
                    db.add_push_message(student.id, msg.message_id)
                    # После push отправляем меню корректно по chat_id
                    await send_student_menu_by_chat_id(context, student.telegram_id)
                except Exception as e:
                    pass
        
        # Проверяем тип экзамена
        if homework.exam_type == ExamType.SCHOOL:
            # Для школьной программы сразу предлагаем конспекты
            await suggest_notes_for_homework(update, context, homework, student)
            return ConversationHandler.END
        else:
            # Для ОГЭ и ЕГЭ показываем меню выбора статуса
            # Сохраняем данные для следующего шага
            give_homework_temp[user_id]["homework_id"] = homework_id
            
            # Показываем меню выбора статуса
            keyboard = [
                [InlineKeyboardButton("✅ Пройдено", callback_data="hw_status_completed")],
                [InlineKeyboardButton("🔄 В процессе", callback_data="hw_status_in_progress")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]
            ]
            
            await update.callback_query.message.edit_text(
                f"{message_text}\n\n"
                f"📝 Задание: {homework.title}\n"
                f"👤 Ученик: {student.name}\n\n"
                f"Выберите статус для этого задания:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return GIVE_HOMEWORK_STATUS
    
    give_homework_temp.pop(user_id, None)
    return ConversationHandler.END

async def give_homework_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор статуса домашнего задания"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Проверяем наличие данных
    if user_id not in give_homework_temp:
        await query.edit_message_text(
            "❌ Ошибка: данные не найдены. Начните процесс заново.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]])
        )
        return ConversationHandler.END
    
    data = give_homework_temp[user_id]
    student_id = data.get("student_id")
    homework_id = data.get("homework_id")
    
    if not student_id or not homework_id:
        await query.edit_message_text(
            "❌ Ошибка: неполные данные. Начните процесс заново.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]])
        )
        give_homework_temp.pop(user_id, None)
        return ConversationHandler.END
    
    db = Database()
    student = db.get_student_by_id(student_id)
    homework = db.get_homework_by_id(homework_id)
    
    if not student or not homework:
        await query.edit_message_text(
            "❌ Ошибка: ученик или задание не найдены.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]])
        )
        give_homework_temp.pop(user_id, None)
        return ConversationHandler.END
    
    # Определяем статус на основе выбранной кнопки
    if query.data == "hw_status_completed":
        status = "completed"
        status_text = "✅ Пройдено"
    elif query.data == "hw_status_in_progress":
        status = "in_progress"
        status_text = "🔄 В процессе"
    else:
        # Если нажата кнопка "Назад"
        give_homework_temp.pop(user_id, None)
        await admin_menu(update, context)
        return ConversationHandler.END
    
    # Обновляем статус в базе данных
    success = db.update_homework_status(student_id, homework_id, status)
    
    if success:
        # Предлагаем конспекты для выдачи (только для ОГЭ и ЕГЭ)
        await suggest_notes_for_homework(update, context, homework, student)
        # Очищаем временные данные
        give_homework_temp.pop(user_id, None)
        return ConversationHandler.END
    else:
        await query.edit_message_text(
            "❌ Ошибка при обновлении статуса.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")]])
        )
        give_homework_temp.pop(user_id, None)
        return ConversationHandler.END

async def suggest_notes_for_homework(update: Update, context: ContextTypes.DEFAULT_TYPE, homework, student):
    """Предлагает конспекты для выдачи после назначения домашнего задания"""
    db = context.bot_data['db']
    process_id = str(uuid.uuid4())
    db.add_pending_note_assignment_with_process(process_id, update.effective_user.id, student_id=student.id, step='choose_note', origin='give_homework')

    # Получаем конспекты того же типа экзамена
    available_notes = db.get_notes_by_exam(homework.exam_type)

    # Ищем подходящие конспекты
    exact_matches = []
    keyword_matches = []

    for note in available_notes:
        # Проверяем, не выдан ли уже конспект ученику
        if db.is_note_assigned_to_student(student.id, note.id):
            continue
        # Проверяем точное совпадение по номеру
        hw_number = homework.get_task_number()
        note_number = note.get_task_number()
        if hw_number == note_number and hw_number != float('inf'):
            exact_matches.append(note)
        else:
            # Проверяем схожесть по ключевым словам
            hw_keywords = db._extract_keywords(homework.title)
            note_keywords = db._extract_keywords(note.title)
            similarity = db._calculate_similarity(hw_keywords, note_keywords)
            if similarity > 0.7:  # Порог схожести 70%
                keyword_matches.append(note)

    # Формируем клавиатуру
    keyboard = []

    if exact_matches:
        keyboard.append([InlineKeyboardButton(
            f"✅ {exact_matches[0].title}",
            callback_data=f"assign_note_{exact_matches[0].id}_{process_id}"
        )])

    if keyword_matches:
        for note in keyword_matches[:2]:  # Максимум 2 предложения
            keyboard.append([InlineKeyboardButton(
                f"🔍 {note.title}",
                callback_data=f"assign_note_{note.id}_{process_id}"
            )])

    keyboard.append([InlineKeyboardButton(
        "📋 Выбрать из всех конспектов",
        callback_data=f"manual_select_notes_{process_id}"
    )])

    keyboard.append([InlineKeyboardButton(
        "❌ Не выдавать конспект",
        callback_data=f"skip_note_assignment_{process_id}"
    )])

    # Формируем текст сообщения
    message_text = f"✅ Домашнее задание '{homework.title}' выдано ученику {student.name}!\n\n"

    if exact_matches:
        message_text += f"📚 Найден подходящий конспект:\n"
    elif keyword_matches:
        message_text += f"🔍 Найдены похожие конспекты:\n"
    else:
        message_text += f"📚 Хотите выдать конспект к этому заданию?\n"

    message_text += f"\nВыберите действие:"

    await update.callback_query.message.edit_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def check_unassigned_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет невыданные конспекты и предлагает их выдать ученикам"""
    db = context.bot_data['db']
    unassigned = db.get_unassigned_notes_for_students()
    
    if not unassigned:
        await update.callback_query.edit_message_text(
            "✅ Все конспекты выданы ученикам!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_notes")
            ]])
        )
        return
    
    # Показываем список невыданных конспектов
    keyboard = []
    for note, student_count in unassigned[:5]:  # Показываем первые 5
        keyboard.append([InlineKeyboardButton(
            f"📚 {note.title} ({student_count} учеников)", 
            callback_data=f"assign_unassigned_note_{note.id}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_notes")])
    
    await update.callback_query.edit_message_text(
        f"🔍 Найдено {len(unassigned)} конспектов, которые можно выдать ученикам:\n\n"
        f"Выберите конспект для выдачи:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Для всех остальных случаев
    return ConversationHandler.END

async def school_homework_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает выбор типа задания для школьной программы"""
    student_id = int(update.callback_query.data.split('_')[-1])
    user_id = update.effective_user.id
    give_homework_temp[user_id]["student_id"] = student_id
    
    db = Database()
    exam_type = give_homework_temp[user_id]["exam_type"]
    homeworks = db.get_homework_by_exam(exam_type)
    
    keyboard = []
    
    # Если есть существующие задания, показываем их
    if homeworks:
        keyboard.append([InlineKeyboardButton("📚 Выбрать из существующих заданий", callback_data="school_existing_homework")])
    
    keyboard.append([InlineKeyboardButton("📝 Загрузить новое задание", callback_data="school_new_homework")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(
        "Выберите способ выдачи домашнего задания:",
        reply_markup=reply_markup
    )
    return SCHOOL_HOMEWORK_CHOICE

async def school_existing_homework(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает существующие задания для школьной программы"""
    user_id = update.effective_user.id
    db = Database()
    exam_type = give_homework_temp[user_id]["exam_type"]
    homeworks = db.get_homework_by_exam(exam_type)
    
    keyboard = []
    for i in range(0, len(homeworks), 2):
        row = []
        for j in range(2):
            if i + j < len(homeworks):
                hw = homeworks[i + j]
                row.append(InlineKeyboardButton(hw.title, callback_data=f"give_hw_task_{hw.id}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_give_homework")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(
        "Выберите задание для выдачи:",
        reply_markup=reply_markup
    )
    return GIVE_HOMEWORK_CHOOSE_TASK

async def school_new_homework_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает название нового домашнего задания"""
    await update.callback_query.message.edit_text(
        "Введите название домашнего задания:"
    )
    return SCHOOL_HOMEWORK_TITLE

async def school_homework_title_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает введенное название домашнего задания"""
    title = update.message.text
    user_id = update.effective_user.id
    give_homework_temp[user_id]["title"] = title
    
    await update.message.reply_text(
        "Отправьте ссылку на домашнее задание:"
    )
    return SCHOOL_HOMEWORK_LINK

async def school_homework_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает введенную ссылку на домашнее задание"""
    link = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Валидация URL
    from core.database import is_valid_url
    if not is_valid_url(link):
        await update.message.reply_text(
            "❌ Неверный формат ссылки!\n\n"
            "Ссылка должна быть в формате:\n"
            "• https://example.com\n"
            "• http://example.com\n"
            "• https://t.me/username\n\n"
            "Попробуйте еще раз:"
        )
        return SCHOOL_HOMEWORK_LINK
    
    give_homework_temp[user_id]["link"] = link
    
    keyboard = [
        [InlineKeyboardButton("📎 Прикрепить файл", callback_data="school_homework_file")],
        [InlineKeyboardButton("⏭️ Пропустить", callback_data="school_homework_no_file")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Хотите прикрепить файл к домашнему заданию?",
        reply_markup=reply_markup
    )
    return SCHOOL_HOMEWORK_FILE

async def school_homework_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    # Если это callback-кнопка — просим отправить файл
    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text("Пожалуйста, отправьте файл домашнего задания одним сообщением.")
        return SCHOOL_HOMEWORK_FILE

    # Если это сообщение с файлом
    if hasattr(update, "message") and update.message and update.message.document:
        file = await context.bot.get_file(update.message.document.file_id)
        file_name = update.message.document.file_name
        file_path = os.path.join("homework_files", file_name)
        os.makedirs("homework_files", exist_ok=True)
        await file.download_to_drive(file_path)
        give_homework_temp[user_id]["file_path"] = file_path
        await update.message.reply_text("✅ Файл успешно загружен!")
        return await create_school_homework(update, context)

    # Если что-то пошло не так
    if hasattr(update, "message") and update.message:
        await update.message.reply_text("❌ Пожалуйста, отправьте файл.")
    return SCHOOL_HOMEWORK_FILE

async def school_homework_no_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает пропуск файла домашнего задания"""
    user_id = update.effective_user.id
    give_homework_temp[user_id]["file_path"] = None
    
    # Создаем домашнее задание
    return await create_school_homework(update, context)

async def create_school_homework(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    db = Database()
    title = give_homework_temp[user_id]["title"]
    link = give_homework_temp[user_id]["link"]
    file_path = give_homework_temp[user_id].get("file_path")
    student_id = give_homework_temp[user_id]["student_id"]
    success = db.add_homework(title, link, ExamType.SCHOOL, file_path)
    if success:
        homeworks = db.get_homework_by_exam(ExamType.SCHOOL)
        homework = next((hw for hw in homeworks if hw.title == title and hw.link == link), None)
        if homework:
            db.assign_homework_to_student(student_id, homework.id)
            student = db.get_student_by_id(student_id)
            
            if student:
                notif_text = f"Новое домашнее задание: {homework.title}"
                db.add_notification(student.id, 'homework', notif_text, homework.link)
                if db.has_unread_notifications(student.id):
                    try:
                        msg = await context.bot.send_message(
                            chat_id=student.telegram_id,
                            text="🔔 У вас новое уведомление! Откройте меню 'Уведомления'."
                        )
                        db.add_push_message(student.id, msg.message_id)
                        # НЕ обновляем меню для школьной программы
                        # await send_student_menu_by_chat_id(context, student.telegram_id)
                    except Exception as e:
                        pass
            
            # Для школьной программы сразу предлагаем создать конспект
            return await suggest_school_note_creation(update, context, homework, student)
        else:
            if hasattr(update, "message") and update.message:
                await update.message.reply_text("❌ Ошибка при создании домашнего задания")
            elif hasattr(update, "callback_query") and update.callback_query:
                await update.callback_query.edit_message_text("❌ Ошибка при создании домашнего задания")
            return ConversationHandler.END
    else:
        if hasattr(update, "message") and update.message:
            await update.message.reply_text("❌ Ошибка при создании домашнего задания")
        elif hasattr(update, "callback_query") and update.callback_query:
            await update.callback_query.edit_message_text("❌ Ошибка при создании домашнего задания")
        return ConversationHandler.END
    give_homework_temp.pop(user_id, None)

async def suggest_school_note_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, homework, student) -> int:
    """Предлагает создать конспект для школьного домашнего задания"""
    keyboard = [
        [InlineKeyboardButton("📝 Создать конспект", callback_data="school_create_note")],
        [InlineKeyboardButton("❌ Не создавать", callback_data="school_no_note")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"✅ Домашнее задание '{homework.title}' успешно создано и выдано ученику {student.name}!\n\n"
            f"Хотите создать конспект к этому заданию?",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"✅ Домашнее задание '{homework.title}' успешно создано и выдано ученику {student.name}!\n\n"
            f"Хотите создать конспект к этому заданию?",
            reply_markup=reply_markup
        )
    return SCHOOL_NOTE_CHOICE

async def school_note_creation_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор создания конспекта"""
    query = update.callback_query
    
    if query.data == "school_create_note":
        await query.message.edit_text("Введите название конспекта:")
        return SCHOOL_NOTE_TITLE
    else:
        await query.message.edit_text("✅ Домашнее задание выдано без конспекта!")
        await admin_menu(update, context)
        return ConversationHandler.END

async def school_note_title_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает введенное название конспекта"""
    title = update.message.text
    user_id = update.effective_user.id
    give_homework_temp[user_id]["note_title"] = title
    
    await update.message.reply_text("Отправьте ссылку на конспект:")
    return SCHOOL_NOTE_LINK

async def school_note_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает введенную ссылку на конспект"""
    link = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Валидация URL
    from core.database import is_valid_url
    if not is_valid_url(link):
        await update.message.reply_text(
            "❌ Неверный формат ссылки!\n\n"
            "Ссылка должна быть в формате:\n"
            "• https://example.com\n"
            "• http://example.com\n"
            "• https://t.me/username\n\n"
            "Попробуйте еще раз:"
        )
        return SCHOOL_NOTE_LINK
    
    give_homework_temp[user_id]["note_link"] = link
    
    keyboard = [
        [InlineKeyboardButton("📎 Прикрепить файл", callback_data="school_note_file")],
        [InlineKeyboardButton("⏭️ Пропустить", callback_data="school_note_no_file")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Хотите прикрепить файл к конспекту?",
        reply_markup=reply_markup
    )
    return SCHOOL_NOTE_FILE

async def school_note_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    # Если это callback-кнопка — просим отправить файл
    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text("Пожалуйста, отправьте файл конспекта одним сообщением.")
        return SCHOOL_NOTE_FILE

    # Если это сообщение с файлом
    if hasattr(update, "message") and update.message and update.message.document:
        file = await context.bot.get_file(update.message.document.file_id)
        file_name = update.message.document.file_name
        file_path = os.path.join("notes_files", file_name)
        os.makedirs("notes_files", exist_ok=True)
        await file.download_to_drive(file_path)
        give_homework_temp[user_id]["note_file_path"] = file_path
        await update.message.reply_text("✅ Файл конспекта успешно загружен!")
        return await create_school_note(update, context)

    # Если что-то пошло не так
    if hasattr(update, "message") and update.message:
        await update.message.reply_text("❌ Пожалуйста, отправьте файл.")
    return SCHOOL_NOTE_FILE

async def school_note_no_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает пропуск файла конспекта"""
    user_id = update.effective_user.id
    give_homework_temp[user_id]["note_file_path"] = None
    
    # Создаем конспект
    return await create_school_note(update, context)

async def create_school_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Создает конспект для школьной программы"""
    user_id = update.effective_user.id
    db = Database()
    
    title = give_homework_temp[user_id]["note_title"]
    link = give_homework_temp[user_id]["note_link"]
    file_path = give_homework_temp[user_id].get("note_file_path")
    student_id = give_homework_temp[user_id]["student_id"]
    
    # Создаем конспект
    success = db.add_note(title, link, ExamType.SCHOOL, file_path)
    
    if success:
        # Получаем созданный конспект
        notes = db.get_notes_by_exam(ExamType.SCHOOL)
        note = next((n for n in notes if n.title == title and n.link == link), None)
        
        if note:
            # Назначаем конспект ученику
            db.assign_note_to_student(student_id, note.id)
            if hasattr(update, "message") and update.message:
                await update.message.reply_text(f"✅ Конспект '{note.title}' успешно создан и выдан ученику!")
            elif hasattr(update, "callback_query") and update.callback_query:
                await update.callback_query.edit_message_text(f"✅ Конспект '{note.title}' успешно создан и выдан ученику!")
            await admin_menu(update, context)
        else:
            if hasattr(update, "message") and update.message:
                await update.message.reply_text("❌ Ошибка при создании конспекта")
            elif hasattr(update, "callback_query") and update.callback_query:
                await update.callback_query.edit_message_text("❌ Ошибка при создании конспекта")
            await admin_menu(update, context)
    else:
        if hasattr(update, "message") and update.message:
            await update.message.reply_text("❌ Ошибка при создании конспекта")
        elif hasattr(update, "callback_query") and update.callback_query:
            await update.callback_query.edit_message_text("❌ Ошибка при создании конспекта")
        await admin_menu(update, context)
    
    # Очищаем временные данные
    give_homework_temp.pop(user_id, None)
    return ConversationHandler.END

# --- Хэндлеры для статистики ---
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def show_statistics_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📝 ОГЭ", callback_data="statistics_exam_OGE"),
         InlineKeyboardButton("🎓 ЕГЭ", callback_data="statistics_exam_EGE")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("Выберите экзамен для просмотра статистики:", reply_markup=reply_markup)
    return STATISTICS_CHOOSE_EXAM

async def handle_statistics_exam_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "statistics_exam_back":
        return await show_statistics_menu(update, context)
    exam_type = query.data.split('_')[-1]
    context.user_data['statistics_exam'] = exam_type
    db = context.bot_data['db']
    students = db.get_students_by_exam_type(ExamType[exam_type])
    if not students:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="statistics_exam_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Нет учеников для выбранного экзамена.", reply_markup=reply_markup)
        return STATISTICS_CHOOSE_EXAM
    keyboard = []
    row = []
    for i, student in enumerate(students, 1):
        row.append(InlineKeyboardButton(student.name, callback_data=f"statistics_student_{student.id}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="statistics_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("Выберите ученика:", reply_markup=reply_markup)
    return STATISTICS_CHOOSE_STUDENT

async def handle_statistics_student_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    student_id = int(query.data.split('_')[-1]) if 'statistics_student_' in query.data else context.user_data.get('statistics_student_id')
    db = context.bot_data['db']
    student = db.get_student_by_id(student_id)
    exam_type = context.user_data.get('statistics_exam', 'EGE')
    exam_label = 'ЕГЭ' if exam_type == 'EGE' else 'ОГЭ'
    page = 0
    if 'statistics_page_' in query.data:
        page = int(query.data.split('_')[-1])
    context.user_data['statistics_student_id'] = student_id
    context.user_data['statistics_page'] = page

    # --- ФИКС: если нет нужных данных, возвращаем к выбору экзамена ---
    if not student_id or not exam_type or not student:
        await show_statistics_menu(update, context)
        return STATISTICS_CHOOSE_EXAM

    if exam_type == 'EGE':
        roadmap = [
            (1, '🖊️'), (4, '🖊️'), (11, '🖊️💻'), (7, '🖊️💻'), (10, '📝'), (3, '📊'), (18, '📊'), (22, '📊'),
            (9, '📊💻'), ('Python', '🐍'), (2, '🐍'), (15, '🐍'), (6, '🐍'), (14, '🐍'), (5, '🐍'), (12, '🐍'),
            (8, '🐍'), (13, '🐍'), (16, '🐍'), (23, '🐍'), ('19-21', '🖊️💻'), (25, '🐍'), (27, '🐍'), (24, '🐍'), (26, '📊💻')
        ]
        
        # Получаем реальные статусы из базы данных
        real_statuses = db.get_homework_status_for_student(student.id, ExamType.EGE)
        
        tasks = []
        primary_score = 0
        for idx, (num, emoji) in enumerate(roadmap, 1):
            # Получаем статус из базы данных или используем "Не пройдено" по умолчанию
            status = real_statuses.get(num)
            # Преобразуем статусы из базы в читаемый вид
            if status == 'completed' or status == 'Пройдено':
                status = 'Пройдено'
            elif status == 'in_progress' or status == 'В процессе':
                status = 'В процессе'
            else:
                status = 'Не пройдено'
            # Поиск конспекта
            note_line = ''
            if status in ('Пройдено', 'В процессе'):
                notes = db.get_notes_by_exam(ExamType.EGE)
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
        
        # Таблица перевода первичных баллов в тестовые
        primary_to_test = {
            1: 7, 2: 14, 3: 20, 4: 27, 5: 34, 6: 40, 7: 43, 8: 46, 9: 48, 10: 51, 11: 54, 12: 56, 13: 59, 14: 62, 15: 64, 16: 67, 17: 70, 18: 72, 19: 75, 20: 78, 21: 80, 22: 83, 23: 85, 24: 88, 25: 90, 26: 93, 27: 95, 28: 98, 29: 100
        }
        test_score = primary_to_test.get(primary_score, 0)
        per_page = 5
        total_pages = (len(tasks) - 1) // per_page + 1
        start = page * per_page
        end = start + per_page
        page_tasks = tasks[start:end]
        tasks_text = "\n\n".join(page_tasks)
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"statistics_page_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"statistics_page_{page+1}"))
        progress_text = (
            f"<b>Прогресс ученика {student.name} ({exam_label}):</b>\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>🏅 Первичный балл: {primary_score}</b>\n"
            f"<b>🎯 Тестовый балл: {test_score}</b>\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"{tasks_text}"
        )
    elif exam_type == 'OGE':
        roadmap = [
            (1, '🖊️'), (2, '🖊️'), (4, '🖊️'), (9, '🖊️'), (7, '🖊️'), (8, '🖊️'), (10, '🖊️'), (5, '🖊️'), (3, '🖊️'), (6, '🖊️'),
            (11, '📁'), (12, '📁'), ('13.1', '🗂️'), ('13.2', '🗂️'), (14, '🗂️'), (15, '🐍'), ('Python', '🐍'), (16, '🐍')
        ]
        
        # Получаем реальные статусы из базы данных
        real_statuses = db.get_homework_status_for_student(student.id, ExamType.OGE)
        
        tasks = []
        score = 0
        passed_13 = False
        for num, emoji in roadmap:
            # Получаем статус из базы данных или используем "Не пройдено" по умолчанию
            status = real_statuses.get(num)
            # Преобразуем статусы из базы в читаемый вид
            if status == 'completed' or status == 'Пройдено':
                status = 'Пройдено'
            elif status == 'in_progress' or status == 'В процессе':
                status = 'В процессе'
            else:
                status = 'Не пройдено'
            # Поиск конспекта
            note_line = ''
            if status in ('Пройдено', 'В процессе'):
                notes = db.get_notes_by_exam(ExamType.OGE)
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
        per_page = 5
        total_pages = (len(tasks) - 1) // per_page + 1
        start = page * per_page
        end = start + per_page
        page_tasks = tasks[start:end]
        tasks_text = "\n\n".join(page_tasks)
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"statistics_page_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"statistics_page_{page+1}"))
        if score <= 4:
            grade = '2'
        elif score <= 10:
            grade = '3'
        elif score <= 16:
            grade = '4'
        else:
            grade = '5'
        progress_text = (
            f"<b>Прогресс ученика {student.name} ({exam_label}):</b>\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>🏅 Текущий балл: {score}</b>\n"
            f"<b>📊 Оценка: {grade}</b>\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"{tasks_text}"
        )
    else:
        tasks_text = "\n\n".join([f"📝 Задание {i+1}\n└─ Статус: ❌ Не пройдено" for i in range(5)])
        nav_buttons = []
    
    keyboard = []
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="statistics_exam_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(progress_text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
    return STATISTICS_CHOOSE_STUDENT

# Функции для управления расписанием
async def show_schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню управления расписанием"""
    keyboard = [
        [
            InlineKeyboardButton("📅 Просмотр расписания", callback_data="schedule_exam_view"),
            InlineKeyboardButton("➕ Добавить занятие", callback_data="schedule_exam_add")
        ],
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data="schedule_exam_edit"),
            InlineKeyboardButton("❌ Удалить занятие", callback_data="schedule_exam_delete")
        ],
        [InlineKeyboardButton("⚙️ Настройки переносов", callback_data="reschedule_settings")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.message.edit_text(
        "📅 Управление расписанием\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def show_schedule_exam_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """Показывает выбор экзамена для работы с расписанием"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [
            InlineKeyboardButton("📝 ОГЭ", callback_data=f"schedule_exam_{action}_OGE"),
            InlineKeyboardButton("🎓 ЕГЭ", callback_data=f"schedule_exam_{action}_EGE")
        ],
        [InlineKeyboardButton("📖 Школьная программа", callback_data=f"schedule_exam_{action}_SCHOOL")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    actions = {
        "view": "просмотра",
        "add": "добавления",
        "edit": "редактирования",
        "delete": "удаления"
    }
    
    await query.edit_message_text(
        f"📚 Выберите тип экзамена для {actions.get(action, '')} расписания:",
        reply_markup=reply_markup
    )

async def show_schedule_student_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, exam_type: str = None) -> None:
    """Показывает выбор студента для работы с расписанием"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    
    # Если указан тип экзамена, фильтруем студентов
    if exam_type:
        students = db.get_students_by_exam_type(ExamType[exam_type])
    else:
        students = db.get_all_students()
    
    if not students:
        exam_text = f" для {ExamType[exam_type].value}" if exam_type else ""
        await query.edit_message_text(
            f"❌ Нет студентов{exam_text} в базе данных.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return
    
    keyboard = []
    for student in students:
        display_name = student.display_name or student.name
        student_exam_type = student.exam_type.value if student.exam_type else "Не указан"
        button_text = f"{display_name} ({student_exam_type})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"schedule_{action}_student_{student.id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    actions = {
        "view": "просмотра",
        "add": "добавления",
        "edit": "редактирования",
        "delete": "удаления"
    }
    
    exam_text = f" для {ExamType[exam_type].value}" if exam_type else ""
    await query.edit_message_text(
        f"👥 Выберите студента для {actions.get(action, '')} расписания{exam_text}:",
        reply_markup=reply_markup
    )

async def show_student_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: int) -> None:
    """Показывает расписание конкретного студента"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    student = db.get_student_by_id(student_id)
    schedules = db.get_student_schedule(student_id)
    
    if not student:
        await query.edit_message_text(
            "❌ Студент не найден.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return
    
    display_name = student.display_name or student.name
    
    if not schedules:
        text = f"📅 <b>Расписание {display_name}</b>\n\n❌ Расписание не настроено."
    else:
        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        text = f"📅 <b>Расписание {display_name}</b>\n\n"
        
        for schedule in schedules:
            day_name = days[schedule.day_of_week]
            duration_text = f" ({schedule.duration} мин)" if schedule.duration != 60 else ""
            text += f"📅 <b>{day_name}</b> в {schedule.time}{duration_text}\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить занятие", callback_data=f"schedule_add_student_{student_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def show_add_schedule_form(update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: int) -> int:
    """Показывает форму добавления занятия"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['schedule_student_id'] = student_id
    
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    keyboard = []
    
    for i, day in enumerate(days):
        keyboard.append([InlineKeyboardButton(day, callback_data=f"schedule_day_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"schedule_view_student_{student_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📅 Выберите день недели для занятия:",
        reply_markup=reply_markup
    )
    
    return SCHEDULE_CHOOSE_DAY

# Добавляем новые состояния для расписания
SCHEDULE_CHOOSE_DAY, SCHEDULE_ENTER_TIME, SCHEDULE_ENTER_DURATION = range(4000, 4003)

# Добавляем состояния для редактирования расписания
SCHEDULE_EDIT_CHOOSE_PARAM, SCHEDULE_EDIT_DAY, SCHEDULE_EDIT_TIME, SCHEDULE_EDIT_DURATION = range(4003, 4007)

async def handle_schedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод времени занятия"""
    time_str = update.message.text.strip()
    
    # Проверяем формат времени
    try:
        hours, minutes = map(int, time_str.split(':'))
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError("Invalid time")
    except:
        await update.message.reply_text(
            "❌ Неверный формат времени!\n\n"
            "Введите время в формате ЧЧ:ММ\n"
            "Например: 14:30, 09:15, 18:45",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return SCHEDULE_ENTER_TIME
    
    context.user_data['schedule_time'] = time_str
    
    await update.message.reply_text(
        "⏱️ Введите длительность занятия в минутах (по умолчанию 60):",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("60 минут", callback_data="schedule_duration_60")],
            [InlineKeyboardButton("90 минут", callback_data="schedule_duration_90")],
            [InlineKeyboardButton("120 минут", callback_data="schedule_duration_120")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")]
        ])
    )
    return SCHEDULE_ENTER_DURATION

async def handle_schedule_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод длительности занятия"""
    if update.callback_query:
        # Если выбрана кнопка с предустановленной длительностью
        duration = int(update.callback_query.data.split("_")[-1])
        await update.callback_query.answer()
    else:
        # Если введена длительность вручную
        try:
            duration = int(update.message.text.strip())
            if duration <= 0 or duration > 480:  # Максимум 8 часов
                raise ValueError("Invalid duration")
        except:
            await update.message.reply_text(
                "❌ Неверная длительность!\n\n"
                "Введите число от 1 до 480 минут.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
                ]])
            )
            return SCHEDULE_ENTER_DURATION
    
    # Сохраняем данные и добавляем занятие
    student_id = context.user_data.get('schedule_student_id')
    day_of_week = context.user_data.get('schedule_day')
    time_str = context.user_data.get('schedule_time')
    
    if not all([student_id, day_of_week is not None, time_str]):
        await (update.callback_query.edit_message_text if update.callback_query else update.message.reply_text)(
            "❌ Ошибка: не все данные заполнены.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return ConversationHandler.END
    
    db = context.bot_data['db']
    success = db.add_schedule(student_id, day_of_week, time_str, duration)
    
    if success:
        student = db.get_student_by_id(student_id)
        display_name = student.display_name or student.name
        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        day_name = days[day_of_week]
        
        await (update.callback_query.edit_message_text if update.callback_query else update.message.reply_text)(
            f"✅ Занятие успешно добавлено!\n\n"
            f"👤 Студент: {display_name}\n"
            f"📅 День: {day_name}\n"
            f"⏰ Время: {time_str}\n"
            f"⏱️ Длительность: {duration} минут",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Добавить еще", callback_data=f"schedule_add_student_{student_id}")],
                [InlineKeyboardButton("📅 Просмотреть расписание", callback_data=f"schedule_view_student_{student_id}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")]
            ])
        )
    else:
        await (update.callback_query.edit_message_text if update.callback_query else update.message.reply_text)(
            "❌ Ошибка: занятие в это время уже существует.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
    
    # Очищаем временные данные
    context.user_data.pop('schedule_student_id', None)
    context.user_data.pop('schedule_day', None)
    context.user_data.pop('schedule_time', None)
    
    return ConversationHandler.END

async def show_schedule_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: int) -> None:
    """Показывает меню редактирования расписания студента"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    student = db.get_student_by_id(student_id)
    schedules = db.get_student_schedule(student_id)
    
    if not student:
        await query.edit_message_text(
            "❌ Студент не найден.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return
    
    if not schedules:
        await query.edit_message_text(
            "❌ У студента нет занятий в расписании.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return
    
    display_name = student.display_name or student.name
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    
    keyboard = []
    for schedule in schedules:
        day_name = days[schedule.day_of_week]
        duration_text = f" ({schedule.duration} мин)" if schedule.duration != 60 else ""
        button_text = f"✏️ {day_name} в {schedule.time}{duration_text}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"schedule_edit_{schedule.id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✏️ <b>Редактирование расписания {display_name}</b>\n\n"
        f"Выберите занятие для редактирования:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def show_schedule_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, student_id: int) -> None:
    """Показывает меню удаления расписания студента"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    student = db.get_student_by_id(student_id)
    schedules = db.get_student_schedule(student_id)
    
    if not student:
        await query.edit_message_text(
            "❌ Студент не найден.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return
    
    if not schedules:
        await query.edit_message_text(
            "❌ У студента нет занятий в расписании.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return
    
    display_name = student.display_name or student.name
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    
    keyboard = []
    for schedule in schedules:
        day_name = days[schedule.day_of_week]
        duration_text = f" ({schedule.duration} мин)" if schedule.duration != 60 else ""
        button_text = f"❌ {day_name} в {schedule.time}{duration_text}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"schedule_delete_{schedule.id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"❌ <b>Удаление занятий {display_name}</b>\n\n"
        f"Выберите занятие для удаления:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def show_schedule_edit_form(update: Update, context: ContextTypes.DEFAULT_TYPE, schedule_id: int) -> None:
    """Показывает форму редактирования занятия"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    session = db.Session()
    
    try:
        schedule = session.query(Schedule).filter_by(id=schedule_id).first()
        if not schedule:
            await query.edit_message_text(
                "❌ Занятие не найдено.",
                reply_markup=InlineKeyboardMarkup([[\
                    InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
                ]])
            )
            return
        
        student = db.get_student_by_id(schedule.student_id)
        display_name = student.display_name or student.name
        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        day_name = days[schedule.day_of_week]

        # Сохраняем id редактируемого занятия
        context.user_data['edit_schedule_id'] = schedule_id
        
        keyboard = [
            [
                InlineKeyboardButton("День недели", callback_data="edit_schedule_day"),
                InlineKeyboardButton("Время", callback_data="edit_schedule_time"),
                InlineKeyboardButton("Длительность", callback_data="edit_schedule_duration")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")]
        ]
        
        await query.edit_message_text(
            f"✏️ <b>Редактирование занятия</b>\n\n"
            f"👤 Студент: {display_name}\n"
            f"📅 День: {day_name}\n"
            f"⏰ Время: {schedule.time}\n"
            f"⏱️ Длительность: {schedule.duration} минут\n\n"
            f"Выберите, что хотите изменить:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    finally:
        session.close()

async def handle_schedule_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, schedule_id: int) -> None:
    """Обрабатывает удаление занятия"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    session = db.Session()
    
    try:
        schedule = session.query(Schedule).filter_by(id=schedule_id).first()
        if not schedule:
            await query.edit_message_text(
                "❌ Занятие не найдено.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
                ]])
            )
            return
        
        student = db.get_student_by_id(schedule.student_id)
        display_name = student.display_name or student.name
        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        day_name = days[schedule.day_of_week]
        
        # Удаляем занятие
        success = db.delete_schedule(schedule_id)
        
        if success:
            await query.edit_message_text(
                f"✅ Занятие успешно удалено!\n\n"
                f"👤 Студент: {display_name}\n"
                f"📅 День: {day_name}\n"
                f"⏰ Время: {schedule.time}\n"
                f"⏱️ Длительность: {schedule.duration} минут",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📅 Управление расписанием", callback_data="admin_schedule")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
                ])
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка при удалении занятия.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
                ]])
            )
    finally:
        session.close()

async def show_schedule_edit_day_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает форму выбора нового дня недели для редактирования"""
    query = update.callback_query
    await query.answer()
    
    schedule_id = context.user_data.get('edit_schedule_id')
    if not schedule_id:
        await query.edit_message_text(
            "❌ Ошибка: занятие не выбрано.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return ConversationHandler.END
    
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    keyboard = []
    
    for i, day in enumerate(days):
        keyboard.append([InlineKeyboardButton(day, callback_data=f"edit_schedule_day_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📅 Выберите новый день недели для занятия:",
        reply_markup=reply_markup
    )
    
    return SCHEDULE_EDIT_DAY

async def show_schedule_edit_time_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает форму ввода нового времени для редактирования"""
    query = update.callback_query
    await query.answer()
    
    schedule_id = context.user_data.get('edit_schedule_id')
    if not schedule_id:
        await query.edit_message_text(
            "❌ Ошибка: занятие не выбрано.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return ConversationHandler.END
    
    await query.edit_message_text(
        "⏰ Введите новое время занятия в формате ЧЧ:ММ (например, 14:30):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
        ]])
    )
    
    return SCHEDULE_EDIT_TIME

async def show_schedule_edit_duration_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает форму выбора новой длительности для редактирования"""
    query = update.callback_query
    await query.answer()
    
    schedule_id = context.user_data.get('edit_schedule_id')
    if not schedule_id:
        await query.edit_message_text(
            "❌ Ошибка: занятие не выбрано.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return ConversationHandler.END
    
    await query.edit_message_text(
        "⏱️ Выберите новую длительность занятия:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("60 минут", callback_data="edit_schedule_duration_60")],
            [InlineKeyboardButton("90 минут", callback_data="edit_schedule_duration_90")],
            [InlineKeyboardButton("120 минут", callback_data="edit_schedule_duration_120")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")]
        ])
    )
    
    return SCHEDULE_EDIT_DURATION

async def handle_schedule_edit_day(update: Update, context: ContextTypes.DEFAULT_TYPE, day_of_week: int) -> int:
    """Обрабатывает изменение дня недели занятия"""
    query = update.callback_query
    await query.answer()
    
    schedule_id = context.user_data.get('edit_schedule_id')
    if not schedule_id:
        await query.edit_message_text(
            "❌ Ошибка: занятие не выбрано.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return ConversationHandler.END
    
    db = context.bot_data['db']
    success = db.update_schedule(schedule_id, day_of_week=day_of_week)
    
    if success:
        # Получаем обновленное занятие для отображения
        session = db.Session()
        try:
            schedule = session.query(Schedule).filter_by(id=schedule_id).first()
            student = db.get_student_by_id(schedule.student_id)
            display_name = student.display_name or student.name
            days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            day_name = days[day_of_week]
            # Отправляем уведомление об изменении дня
            asyncio.create_task(send_schedule_change_notification(context, student, schedule, changed_fields=['day']))
            
            # Перепланировать напоминания для ученика
            plan_schedule_reminders_for_student(context.job_queue, db, schedule.student_id)
            
            await query.edit_message_text(
                f"✅ День недели успешно изменен!\n\n"
                f"👤 Студент: {display_name}\n"
                f"📅 Новый день: {day_name}\n"
                f"⏰ Время: {schedule.time}\n"
                f"⏱️ Длительность: {schedule.duration} минут",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📅 Управление расписанием", callback_data="admin_schedule")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
                ])
            )
        finally:
            session.close()
    else:
        await query.edit_message_text(
            "❌ Ошибка: занятие в это время в выбранный день уже существует.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
    
    # Очищаем временные данные
    context.user_data.pop('edit_schedule_id', None)
    return ConversationHandler.END

async def handle_schedule_edit_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод нового времени занятия"""
    time_str = update.message.text.strip()
    
    # Проверяем формат времени
    try:
        hours, minutes = map(int, time_str.split(':'))
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError("Invalid time")
    except:
        await update.message.reply_text(
            "❌ Неверный формат времени!\n\n"
            "Введите время в формате ЧЧ:ММ\n"
            "Например: 14:30, 09:15, 18:45",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return SCHEDULE_EDIT_TIME
    
    schedule_id = context.user_data.get('edit_schedule_id')
    if not schedule_id:
        await update.message.reply_text(
            "❌ Ошибка: занятие не выбрано.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return ConversationHandler.END
    
    db = context.bot_data['db']
    success = db.update_schedule(schedule_id, time=time_str)
    
    if success:
        # Получаем обновленное занятие для отображения
        session = db.Session()
        try:
            schedule = session.query(Schedule).filter_by(id=schedule_id).first()
            student = db.get_student_by_id(schedule.student_id)
            display_name = student.display_name or student.name
            days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            day_name = days[schedule.day_of_week]
            # Отправляем уведомление об изменении времени
            asyncio.create_task(send_schedule_change_notification(context, student, schedule, changed_fields=['time']))
            
            # Перепланировать напоминания для ученика
            plan_schedule_reminders_for_student(context.job_queue, db, schedule.student_id)
            
            await update.message.reply_text(
                f"✅ Время успешно изменено!\n\n"
                f"👤 Студент: {display_name}\n"
                f"📅 День: {day_name}\n"
                f"⏰ Новое время: {time_str}\n"
                f"⏱️ Длительность: {schedule.duration} минут",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📅 Управление расписанием", callback_data="admin_schedule")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
                ])
            )
        finally:
            session.close()
    else:
        await update.message.reply_text(
            "❌ Ошибка: занятие в это время в этот день уже существует.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
    
    # Очищаем временные данные
    context.user_data.pop('edit_schedule_id', None)
    return ConversationHandler.END

async def handle_schedule_edit_duration(update: Update, context: ContextTypes.DEFAULT_TYPE, duration: int) -> int:
    """Обрабатывает изменение длительности занятия"""
    query = update.callback_query
    await query.answer()
    
    schedule_id = context.user_data.get('edit_schedule_id')
    if not schedule_id:
        await query.edit_message_text(
            "❌ Ошибка: занятие не выбрано.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
        return ConversationHandler.END
    
    db = context.bot_data['db']
    success = db.update_schedule(schedule_id, duration=duration)
    
    if success:
        # Получаем обновленное занятие для отображения
        session = db.Session()
        try:
            schedule = session.query(Schedule).filter_by(id=schedule_id).first()
            student = db.get_student_by_id(schedule.student_id)
            display_name = student.display_name or student.name
            days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            day_name = days[schedule.day_of_week]
            
            await query.edit_message_text(
                f"✅ Длительность успешно изменена!\n\n"
                f"👤 Студент: {display_name}\n"
                f"📅 День: {day_name}\n"
                f"⏰ Время: {schedule.time}\n"
                f"⏱️ Новая длительность: {duration} минут",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📅 Управление расписанием", callback_data="admin_schedule")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
                ])
            )
        finally:
            session.close()
    else:
        await query.edit_message_text(
            "❌ Ошибка при изменении длительности.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")
            ]])
        )
    
    # Очищаем временные данные
    context.user_data.pop('edit_schedule_id', None)
    return ConversationHandler.END

async def send_schedule_change_notification(context, student, schedule, changed_fields):
    """Отправляет уведомление ученику об изменении расписания (день или время)"""
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    day_name = days[schedule.day_of_week]
    
    # Формируем текст уведомления
    text = f"⚠️ Ваше занятие изменено!\n"
    if 'day' in changed_fields:
        text += f"Новый день: {day_name}\n"
    if 'time' in changed_fields:
        text += f"Новое время: {schedule.time}\n"
    text += f"\nПожалуйста, проверьте расписание в меню."
    
    # Добавляем уведомление в базу данных
    db = context.bot_data['db']
    db.add_notification(student.id, 'schedule', text)
    
    # Отправляем push-сообщение над меню
    try:
        msg = await context.bot.send_message(
            chat_id=student.telegram_id,
            text="🔔 У вас новое уведомление! Откройте меню 'Уведомления'."
        )
        db.add_push_message(student.id, msg.message_id)
        
        # Обновляем меню с новым счётчиком уведомлений
        await send_student_menu_by_chat_id(context, student.telegram_id)
    except Exception:
        pass

def plan_schedule_reminders_for_student(job_queue, db, student_id, tz_str='Europe/Moscow'):
    """Планирует напоминания за 15 минут до каждого занятия ученика на ближайшую неделю"""
    student = db.get_student_by_id(student_id)
    if not student:
        return
    schedules = db.get_student_schedule(student_id)
    tz = pytz.timezone(tz_str)
    now = datetime.now(tz)
    for schedule in schedules:
        # Определяем дату ближайшего занятия
        lesson_time = datetime.strptime(schedule.time, '%H:%M').time()
        # Определяем ближайший день недели
        days_ahead = (schedule.day_of_week - now.weekday()) % 7
        lesson_date = (now + timedelta(days=days_ahead)).date()
        lesson_dt = tz.localize(datetime.combine(lesson_date, lesson_time))
        # Если занятие уже прошло сегодня, берем на следующей неделе
        if lesson_dt < now:
            lesson_dt += timedelta(days=7)
        # Время напоминания
        reminder_dt = lesson_dt - timedelta(minutes=15)
        # Не планируем напоминание в прошлом
        if reminder_dt < now:
            continue
        # Планируем задачу
        job_queue.run_once(
            send_schedule_reminder,
            when=(reminder_dt - now).total_seconds(),
            data={
                'student_id': student_id,
                'schedule': {
                    'day_of_week': schedule.day_of_week,
                    'time': schedule.time,
                    'duration': schedule.duration
                }
            },
            name=f"reminder_{student_id}_{schedule.id}_{reminder_dt.strftime('%Y%m%d%H%M')}"
        )

async def send_schedule_reminder(context):
    """Отправляет напоминание о занятии за 15 минут до начала над меню и сохраняет его как push-уведомление, удаляя предыдущие напоминания"""
    job = context.job
    student_id = job.data['student_id']
    schedule = job.data['schedule']
    db = context.bot_data['db']
    student = db.get_student_by_id(student_id)
    if not student or not student.telegram_id:
        return
    
    # Формируем простой текст напоминания
    text = "⏰ Через 15 минут начинается занятие!"
    
    # Добавляем ссылку на подключение, если она есть
    if student.lesson_link:
        text += f"\n\n🔗 <a href='{student.lesson_link}'>Подключиться</a>"
    
    try:
        # Удаляем старое меню, если есть
        last_menu_id = db.get_student_menu_message_id(student.id)
        if last_menu_id:
            try:
                await context.bot.delete_message(chat_id=student.telegram_id, message_id=last_menu_id)
            except Exception:
                pass
        # Удаляем все предыдущие push-напоминания (push_messages)
        push_msgs = db.get_push_messages(student.id)
        for push in push_msgs:
            try:
                await context.bot.delete_message(chat_id=student.telegram_id, message_id=push.message_id)
            except Exception:
                pass
        db.clear_push_messages(student.id)
        # Отправляем напоминание
        msg = await context.bot.send_message(
            chat_id=student.telegram_id,
            text=text,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        db.add_push_message(student.id, msg.message_id)
        # Отправляем новое меню
        await send_student_menu_by_chat_id(context, student.telegram_id)
    except Exception:
        pass

# Локальная функция для отправки меню студента
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
        except Exception as e:
            pass
    
    unread_count = len(db.get_notifications(student.id, only_unread=True))
    
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
    msg = await context.bot.send_message(chat_id=chat_id, text=greeting, reply_markup=reply_markup)
    db.update_student_menu_message_id(student.id, msg.message_id)

# --- Обработчики настроек переносов ---
async def show_reschedule_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню настроек переносов"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    settings = db.get_reschedule_settings()
    
    # Форматируем доступные дни
    days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    available_days = [int(d) for d in settings.available_days.split(',')]
    days_text = ' '.join([days[i] for i in available_days])
    
    text = (
        "⚙️ <b>Настройки переносов</b>\n\n"
        f"🕐 Рабочие часы: {settings.work_start_time} - {settings.work_end_time}\n"
        f"📅 Доступные дни: {days_text}\n"
        f"⏱️ Интервал слотов: {settings.slot_interval} мин\n\n"
        "Выберите, что хотите изменить:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🕐 Рабочие часы", callback_data="reschedule_settings_hours")],
        [InlineKeyboardButton("📅 Доступные дни", callback_data="reschedule_settings_days")],
        [InlineKeyboardButton("⏱️ Интервал слотов", callback_data="reschedule_settings_interval")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_schedule")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def show_reschedule_hours_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает настройки рабочих часов"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    settings = db.get_reschedule_settings()
    
    text = (
        "🕐 <b>Настройка рабочих часов</b>\n\n"
        f"Текущие часы: {settings.work_start_time} - {settings.work_end_time}\n\n"
        "Выберите время начала работы:"
    )
    
    # Кнопки для выбора времени начала
    start_times = ["08:00", "09:00", "10:00", "11:00", "12:00"]
    keyboard = []
    for i in range(0, len(start_times), 2):
        row = []
        row.append(InlineKeyboardButton(start_times[i], callback_data=f"reschedule_start_{start_times[i]}"))
        if i + 1 < len(start_times):
            row.append(InlineKeyboardButton(start_times[i + 1], callback_data=f"reschedule_start_{start_times[i + 1]}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="reschedule_settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def show_reschedule_end_hours_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает настройки времени окончания работы"""
    query = update.callback_query
    await query.answer()
    
    start_time = query.data.split('_')[-1]
    context.user_data['reschedule_start_time'] = start_time
    
    text = (
        "🕐 <b>Настройка рабочих часов</b>\n\n"
        f"Время начала: {start_time}\n"
        "Выберите время окончания работы:"
    )
    
    # Кнопки для выбора времени окончания
    end_times = ["17:00", "18:00", "19:00", "20:00", "21:00", "22:00"]
    keyboard = []
    for i in range(0, len(end_times), 2):
        row = []
        row.append(InlineKeyboardButton(end_times[i], callback_data=f"reschedule_end_{end_times[i]}"))
        if i + 1 < len(end_times):
            row.append(InlineKeyboardButton(end_times[i + 1], callback_data=f"reschedule_end_{end_times[i + 1]}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="reschedule_settings_hours")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def save_reschedule_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сохраняет настройки рабочих часов"""
    query = update.callback_query
    await query.answer()
    
    start_time = context.user_data.get('reschedule_start_time')
    end_time = query.data.split('_')[-1]
    
    db = context.bot_data['db']
    success = db.update_reschedule_settings(work_start_time=start_time, work_end_time=end_time)
    
    if success:
        await query.answer("✅ Рабочие часы обновлены!")
    else:
        await query.answer("❌ Ошибка при обновлении!")
    
    await show_reschedule_settings(update, context)

async def show_reschedule_days_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает настройки доступных дней"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    settings = db.get_reschedule_settings()
    available_days = [int(d) for d in settings.available_days.split(',')]
    
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    
    text = "📅 <b>Настройка доступных дней</b>\n\nВыберите дни, доступные для переноса:"
    
    keyboard = []
    for i, day in enumerate(days):
        status = "✅" if i in available_days else "❌"
        keyboard.append([InlineKeyboardButton(f"{status} {day}", callback_data=f"reschedule_day_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="reschedule_settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def toggle_reschedule_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Переключает доступность дня"""
    query = update.callback_query
    await query.answer()
    
    day = int(query.data.split('_')[-1])
    db = context.bot_data['db']
    settings = db.get_reschedule_settings()
    available_days = [int(d) for d in settings.available_days.split(',')]
    
    if day in available_days:
        available_days.remove(day)
    else:
        available_days.append(day)
    
    available_days.sort()
    new_days_str = ','.join(map(str, available_days))
    
    success = db.update_reschedule_settings(available_days=new_days_str)
    
    if success:
        await show_reschedule_days_settings(update, context)
    else:
        await query.answer("❌ Ошибка при обновлении!")

async def show_reschedule_interval_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает настройки интервала слотов"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    settings = db.get_reschedule_settings()
    
    text = (
        "⏱️ <b>Настройка интервала слотов</b>\n\n"
        f"Текущее значение: {settings.slot_interval} минут\n\n"
        "Выберите новый интервал:"
    )
    
    keyboard = [
        [InlineKeyboardButton("15 минут", callback_data="reschedule_interval_15")],
        [InlineKeyboardButton("30 минут", callback_data="reschedule_interval_30")],
        [InlineKeyboardButton("45 минут", callback_data="reschedule_interval_45")],
        [InlineKeyboardButton("60 минут", callback_data="reschedule_interval_60")],
        [InlineKeyboardButton("🔙 Назад", callback_data="reschedule_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def save_reschedule_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сохраняет настройки интервала слотов"""
    query = update.callback_query
    await query.answer()
    
    interval = int(query.data.split('_')[-1])
    db = context.bot_data['db']
    success = db.update_reschedule_settings(slot_interval=interval)
    
    if success:
        await query.answer("✅ Интервал слотов обновлен!")
    else:
        await query.answer("❌ Ошибка при обновлении!")
    
    await show_reschedule_settings(update, context)

async def send_admin_menu_by_chat_id(context, chat_id):
    db = context.bot_data['db']
    admin = db.get_admin_by_telegram_id(chat_id) if hasattr(db, 'get_admin_by_telegram_id') else None
    if not admin:
        return
    # Удаляем предыдущее меню, если оно есть
    last_menu_id = db.get_admin_menu_message_id(admin.id) if hasattr(db, 'get_admin_menu_message_id') else None
    if last_menu_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_menu_id)
        except Exception:
            pass

    # Получаем количество непрочитанных уведомлений
    unread_count = len(db.get_admin_notifications(admin.id, only_unread=True))
    notif_text = f"🔔 Уведомления ({unread_count})" if unread_count else "🔔 Уведомления"
    
    # Формируем клавиатуру меню
    keyboard = [
        [InlineKeyboardButton("🎯 Выдать домашнее задание", callback_data="admin_give_homework")],
        [InlineKeyboardButton("👥 Управление учениками", callback_data="admin_students"),
         InlineKeyboardButton("📚 Управление заданиями", callback_data="admin_homework")],
        [InlineKeyboardButton("📝 Управление конспектами", callback_data="admin_notes"),
         InlineKeyboardButton("📅 Управление расписанием", callback_data="admin_schedule")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
         InlineKeyboardButton(notif_text, callback_data="admin_notifications")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text="🔑 Панель управления администратора\nВыберите раздел:",
        reply_markup=reply_markup
    )
    if hasattr(db, 'update_admin_menu_message_id'):
        db.update_admin_menu_message_id(admin.id, msg.message_id)

async def show_admin_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает уведомления администратора"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    user_id = query.from_user.id
    admin = db.get_admin_by_telegram_id(user_id)
    
    if not admin:
        await query.edit_message_text(
            text="❌ Администратор не найден.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
        )
        return
    
    # Сброс страницы при открытии уведомлений
    context.user_data['admin_notif_page'] = 0
    notifications = db.get_admin_notifications(admin.id)
    
    if not notifications:
        await query.edit_message_text(
            text="🔔 Нет новых уведомлений.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
        )
        return
    
    # Пагинация: показываем только 5 последних уведомлений
    page = int(context.user_data.get('admin_notif_page', 0))
    per_page = 5
    total = len(notifications)
    max_page = (total + per_page - 1) // per_page - 1
    page_notifications = notifications[page * per_page:min(page * per_page + per_page, total)]
    
    notif_texts = []
    for i, notif in enumerate(page_notifications, 1):
        status = "🆕 " if not notif.is_read else "📋 "
        dt = notif.created_at.strftime('%d.%m.%Y %H:%M')
        
        # Тип уведомления на кириллице с эмодзи
        if notif.type == 'reschedule':
            notif_type = "🔄 Запрос на перенос"
        elif notif.type == 'homework':
            notif_type = "📚 Домашнее задание"
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
    db.mark_admin_notifications_read(admin.id)
    buttons = []
    
    # Показываем навигацию только если есть больше одной страницы
    if max_page > 0:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️", callback_data="admin_notif_prev"))
        nav_row.append(InlineKeyboardButton(f"{page+1}/{max_page+1}", callback_data="noop"))
        if page < max_page:
            nav_row.append(InlineKeyboardButton("▶️", callback_data="admin_notif_next"))
        buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton("🗑️ Очистить все", callback_data="admin_notif_clear")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
    
    # Красивый заголовок с информацией о страницах
    header = f"🔔 <b>Уведомления администратора</b>\n"
    header += f"📊 Всего: {total}\n"
    header += "─────────────\n\n"
    
    await query.edit_message_text(
        text=header + text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def handle_admin_notification_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает действия с уведомлениями администратора"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    user_id = query.from_user.id
    admin = db.get_admin_by_telegram_id(user_id)
    
    if not admin:
        return
    
    if query.data == "admin_notif_prev":
        context.user_data['admin_notif_page'] = max(0, context.user_data.get('admin_notif_page', 0) - 1)
        await show_admin_notifications(update, context)
    elif query.data == "admin_notif_next":
        context.user_data['admin_notif_page'] = context.user_data.get('admin_notif_page', 0) + 1
        await show_admin_notifications(update, context)
    elif query.data == "admin_notif_clear":
        # Удаляем все уведомления администратора
        db.clear_admin_notifications(admin.id)
        # Удаляем все push-уведомления из чата
        push_msgs = db.get_admin_push_messages(admin.id)
        for push in push_msgs:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=push.message_id)
            except Exception:
                pass  # Игнорируем ошибки (например, если сообщение уже удалено)
        db.clear_admin_push_messages(admin.id)
        context.user_data['admin_notif_page'] = 0
        await query.edit_message_text(
            text="🔔 Все уведомления удалены!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
        )

async def show_task_status_menu(update, context, student_id, task_num):
    """Показывает меню смены статуса задания для администратора"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    query = update.callback_query
    # Кнопки статусов
    keyboard = [
        [
            InlineKeyboardButton("✅ Пройдено", callback_data=f"edit_task_status_set_{student_id}_{task_num}_completed"),
            InlineKeyboardButton("🔄 В процессе", callback_data=f"edit_task_status_set_{student_id}_{task_num}_in_progress"),
            InlineKeyboardButton("❌ Не пройдено", callback_data=f"edit_task_status_set_{student_id}_{task_num}_not_completed"),
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"edit_task_status_{student_id}")]
    ]
    await query.edit_message_text(
        text=f"Выберите новый статус для задания {task_num}:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return

async def show_task_status_set(update, context, student_id, task_num):
    """Обрабатывает выбор статуса задания"""
    query = update.callback_query
    await query.answer()
    status = query.data.split('_')[-1]
    db = context.bot_data['db']
    student = db.get_student_by_id(student_id)
    if student:
        db.update_homework_status(student.id, task_num, status)
        await query.edit_message_text(
            f"Статус задания {task_num} успешно изменен на: {status}"
        )
    else:
        await query.edit_message_text(
            "❌ Студент не найден."
        )
    return ConversationHandler.END