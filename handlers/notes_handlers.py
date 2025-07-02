from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from core.database import Database, ExamType, is_valid_url
from telegram.error import BadRequest
from handlers.admin_handlers import admin_menu
import os
from datetime import datetime
import logging

# Состояния для ConversationHandler
CHOOSE_EXAM, ENTER_TITLE, ENTER_LINK, CONFIRM_DELETE, SELECT_NOTE, EDIT_TITLE, EDIT_LINK, ASK_FOR_FILE, WAIT_FOR_FILE = range(9)

# Временное хранилище данных
temp_data = {}

# Создаем директории для файлов, если их нет
NOTES_FILES_DIR = "notes_files"

if not os.path.exists(NOTES_FILES_DIR):
    os.makedirs(NOTES_FILES_DIR)

async def safe_answer_query(query):
    """Безопасно отвечает на callback query, игнорируя ошибки устаревших запросов"""
    try:
        await query.answer()
    except Exception as e:
        # Игнорируем ошибку устаревшего query
        pass

async def show_notes_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает меню управления конспектами"""
    query = update.callback_query
    
    if query and query.data != "admin_notes":
        action = query.data.split("_")[1]  # notes_add -> add
        await safe_answer_query(query)
        return await show_exam_menu(update, context, action)
    
    keyboard = [
        [
            InlineKeyboardButton("📝 Добавить конспект", callback_data="notes_add"),
            InlineKeyboardButton("📋 Список конспектов", callback_data="notes_list")
        ],
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data="notes_edit"),
            InlineKeyboardButton("❌ Удалить", callback_data="notes_delete")
        ],
        [
            InlineKeyboardButton("🔍 Проверить невыданные", callback_data="admin_check_unassigned_notes")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            "📚 Управление конспектами\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "📚 Управление конспектами\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def show_exam_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> int:
    """Показывает меню выбора типа экзамена"""
    query = update.callback_query
    await safe_answer_query(query)
    
    user_id = update.effective_user.id
    temp_data[user_id] = {"action": action}
    
    keyboard = [
        [
            InlineKeyboardButton("📝 ОГЭ", callback_data="notes_exam_OGE"),
            InlineKeyboardButton("🎓 ЕГЭ", callback_data="notes_exam_EGE"),
            InlineKeyboardButton("📖 Школьная программа", callback_data="notes_exam_SCHOOL")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    actions = {
        "add": "добавления",
        "list": "просмотра",
        "edit": "редактирования",
        "delete": "удаления"
    }
    
    await query.edit_message_text(
        text=f"📚 Выберите тип экзамена для {actions.get(action, '')} конспектов:",
        reply_markup=reply_markup
    )
    
    return CHOOSE_EXAM

async def handle_exam_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор типа экзамена"""
    query = update.callback_query
    await safe_answer_query(query)
    
    user_id = update.effective_user.id
    exam_type = query.data.split("_")[-1]
    action = temp_data[user_id]["action"]
    temp_data[user_id]["exam_type"] = exam_type
    
    db = Database()
    
    if action == "add":
        await query.edit_message_text(
            text="📝 Введите название конспекта:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
            ]])
        )
        return ENTER_TITLE
    
    elif action in ["list", "edit", "delete"]:
        notes = db.get_notes_by_exam(exam_type)
        if not notes:
            await query.edit_message_text(
                text=f"❌ Нет конспектов для {ExamType[exam_type].value}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="admin_back")
                ]])
            )
            return ConversationHandler.END
        
        if action == "list":
            # Сохраняем список конспектов и текущую страницу
            temp_data[user_id]["notes"] = notes
            temp_data[user_id]["current_page"] = 0
            await show_notes_page(update, context, user_id)
            return SELECT_NOTE
        
        # Для edit и delete формируем клавиатуру по два конспекта в строку
        keyboard = []
        current_row = []
        
        for note in notes:
            icon = "✏️" if action == "edit" else "❌"
            button_text = f"{icon} {note.title}"
            button = InlineKeyboardButton(
                button_text, 
                callback_data=f"notes_{action}_{note.id}"
            )
            
            # Если название длиннее 15 символов, добавляем кнопку в новую строку
            if len(note.title) > 15:
                if current_row:  # Если есть незавершенная строка
                    keyboard.append(current_row)
                    current_row = []
                keyboard.append([button])  # Добавляем длинную кнопку в отдельную строку
            else:
                current_row.append(button)
                if len(current_row) == 2:  # Если в текущей строке две кнопки
                    keyboard.append(current_row)
                    current_row = []
        
        # Добавляем оставшиеся кнопки, если есть
        if current_row:
            keyboard.append(current_row)
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        actions = {
            "edit": "редактирования",
            "delete": "удаления"
        }
        
        await query.edit_message_text(
            text=f"📋 Список конспектов для {ExamType[exam_type].value}\n"
                 f"Выберите конспект для {actions.get(action, '')}:",
            reply_markup=reply_markup
        )
        return SELECT_NOTE if action in ["edit", "delete"] else ConversationHandler.END

