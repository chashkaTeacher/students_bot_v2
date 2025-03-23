from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from core.database import ExamType

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

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> None:
    """Показывает меню администратора"""
    keyboard = [
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
    link = update.message.text
    user_id = update.effective_user.id
    
    if user_id not in student_data:
        await update.message.reply_text("❌ Ошибка: данные о студенте не найдены. Начните сначала.")
        await admin_menu(update, context)
        return ConversationHandler.END
    
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
    await query.answer()
    
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
    elif query.data == "admin_notes":
        await notes_menu(update, context)
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
        for student in students:
            note_text = f" ({student.notes})" if student.notes else ""
            keyboard.append([InlineKeyboardButton(
                f"👤 {student.name}{note_text}",
                callback_data=f"student_info_{student.id}"
            )])
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
        for student in students:
            note_text = f" ({student.notes})" if student.notes else ""
            keyboard.append([InlineKeyboardButton(
                f"❌ {student.name}{note_text}",
                callback_data=f"delete_{student.id}"
            )])
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
        for student in students:
            note_text = f" ({student.notes})" if student.notes else ""
            keyboard.append([InlineKeyboardButton(
                f"✏️ {student.name}{note_text}",
                callback_data=f"edit_student_{student.id}"
            )])
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
    new_link = update.message.text
    
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
        context.bot_data['db'].update_student_exam_type(student_id, ExamType[exam_type])
        await query.message.edit_text("✅ Тип экзамена успешно изменен!")
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