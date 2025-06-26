from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from core.database import Database, ExamType
from telegram.error import BadRequest
from handlers.admin_handlers import admin_menu
import os
from datetime import datetime
import logging

# Состояния для ConversationHandler
CHOOSE_EXAM, ENTER_TITLE, ENTER_LINK, CONFIRM_DELETE, SELECT_HOMEWORK, EDIT_TITLE, EDIT_LINK, ASK_FOR_FILE, WAIT_FOR_FILE = range(9)

# Временное хранилище данных
temp_data = {}

# Создаем директории для файлов, если их нет
HOMEWORK_FILES_DIR = "homework_files"

if not os.path.exists(HOMEWORK_FILES_DIR):
    os.makedirs(HOMEWORK_FILES_DIR)

async def show_homework_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает меню управления домашними заданиями"""
    query = update.callback_query
    
    if query and query.data != "admin_homework" and query.data.startswith("homework_"):
        action = query.data.split("_")[1]  # homework_add -> add
        await query.answer()
        return await show_exam_menu(update, context, action)
    
    keyboard = [
        [
            InlineKeyboardButton("📝 Добавить задание", callback_data="homework_add"),
            InlineKeyboardButton("📋 Список заданий", callback_data="homework_list")
        ],
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data="homework_edit"),
            InlineKeyboardButton("❌ Удалить", callback_data="homework_delete")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            "📚 Управление домашними заданиями\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "📚 Управление домашними заданиями\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def show_exam_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> int:
    """Показывает меню выбора типа экзамена"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    temp_data[user_id] = {"action": action}
    
    keyboard = [
        [
            InlineKeyboardButton("📝 ОГЭ", callback_data="homework_exam_OGE"),
            InlineKeyboardButton("📚 ЕГЭ", callback_data="homework_exam_EGE")
        ],
        [InlineKeyboardButton("🏫 Школьная программа", callback_data="homework_exam_SCHOOL")],
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
        text=f"📚 Выберите тип экзамена для {actions.get(action, '')} заданий:",
        reply_markup=reply_markup
    )
    
    return CHOOSE_EXAM

async def handle_exam_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор типа экзамена"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    exam_type = query.data.split("_")[-1]  # Изменено для нового формата callback_data
    action = temp_data[user_id]["action"]
    temp_data[user_id]["exam_type"] = exam_type
    
    db = Database()
    
    if action == "add":
        await query.edit_message_text(
            text="📝 Введите название домашнего задания:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
            ]])
        )
        return ENTER_TITLE
    
    elif action in ["list", "edit", "delete"]:
        homeworks = db.get_homework_by_exam(exam_type)
        if not homeworks:
            await query.edit_message_text(
                text=f"❌ Нет домашних заданий для {ExamType[exam_type].value}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="admin_back")
                ]])
            )
            return ConversationHandler.END
        
        if action == "list":
            # Сохраняем список заданий и текущую страницу
            temp_data[user_id]["homeworks"] = homeworks
            temp_data[user_id]["current_page"] = 0
            await show_homework_page(update, context, user_id)
            return SELECT_HOMEWORK
        
        # Для edit и delete формируем клавиатуру по два задания в строку
        keyboard = []
        
        for i in range(0, len(homeworks), 2):
            row = []
            for j in range(2):
                if i + j < len(homeworks):
                    hw = homeworks[i + j]
                    icon = "✏️" if action == "edit" else "❌"
                    button_text = f"{icon} {hw.title}"
                    button = InlineKeyboardButton(
                        button_text, 
                        callback_data=f"homework_{action}_{hw.id}"
                    )
                    row.append(button)
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        actions = {
            "edit": "редактирования",
            "delete": "удаления"
        }
        
        await query.edit_message_text(
            text=f"📋 Список заданий для {ExamType[exam_type].value}\n"
                 f"Выберите задание для {actions.get(action, '')}:",
            reply_markup=reply_markup
        )
        return SELECT_HOMEWORK if action in ["edit", "delete"] else ConversationHandler.END