async def handle_note_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия конспекта"""
    user_id = update.effective_user.id
    temp_data[user_id]["title"] = update.message.text
    
    await update.message.reply_text(
        text="🔗 Введите ссылку на конспект:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
        ]])
    )
    return ENTER_LINK

async def handle_note_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ссылки на конспект"""
    user_id = update.effective_user.id
    link = update.message.text.strip()
    
    # Валидация URL
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
    
    temp_data[user_id]["link"] = link
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="notes_file_yes"),
            InlineKeyboardButton("❌ Нет", callback_data="notes_file_no")
        ]
    ]
    
    await update.message.reply_text(
        text="📎 Хотите добавить файл к конспекту?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ASK_FOR_FILE

async def handle_file_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор загрузки файла"""
    query = update.callback_query
    await safe_answer_query(query)
    
    user_id = update.effective_user.id
    data = temp_data[user_id]
    
    if query.data == "notes_file_yes":
        await query.edit_message_text(
            text="📎 Отправьте файл с конспектом:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
            ]])
        )
        return WAIT_FOR_FILE
    else:
        # Сохраняем конспект без файла
        db = Database()
        success = db.add_note(data["title"], data["link"], data["exam_type"])
        
        if not success:
            await query.edit_message_text(
                text="❌ Ошибка при добавлении конспекта.\n"
                     "Возможно, конспект с таким названием уже существует.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                ]])
            )
            return ConversationHandler.END
        
        await query.edit_message_text(
            text="✅ Конспект успешно добавлен!\n\n"
                 f"📝 Название: {data['title']}\n"
                 f"📚 Экзамен: {ExamType[data['exam_type']].value}\n"
                 f"🔗 Ссылка: {data['link']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает загрузку файла при создании или редактировании конспекта"""
    user_id = update.effective_user.id
    
    if user_id not in temp_data:
        await update.message.reply_text(
            text="❌ Ошибка: данные о конспекте не найдены",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    data = temp_data[user_id]
    note_id = data.get("note_id")
    
    # Сохраняем файл с временной меткой
    file = update.message.document
    file_name = file.file_name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{timestamp}_{file_name}"
    file_path = os.path.join(NOTES_FILES_DIR, unique_filename)
    
    try:
        new_file = await file.get_file()
        await new_file.download_to_drive(file_path)
        
        db = context.bot_data['db']
        
        if not note_id:  # Если это создание нового конспекта
            success = db.add_note(
                data["title"],
                data["link"],
                data["exam_type"],
                file_path
            )
            
            if not success:
                if os.path.exists(file_path):
                    os.remove(file_path)
                await update.message.reply_text(
                    text="❌ Ошибка при добавлении конспекта.\n"
                         "Возможно, конспект с таким названием уже существует.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                    ]])
                )
                return ConversationHandler.END
            
            await update.message.reply_text(
                text="✅ Конспект успешно добавлен!\n\n"
                     f"📝 Название: {data['title']}\n"
                     f"📚 Экзамен: {ExamType[data['exam_type']].value}\n"
                     f"🔗 Ссылка: {data['link']}\n"
                     f"📎 Файл: {file_name}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                ]])
            )
            return ConversationHandler.END
        
        else:  # Если это редактирование существующего конспекта
            note = db.get_note_by_id(note_id)
            
            if not note:
                if os.path.exists(file_path):
                    os.remove(file_path)
                await update.message.reply_text(
                    text="❌ Ошибка: конспект не найден",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                    ]])
                )
                return ConversationHandler.END
            
            # Удаляем старый файл, если он существует
            if note.file_path and os.path.exists(note.file_path):
                try:
                    os.remove(note.file_path)
                except Exception as e:
                    logging.error(f"Ошибка при удалении старого файла: {e}")
            
            # Обновляем путь к файлу в базе данных
            success = db.update_note(
                note_id,
                title=note.title,
                link=note.link,
                exam_type=note.exam_type,
                file_path=file_path
            )
            
            if not success:
                if os.path.exists(file_path):
                    os.remove(file_path)
                await update.message.reply_text(
                    text="❌ Ошибка при сохранении файла в базе данных",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                    ]])
                )
                return ConversationHandler.END
            
            await update.message.reply_text(
                text=f"✅ Файл успешно добавлен к конспекту!\n\n"
                     f"📝 Название: {note.title}\n"
                     f"📎 Файл: {file_name}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                ]])
            )
            return ConversationHandler.END
            
    except Exception as e:
        logging.error(f"Ошибка при загрузке файла: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        await update.message.reply_text(
            text="❌ Ошибка при загрузке файла",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END

async def handle_note_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор конспекта для редактирования или удаления"""
    query = update.callback_query
    await safe_answer_query(query)
    
    action, note_id = query.data.split("_")[1:]
    user_id = update.effective_user.id
    temp_data[user_id]["note_id"] = int(note_id)
    
    db = context.bot_data['db']
    note = db.get_note_by_id(int(note_id))
    
    if action == "edit":
        keyboard = [
            [
                InlineKeyboardButton("📝 Изменить название", callback_data=f"notes_edit_title_{note_id}"),
                InlineKeyboardButton("🔗 Изменить ссылку", callback_data=f"notes_edit_link_{note_id}")
            ],
            [InlineKeyboardButton("📎 Добавить файл", callback_data=f"notes_edit_file_{note_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
        ]
        
        file_info = ""
        if note.file_path:
            file_name = os.path.basename(note.file_path)
            file_info = f"📎 Файл: {file_name}\n"
        
        await query.edit_message_text(
            text=f"✏️ Редактирование конспекта:\n\n"
                 f"📝 Название: {note.title}\n"
                 f"📚 Экзамен: {note.exam_type.value}\n"
                 f"🔗 Ссылка: {note.link}\n"
                 f"{file_info}\n"
                 f"Выберите, что хотите изменить:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECT_NOTE
    
    elif action == "delete":
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"notes_confirm_delete_{note_id}"),
                InlineKeyboardButton("❌ Нет, отмена", callback_data="admin_back")
            ]
        ]
        
        file_info = ""
        if note.file_path:
            file_name = os.path.basename(note.file_path)
            file_info = f"📎 Файл: {file_name}\n"
        
        await query.edit_message_text(
            text=f"❗️ Удалить конспект?\n\n"
                 f"📝 Название: {note.title}\n"
                 f"📚 Экзамен: {note.exam_type.value}\n"
                 f"🔗 Ссылка: {note.link}\n"
                 f"{file_info}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CONFIRM_DELETE

async def handle_edit_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор действия при редактировании"""
    query = update.callback_query
    await safe_answer_query(query)
    
    parts = query.data.split("_")  # notes_edit_link_123 -> ["notes", "edit", "link", "123"]
    action = parts[2]
    note_id = int(parts[3])
    
    user_id = update.effective_user.id
    if user_id not in temp_data:
        temp_data[user_id] = {}
    temp_data[user_id]["note_id"] = note_id
    
    db = Database()
    note = db.get_note_by_id(note_id)
    
    if action == "file":
        await query.edit_message_text(
            text="📎 Отправьте файл:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
            ]])
        )
        return WAIT_FOR_FILE
    
    if action == "link":
        await query.edit_message_text(
            text=f"🔗 Введите новую ссылку:\n"
                 f"Текущая ссылка: {note.link}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]]),
            disable_web_page_preview=True
        )
        return EDIT_LINK
    else:  # action == "title"
        await query.edit_message_text(
            text=f"📝 Введите новое название:\n"
                 f"Текущее название: {note.title}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]]),
            disable_web_page_preview=True
        )
        return EDIT_TITLE

