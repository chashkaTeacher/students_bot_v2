from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from core.database import Database, ExamType
from telegram.error import BadRequest
from handlers.admin_handlers import admin_menu

# Состояния для ConversationHandler
CHOOSE_EXAM = "CHOOSE_EXAM"
ENTER_TITLE = "ENTER_TITLE"
ENTER_LINK = "ENTER_LINK"
SELECT_HOMEWORK = "SELECT_HOMEWORK"
EDIT_TITLE = "EDIT_TITLE"
EDIT_LINK = "EDIT_LINK"
CONFIRM_DELETE = "CONFIRM_DELETE"

# Временное хранилище данных
temp_data = {}

async def show_homework_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает меню управления домашними заданиями"""
    query = update.callback_query
    if query:
        await query.answer()

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
    
    text = (
        "📚 Управление домашними заданиями\n"
        "Выберите действие:"
    )
    
    if query:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)
    
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
            return ConversationHandler.END
        
        # Для edit и delete оставляем старую логику
        keyboard = []
        for hw in homeworks:
            icon = "✏️" if action == "edit" else "❌"
            keyboard.append([InlineKeyboardButton(
                f"{icon} {hw.title}", 
                callback_data=f"homework_{action}_{hw.id}"
            )])
        
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
    
    db = Database()
    db.add_homework(data["title"], update.message.text, data["exam_type"])
    
    await update.message.reply_text(
        text="✅ Домашнее задание успешно добавлено!\n\n"
             f"📝 Название: {data['title']}\n"
             f"📚 Экзамен: {ExamType[data['exam_type']].value}\n"
             f"🔗 Ссылка: {update.message.text}",
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
    
    db = Database()
    homework = db.get_homework_by_id(int(hw_id))
    
    if action == "edit":
        keyboard = [
            [
                InlineKeyboardButton("📝 Изменить название", callback_data=f"edit_title_{hw_id}"),
                InlineKeyboardButton("🔗 Изменить ссылку", callback_data=f"edit_link_{hw_id}")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
        ]
        await query.edit_message_text(
            text=f"✏️ Редактирование задания:\n\n"
                 f"📝 Название: {homework.title}\n"
                 f"📚 Экзамен: {homework.exam_type.value}\n"
                 f"🔗 Ссылка: {homework.link}\n\n"
                 f"Выберите, что хотите изменить:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECT_HOMEWORK
    
    elif action == "delete":
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{hw_id}"),
                InlineKeyboardButton("❌ Нет, отмена", callback_data="admin_back")
            ]
        ]
        await query.edit_message_text(
            text=f"❗️ Удалить задание?\n\n"
                 f"📝 Название: {homework.title}\n"
                 f"📚 Экзамен: {homework.exam_type.value}\n"
                 f"🔗 Ссылка: {homework.link}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CONFIRM_DELETE

async def handle_edit_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор действия при редактировании"""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split("_")[1]
    await query.edit_message_text(
        text=f"📝 Введите новое {'название' if action == 'title' else 'ссылку'}:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
        ]])
    )
    return EDIT_TITLE if action == "title" else EDIT_LINK

async def handle_edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает изменение названия домашнего задания"""
    user_id = update.effective_user.id
    hw_id = temp_data[user_id]["hw_id"]
    
    db = Database()
    homework = db.get_homework_by_id(hw_id)
    if homework:
        db.update_homework(hw_id, title=update.message.text, link=homework.link)
    
    await update.message.reply_text(
        text=f"✅ Название задания успешно изменено!\n\n"
             f"📝 Новое название: {update.message.text}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
        ]])
    )
    return ConversationHandler.END

async def handle_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает изменение ссылки домашнего задания"""
    user_id = update.effective_user.id
    hw_id = temp_data[user_id]["hw_id"]
    
    db = Database()
    homework = db.get_homework_by_id(hw_id)
    if homework:
        db.update_homework(hw_id, title=homework.title, link=update.message.text)
    
    await update.message.reply_text(
        text=f"✅ Ссылка задания успешно изменена!\n\n"
             f"🔗 Новая ссылка: {update.message.text}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад в меню", callback_data="admin_back")
        ]])
    )
    return ConversationHandler.END

async def handle_delete_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает подтверждение удаления домашнего задания"""
    query = update.callback_query
    await query.answer()
    
    hw_id = int(query.data.split("_")[2])
    db = Database()
    homework = db.get_homework_by_id(hw_id)
    title = homework.title if homework else "Неизвестное задание"
    
    db.delete_homework(hw_id)
    
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
    homeworks = temp_data[user_id]["homeworks"]
    current_page = temp_data[user_id]["current_page"]
    exam_type = temp_data[user_id]["exam_type"]
    
    # Настройки пагинации
    items_per_page = 5
    start_idx = current_page * items_per_page
    end_idx = start_idx + items_per_page
    total_pages = (len(homeworks) + items_per_page - 1) // items_per_page
    
    # Формируем текст списка заданий
    text = f"📚 Список заданий для {ExamType[exam_type].value}\n\n"
    for i, hw in enumerate(homeworks[start_idx:end_idx], start=start_idx + 1):
        text += f"{i}. 📝 {hw.title}\n   🔗 {hw.link}\n\n"
    
    text += f"\nСтраница {current_page + 1} из {total_pages}"
    
    # Формируем клавиатуру для навигации
    keyboard = []
    nav_buttons = []
    
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="homework_page_prev"))
    if current_page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Вперёд", callback_data="homework_page_next"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="admin_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)

async def handle_page_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает навигацию по страницам списка заданий"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    action = query.data.split("_")[-1]
    
    if action == "prev":
        temp_data[user_id]["current_page"] -= 1
    elif action == "next":
        temp_data[user_id]["current_page"] += 1
    
    await show_homework_page(update, context, user_id)
    return ConversationHandler.END 