async def handle_homework_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия домашнего задания"""
    user_id = update.effective_user.id
    temp_data[user_id]["title"] = update.message.text
    
    await update.message.reply_text(
        text="🔗 Введите ссылку на домашнее задание:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
        ]])
    )
    return ENTER_LINK

async def handle_homework_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ссылки на домашнее задание"""
    user_id = update.effective_user.id
    data = temp_data[user_id]
    data["link"] = update.message.text
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="homework_file_yes"),
            InlineKeyboardButton("❌ Нет", callback_data="homework_file_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text="📎 Хотите загрузить файл с домашним заданием?",
        reply_markup=reply_markup
    )
    return ASK_FOR_FILE

async def handle_file_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор загрузки файла"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = temp_data[user_id]
    
    if query.data == "homework_file_yes":
        await query.edit_message_text(
            text="📎 Отправьте файл с домашним заданием:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
            ]])
        )
        return WAIT_FOR_FILE
    else:
        # Сохраняем домашнее задание без файла
        db = Database()
        success = db.add_homework(data["title"], data["link"], data["exam_type"])
        
        if not success:
            await query.edit_message_text(
                text="❌ Ошибка при добавлении задания.\n"
                     "Возможно, задание с таким названием уже существует.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                ]])
            )
            return ConversationHandler.END
        
        await query.edit_message_text(
            text="✅ Домашнее задание успешно добавлено!\n\n"
                 f"📝 Название: {data['title']}\n"
                 f"📚 Экзамен: {ExamType[data['exam_type']].value}\n"
                 f"🔗 Ссылка: {data['link']}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает загрузку файла при создании или редактировании домашнего задания"""
    user_id = update.effective_user.id
    
    if user_id not in temp_data:
        await update.message.reply_text(
            text="❌ Ошибка: данные о задании не найдены",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    data = temp_data[user_id]
    hw_id = data.get("hw_id")
    
    # Сохраняем файл с временной меткой
    file = update.message.document
    file_name = file.file_name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{timestamp}_{file_name}"
    file_path = os.path.join(HOMEWORK_FILES_DIR, unique_filename)
    
    try:
        new_file = await file.get_file()
        await new_file.download_to_drive(file_path)
        
        db = context.bot_data['db']
        
        if not hw_id:  # Если это создание нового задания
            success = db.add_homework(
                data["title"],
                data["link"],
                data["exam_type"],
                file_path
            )
            
            if not success:
                if os.path.exists(file_path):
                    os.remove(file_path)
                await update.message.reply_text(
                    text="❌ Ошибка при добавлении задания.\n"
                         "Возможно, задание с таким названием уже существует.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                    ]])
                )
                return ConversationHandler.END
            
            await update.message.reply_text(
                text="✅ Домашнее задание успешно добавлено!\n\n"
                     f"📝 Название: {data['title']}\n"
                     f"📚 Экзамен: {ExamType[data['exam_type']].value}\n"
                     f"🔗 Ссылка: {data['link']}\n"
                     f"📎 Файл: {file_name}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                ]])
            )
            return ConversationHandler.END
        
        else:  # Если это редактирование существующего задания
            homework = db.get_homework_by_id(hw_id)
            
            if not homework:
                if os.path.exists(file_path):
                    os.remove(file_path)
                await update.message.reply_text(
                    text="❌ Ошибка: задание не найдено",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                    ]])
                )
                return ConversationHandler.END
            
            # Удаляем старый файл, если он существует
            if homework.file_path and os.path.exists(homework.file_path):
                try:
                    os.remove(homework.file_path)
                except Exception as e:
                    logging.error(f"Ошибка при удалении старого файла: {e}")
            
            # Обновляем путь к файлу в базе данных
            success = db.update_homework(
                hw_id,
                title=homework.title,
                link=homework.link,
                exam_type=homework.exam_type,
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
                text=f"✅ Файл успешно обновлен!\n\n"
                     f"📝 Задание: {homework.title}\n"
                     f"📎 Новый файл: {file_name}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
                ]])
            )
            return ConversationHandler.END
            
    except Exception as e:
        logging.error(f"Ошибка при сохранении файла: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        await update.message.reply_text(
            text="❌ Ошибка при сохранении файла",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END

async def handle_homework_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор домашнего задания для редактирования или удаления"""
    query = update.callback_query
    await query.answer()
    
    action, hw_id = query.data.split("_")[1:]
    user_id = update.effective_user.id
    temp_data[user_id]["hw_id"] = int(hw_id)
    
    db = context.bot_data['db']
    homework = db.get_homework_by_id(int(hw_id))
    
    if action == "edit":
        keyboard = [
            [
                InlineKeyboardButton("📝 Изменить название", callback_data=f"homework_edit_title_{hw_id}"),
                InlineKeyboardButton("🔗 Изменить ссылку", callback_data=f"homework_edit_link_{hw_id}")
            ],
            [InlineKeyboardButton("📎 Добавить файл", callback_data=f"homework_edit_file_{hw_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
        ]
        
        file_info = ""
        if homework.file_path:
            file_name = os.path.basename(homework.file_path)
            file_info = f"📎 Файл: {file_name}\n"
        
        await query.edit_message_text(
            text=f"✏️ Редактирование задания:\n\n"
                 f"📝 Название: {homework.title}\n"
                 f"📚 Экзамен: {homework.exam_type.value}\n"
                 f"🔗 Ссылка: {homework.link}\n"
                 f"{file_info}\n"
                 f"Выберите, что хотите изменить:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECT_HOMEWORK
    
    elif action == "delete":
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"homework_confirm_delete_{hw_id}"),
                InlineKeyboardButton("❌ Нет, отмена", callback_data="admin_back")
            ]
        ]
        
        file_info = ""
        if homework.file_path:
            file_name = os.path.basename(homework.file_path)
            file_info = f"📎 Файл: {file_name}\n"
        
        await query.edit_message_text(
            text=f"❗️ Удалить задание?\n\n"
                 f"📝 Название: {homework.title}\n"
                 f"📚 Экзамен: {homework.exam_type.value}\n"
                 f"🔗 Ссылка: {homework.link}\n"
                 f"{file_info}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CONFIRM_DELETE

async def handle_edit_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор действия при редактировании"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")  # homework_edit_link_123 -> ["homework", "edit", "link", "123"]
    action = parts[2]
    hw_id = int(parts[3])
    
    user_id = update.effective_user.id
    if user_id not in temp_data:
        temp_data[user_id] = {}
    temp_data[user_id]["hw_id"] = hw_id
    
    db = Database()
    homework = db.get_homework_by_id(hw_id)
    
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
                 f"Текущая ссылка: {homework.link}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
            ]])
        )
        return EDIT_LINK
    else:  # action == "title"
        await query.edit_message_text(
            text=f"📝 Введите новое название:\n"
                 f"Текущее название: {homework.title}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
            ]])
        )
        return EDIT_TITLE

async def handle_edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает изменение названия домашнего задания"""
    user_id = update.effective_user.id
    hw_id = temp_data[user_id]["hw_id"]
    new_title = update.message.text
    
    db = Database()
    homework = db.get_homework_by_id(hw_id)
    
    if not homework:
        await update.message.reply_text(
            text="❌ Ошибка: задание не найдено",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    # Обновляем только название, сохраняя остальные поля без изменений
    success = db.update_homework(
        hw_id,
        title=new_title,
        link=homework.link,
        exam_type=homework.exam_type,
        file_path=homework.file_path
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
        text=f"✅ Название задания успешно изменено!\n\n"
             f"📝 Новое название: {new_title}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
        ]])
    )
    return ConversationHandler.END