async def handle_edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает изменение названия конспекта"""
    user_id = update.effective_user.id
    note_id = temp_data[user_id]["note_id"]
    new_title = update.message.text
    
    db = Database()
    note = db.get_note_by_id(note_id)
    
    if not note:
        await update.message.reply_text(
            text="❌ Ошибка: конспект не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    # Обновляем только название, сохраняя остальные поля без изменений
    success = db.update_note(
        note_id,
        title=new_title,
        link=note.link,
        exam_type=note.exam_type,
        file_path=note.file_path
    )
    
    if not success:
        await update.message.reply_text(
            text="❌ Ошибка при обновлении названия",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        text=f"✅ Название конспекта успешно изменено!\n\n"
             f"📝 Новое название: {new_title}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
        ]])
    )
    return ConversationHandler.END

async def handle_note_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает изменение ссылки на конспект"""
    user_id = update.effective_user.id
    if user_id not in temp_data:
        await update.message.reply_text("❌ Ошибка: данные не найдены")
        return ConversationHandler.END
    
    note_id = temp_data[user_id]["note_id"]
    new_link = update.message.text.strip()
    
    # Валидация URL
    if not is_valid_url(new_link):
        await update.message.reply_text(
            "❌ Неверный формат ссылки!\n\n"
            "Ссылка должна быть в формате:\n"
            "• https://example.com\n"
            "• http://example.com\n"
            "• https://t.me/username\n\n"
            "Попробуйте еще раз:"
        )
        return EDIT_LINK
    
    db = context.bot_data['db']
    note = db.get_note_by_id(note_id)
    
    if not note:
        await update.message.reply_text(
            text="❌ Ошибка: конспект не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    # Обновляем только ссылку, сохраняя остальные поля без изменений
    success = db.update_note(
        note_id,
        title=note.title,
        link=new_link,
        exam_type=note.exam_type,
        file_path=note.file_path
    )
    
    if not success:
        await update.message.reply_text(
            text="❌ Ошибка при обновлении ссылки",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        text=f"✅ Ссылка успешно изменена!\n\n"
             f"🔗 Новая ссылка: {new_link}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")]]),
        disable_web_page_preview=True
    )
    return ConversationHandler.END

