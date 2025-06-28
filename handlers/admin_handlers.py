from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from core.database import Database, ExamType, PendingNoteAssignment
from handlers.student_handlers import student_menu, send_student_menu_by_chat_id
import os
import uuid

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

# Новые состояния для школьной программы
SCHOOL_HOMEWORK_CHOICE, SCHOOL_HOMEWORK_TITLE, SCHOOL_HOMEWORK_LINK, SCHOOL_HOMEWORK_FILE, SCHOOL_NOTE_CHOICE, SCHOOL_NOTE_TITLE, SCHOOL_NOTE_LINK, SCHOOL_NOTE_FILE = range(103, 111)

give_homework_temp = {}

GIVE_VARIANT_CHOOSE_EXAM, GIVE_VARIANT_ENTER_LINK = 200, 201

give_variant_temp = {}

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> None:
    """Показывает меню администратора"""
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
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
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
            InlineKeyboardButton("📚 ЕГЭ", callback_data="student_exam_EGE")
        ],
        [InlineKeyboardButton("🏫 Школьная программа", callback_data="student_exam_SCHOOL")],
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
        "Отправьте ссылку на профиль ученика:",
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
    
    # Обрабатываем возможную ошибку устаревшего callback query
    try:
        await query.answer()
    except Exception as e:
        # Игнорируем ошибку устаревшего query
        pass
    
    action = query.data
    
    if action.startswith("edit_name_"):
        student_id = int(action.split("_")[-1])
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
        
    elif action.startswith("edit_link_"):
        student_id = int(action.split("_")[-1])
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
    elif query.data == "admin_give_homework_task":
        from handlers.homework_handlers import show_homework_menu
        await show_homework_menu(update, context)
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
                InlineKeyboardButton("ОГЭ", callback_data="info_type_OGE"),
                InlineKeyboardButton("ЕГЭ", callback_data="info_type_EGE")
            ],
            [
                InlineKeyboardButton("Школьная программа", callback_data="info_type_SCHOOL")
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
        
        await query.message.edit_text(
            f"👤 Информация о студенте:\n\n"
            f"📝 Имя: {student.name}\n"
            f"📚 Экзамен: {student.exam_type.value}\n"
            f"🆔 Telegram ID: {student.telegram_id or 'Не привязан'}\n"
            f"🔗 Ссылка на занятие: {student.lesson_link or 'Не указана'}\n"
            f"📝 Заметки: {student.notes or 'Нет заметок'}",
            reply_markup=reply_markup
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
                InlineKeyboardButton("ОГЭ", callback_data="delete_type_OGE"),
                InlineKeyboardButton("ЕГЭ", callback_data="delete_type_EGE")
            ],
            [
                InlineKeyboardButton("Школьная программа", callback_data="delete_type_SCHOOL")
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
                InlineKeyboardButton("ОГЭ", callback_data="edit_type_OGE"),
                InlineKeyboardButton("ЕГЭ", callback_data="edit_type_EGE")
            ],
            [
                InlineKeyboardButton("Школьная программа", callback_data="edit_type_SCHOOL")
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
                InlineKeyboardButton("📚 Изменить экзамен", callback_data=f"edit_exam_{student_id}")
            ],
            [
                InlineKeyboardButton("🔗 Изменить ссылку", callback_data=f"edit_link_{student_id}"),
                InlineKeyboardButton("📝 Добавить заметку", callback_data=f"add_note_{student_id}")
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
        back_cb = "admin_give_homework" if pending and pending.origin == 'give_homework' else "admin_check_unassigned_notes"
        await query.edit_message_text("✅ Домашнее задание выдано без конспекта", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=back_cb)]]))
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
            InlineKeyboardButton("📚 ЕГЭ", callback_data=f"student_new_exam_EGE")
        ],
        [InlineKeyboardButton("🏫 Школьная программа", callback_data=f"student_new_exam_SCHOOL")],
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

async def give_homework_menu(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> None:
    """Меню выдачи домашнего задания или варианта"""
    keyboard = [
        [
            InlineKeyboardButton("👤 Ученику", callback_data="admin_give_homework_task"),
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

async def handle_give_homework_variant(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> int:
    keyboard = [
        [InlineKeyboardButton("📝 ОГЭ", callback_data="give_variant_exam_OGE"), InlineKeyboardButton("📚 ЕГЭ", callback_data="give_variant_exam_EGE")],
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
            InlineKeyboardButton("📚 ЕГЭ", callback_data="give_hw_exam_EGE")
        ],
        [InlineKeyboardButton("🏫 Школьная программа", callback_data="give_hw_exam_SCHOOL")],
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
                    print(f"Ошибка push студенту {student.id}: {e}")
        
        # Предлагаем конспекты для выдачи
        await suggest_notes_for_homework(update, context, homework, student)
        return ConversationHandler.END
    
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
                        await send_student_menu_by_chat_id(context, student.telegram_id)
                    except Exception as e:
                        print(f"Ошибка push студенту {student.id}: {e}")
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