async def handle_homework_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает изменение ссылки на домашнее задание"""
    user_id = update.effective_user.id
    if user_id not in temp_data:
        await update.message.reply_text("❌ Ошибка: данные не найдены")
        return ConversationHandler.END
    
    hw_id = temp_data[user_id]["hw_id"]
    new_link = update.message.text
    
    db = context.bot_data['db']
    homework = db.get_homework_by_id(hw_id)
    
    if not homework:
        await update.message.reply_text(
            text="❌ Ошибка: задание не найдено",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    # Обновляем только ссылку, сохраняя остальные поля без изменений
    success = db.update_homework(
        hw_id,
        title=homework.title,
        link=new_link,
        exam_type=homework.exam_type,
        file_path=homework.file_path
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
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
        ]])
    )
    return ConversationHandler.END

async def handle_delete_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает подтверждение удаления домашнего задания"""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID задания из callback_data
    hw_id = int(query.data.split("_")[-1])  # homework_confirm_delete_123 -> 123
    
    db = context.bot_data['db']
    homework = db.get_homework_by_id(hw_id)
    
    if not homework:
        await query.edit_message_text(
            text="❌ Ошибка: задание не найдено",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    title = homework.title
    
    # Удаляем файл, если он существует
    if homework.file_path and os.path.exists(homework.file_path):
        try:
            os.remove(homework.file_path)
            logging.info(f"Файл {homework.file_path} успешно удален")
        except Exception as e:
            logging.error(f"Ошибка при удалении файла {homework.file_path}: {e}")
    
    # Удаляем задание из базы данных
    success = db.delete_homework(hw_id)
    
    if not success:
        await query.edit_message_text(
            text="❌ Ошибка при удалении задания",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
            ]])
        )
        return ConversationHandler.END
    
    await query.edit_message_text(
        text=f"✅ Задание успешно удалено!\n\n"
             f"📝 Название: {title}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
        ]])
    )
    return ConversationHandler.END