async def handle_delete_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает подтверждение удаления конспекта"""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID конспекта из callback_data
    note_id = int(query.data.split("_")[-1])  # notes_confirm_delete_123 -> 123
    
    db = context.bot_data['db']
    note = db.get_note_by_id(note_id)
    
    if not note:
        await query.edit_message_text(
            text="❌ Ошибка: конспект не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    title = note.title
    
    # Удаляем файл, если он существует
    if note.file_path and os.path.exists(note.file_path):
        try:
            os.remove(note.file_path)
            logging.info(f"Файл {note.file_path} успешно удален")
        except Exception as e:
            logging.error(f"Ошибка при удалении файла {note.file_path}: {e}")
    
    # Удаляем конспект из базы данных
    success = db.delete_note(note_id)
    
    if not success:
        await query.edit_message_text(
            text="❌ Ошибка при удалении конспекта",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    await query.edit_message_text(
        text=f"✅ Конспект '{title}' успешно удален!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
        ]])
    )
    return ConversationHandler.END

async def show_notes_page(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Показывает текущую страницу списка конспектов"""
    query = update.callback_query
    
    # Получаем данные из временного хранилища
    if user_id not in temp_data or 'notes' not in temp_data[user_id]:
        # Если данных нет, возвращаемся в меню
        await query.edit_message_text(
            "❌ Ошибка: данные о конспектах не найдены",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 В меню", callback_data="admin_back")
            ]])
        )
        return

    notes = temp_data[user_id]["notes"]
    current_page = temp_data[user_id].get("current_page", 0)  # По умолчанию первая страница
    exam_type = temp_data[user_id]["exam_type"]

    # Настройки пагинации
    ITEMS_PER_PAGE = 5
    total_items = len(notes)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    # Проверяем валидность текущей страницы
    if current_page >= total_pages:
        current_page = total_pages - 1
    if current_page < 0:
        current_page = 0
    
    # Обновляем current_page в temp_data
    temp_data[user_id]["current_page"] = current_page

    # Вычисляем индексы для текущей страницы
    start_idx = current_page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
    
    # Формируем текст сообщения
    message_lines = [
        f"📚 Список конспектов для {ExamType[exam_type].value}",
        f"Всего конспектов: {total_items}\n"
    ]
    
    # Добавляем конспекты
    for i, note in enumerate(notes[start_idx:end_idx], start=1):
        file_info = "❌ Нет файла"
        if note.file_path:
            file_name = os.path.basename(note.file_path)
            file_info = f"📎 Файл: {file_name}"
        link = note.link if note.link else ""
        if len(link) > 50:
            link = link[:47] + "..."
        message_lines.append(f"\n{start_idx + i}. 📝 {note.title}")
        if link:
            message_lines.append(f"└─ <a href=\"{link}\">Ссылка</a>")
        else:
            message_lines.append("└─ Ссылка: —")
        message_lines.append(f"└─ {file_info}")

    # Формируем клавиатуру
    keyboard = []
    
    # Кнопки навигации
    nav_row = []
    if current_page > 0:
        nav_row.append(InlineKeyboardButton("◀️", callback_data="notes_page_prev"))
    nav_row.append(InlineKeyboardButton(f"{current_page+1}/{total_pages}", callback_data="noop"))
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("▶️", callback_data="notes_page_next"))
    if len(nav_row) > 1:
        keyboard.append(nav_row)
    
    # Кнопка возврата в меню
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="admin_back")])
    
    # Отправляем или обновляем сообщение
    message_text = "\n".join(message_lines)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            parse_mode='HTML'
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            await query.answer("Нет изменений для отображения")
        else:
            raise e

async def handle_page_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает навигацию по страницам списка конспектов"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Проверяем наличие данных
    if user_id not in temp_data or 'notes' not in temp_data[user_id]:
        await query.answer("❌ Ошибка: данные не найдены")
        return ConversationHandler.END

    # Определяем направление навигации
    action = query.data.split("_")[-1]
    current_page = temp_data[user_id].get("current_page", 0)
    
    # Изменяем номер страницы
    if action == "prev":
        temp_data[user_id]["current_page"] = max(0, current_page - 1)
    elif action == "next":
        total_pages = (len(temp_data[user_id]["notes"]) + 4) // 5  # 5 элементов на странице
        temp_data[user_id]["current_page"] = min(total_pages - 1, current_page + 1)

    # Показываем обновленную страницу
    await show_notes_page(update, context, user_id)
    return SELECT_NOTE

async def handle_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает возврат в главное меню администратора"""
    query = update.callback_query
    await query.answer()
    
    # Очищаем временные данные пользователя
    user_id = update.effective_user.id
    if user_id in temp_data:
        del temp_data[user_id]
    
    # Возвращаемся в главное меню администратора
    await admin_menu(update, context)
    return ConversationHandler.END 