async def show_homework_page(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Показывает текущую страницу списка заданий"""
    query = update.callback_query
    
    # Получаем данные из временного хранилища
    if user_id not in temp_data or 'homeworks' not in temp_data[user_id]:
        # Если данных нет, возвращаемся в меню
        await query.edit_message_text(
            "❌ Ошибка: данные о заданиях не найдены",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 В меню", callback_data="admin_back")
            ]])
        )
        return

    homeworks = temp_data[user_id]["homeworks"]
    current_page = temp_data[user_id].get("current_page", 0)  # По умолчанию первая страница
    exam_type = temp_data[user_id]["exam_type"]

    # Настройки пагинации
    ITEMS_PER_PAGE = 5
    total_items = len(homeworks)
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
        f"📚 Список заданий для {ExamType[exam_type].value}",
        f"Всего заданий: {total_items}\n"
    ]
    
    # Добавляем задания
    for i, hw in enumerate(homeworks[start_idx:end_idx], start=1):
        # Получаем имя файла, если он есть
        file_info = "❌ Нет файла"
        if hw.file_path:
            file_name = os.path.basename(hw.file_path)
            file_info = f"📎 Файл: {file_name}"
        
        # Форматируем ссылку, обрезая если она слишком длинная
        link = hw.link
        if len(link) > 50:
            link = link[:47] + "..."
        
        message_lines.extend([
            f"\n{start_idx + i}. 📝 {hw.title}",
            f"└─ 🔗 {link}",
            f"└─ {file_info}"
        ])

    # Добавляем информацию о страницах
    message_lines.extend([
        "",  # Пустая строка для разделения
        f"📄 Страница {current_page + 1} из {total_pages}",
        f"Показано заданий: {start_idx + 1}-{end_idx} из {total_items}"
    ])
    
    # Формируем клавиатуру
    keyboard = []
    
    # Кнопки навигации
    nav_row = []
    if current_page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Предыдущая", callback_data="homework_page_prev"))
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Следующая ➡️", callback_data="homework_page_next"))
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка возврата в меню
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="admin_back")])
    
    # Отправляем или обновляем сообщение
    message_text = "\n".join(message_lines)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if query:
            await query.edit_message_text(text=message_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text=message_text, reply_markup=reply_markup)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            await query.answer("Вы уже на этой странице")
        else:
            raise
    
    return SELECT_HOMEWORK

async def handle_page_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает навигацию по страницам списка заданий"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Проверяем наличие данных
    if user_id not in temp_data or 'homeworks' not in temp_data[user_id]:
        await query.answer("❌ Ошибка: данные не найдены")
        return ConversationHandler.END

    # Определяем направление навигации
    action = query.data.split("_")[-1]
    current_page = temp_data[user_id].get("current_page", 0)
    
    # Изменяем номер страницы
    if action == "prev":
        temp_data[user_id]["current_page"] = max(0, current_page - 1)
    elif action == "next":
        total_pages = (len(temp_data[user_id]["homeworks"]) + 4) // 5  # 5 элементов на странице
        temp_data[user_id]["current_page"] = min(total_pages - 1, current_page + 1)

    # Показываем обновленную страницу
    await show_homework_page(update, context, user_id)
    return SELECT_HOMEWORK

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