import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters, ConversationHandler
)
from core.database import Database
from core.migrations import migrate_database
from handlers.admin_handlers import (
    admin_menu, start_add_student, enter_name, choose_exam,
    enter_link, cancel, handle_admin_actions, handle_edit_exam,
    handle_edit_name, handle_edit_link, handle_add_note,
    ENTER_NAME, CHOOSE_EXAM, ENTER_LINK, CONFIRM_DELETE,
    EDIT_NAME, EDIT_EXAM, EDIT_LINK, ADD_NOTE
)
from handlers.student_handlers import (
    student_menu, handle_student_actions, handle_password, ENTER_PASSWORD,
    handle_display_name_change, ENTER_DISPLAY_NAME
)
from handlers.homework_handlers import (
    show_homework_menu,
    show_exam_menu,
    handle_exam_choice,
    handle_homework_title,
    handle_homework_link,
    handle_homework_selection,
    handle_edit_action,
    handle_edit_title,
    handle_edit_link,
    handle_delete_confirmation,
    handle_page_navigation,
    CHOOSE_EXAM as HOMEWORK_CHOOSE_EXAM,
    ENTER_TITLE, ENTER_LINK as HOMEWORK_ENTER_LINK,
    CONFIRM_DELETE as HOMEWORK_CONFIRM_DELETE,
    SELECT_HOMEWORK, EDIT_TITLE, EDIT_LINK
)
from handlers.common_handlers import handle_start

# Загрузка переменных окружения
load_dotenv()

def main():
    """Основная функция"""
    # Получаем токен из переменных окружения
    token = os.getenv("TELEGRAM_TOKEN")
    
    # Выполняем миграцию базы данных
    migrate_database()
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Инициализируем базу данных
    db = Database()
    application.bot_data['db'] = db

    # Создаем главный обработчик для команды /start и ввода пароля
    main_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", handle_start),
            CallbackQueryHandler(handle_student_actions, pattern="^student_change_name$")
        ],
        states={
            ENTER_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password)
            ],
            ENTER_DISPLAY_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_display_name_change),
                CallbackQueryHandler(handle_student_actions, pattern="^student_back_to_settings$")
            ]
        },
        fallbacks=[CommandHandler("cancel", handle_start)],
        name="main_handler",
        persistent=False
    )

    # Создаем обработчик диалога добавления студента
    add_student_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_student, pattern="^admin_add_student$")],
        states={
            ENTER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$"),
                CallbackQueryHandler(admin_menu, pattern="^cancel_add$")
            ],
            CHOOSE_EXAM: [
                CallbackQueryHandler(choose_exam, pattern="^student_exam_(OGE|EGE|SCHOOL)$"),
                CallbackQueryHandler(admin_menu, pattern="^cancel_add$"),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            ENTER_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_link),
                CallbackQueryHandler(admin_menu, pattern="^cancel_add$"),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(admin_menu, pattern="^admin_back$"),
            CallbackQueryHandler(admin_menu, pattern="^cancel_add$")
        ],
        name="add_student",
        persistent=False
    )

    # Создаем обработчик диалога редактирования студента
    edit_student_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_admin_actions, pattern="^edit_name_"),
            CallbackQueryHandler(handle_admin_actions, pattern="^edit_exam_"),
            CallbackQueryHandler(handle_admin_actions, pattern="^edit_link_"),
            CallbackQueryHandler(handle_admin_actions, pattern="^add_note_"),
            CallbackQueryHandler(handle_admin_actions, pattern="^edit_type_"),
            CallbackQueryHandler(handle_admin_actions, pattern="^edit_student_")
        ],
        states={
            EDIT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_name),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            EDIT_EXAM: [
                CallbackQueryHandler(handle_edit_exam, pattern="^student_new_exam_(OGE|EGE|SCHOOL)$"),
                CallbackQueryHandler(admin_menu, pattern="^edit_cancel$")
            ],
            EDIT_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_link),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            ADD_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_note),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(admin_menu, pattern="^admin_back$")
        ],
        name="edit_student"
    )

    # Создаем обработчик диалога удаления студента
    delete_student_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_admin_actions, pattern="^admin_delete$"),
            CallbackQueryHandler(handle_admin_actions, pattern="^delete_type_"),
            CallbackQueryHandler(handle_admin_actions, pattern="^delete_[0-9]+$")
        ],
        states={
            CONFIRM_DELETE: [
                CallbackQueryHandler(handle_admin_actions, pattern="^confirm_delete$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^cancel_delete$"),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(admin_menu, pattern="^admin_back$"),
            CallbackQueryHandler(handle_admin_actions, pattern="^admin_delete$")
        ],
        name="delete_student",
        persistent=False
    )

    # Создаем обработчик для управления домашними заданиями
    homework_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_homework_menu, pattern="^homework_menu$"),
            CallbackQueryHandler(lambda u, c: show_exam_menu(u, c, "add"), pattern="^homework_add$"),
            CallbackQueryHandler(lambda u, c: show_exam_menu(u, c, "list"), pattern="^homework_list$"),
            CallbackQueryHandler(lambda u, c: show_exam_menu(u, c, "edit"), pattern="^homework_edit$"),
            CallbackQueryHandler(lambda u, c: show_exam_menu(u, c, "delete"), pattern="^homework_delete$")
        ],
        states={
            HOMEWORK_CHOOSE_EXAM: [
                CallbackQueryHandler(handle_exam_choice, pattern="^homework_exam_(OGE|EGE|SCHOOL)$"),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            ENTER_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_homework_title),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            HOMEWORK_ENTER_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_homework_link),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            SELECT_HOMEWORK: [
                CallbackQueryHandler(handle_homework_selection, pattern="^homework_(edit|delete)_\d+$"),
                CallbackQueryHandler(handle_edit_action, pattern="^edit_(title|link)_\d+$"),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            EDIT_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_title),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            EDIT_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_link),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            HOMEWORK_CONFIRM_DELETE: [
                CallbackQueryHandler(handle_delete_confirmation, pattern="^confirm_delete_\d+$"),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            ConversationHandler.END: [
                CallbackQueryHandler(handle_page_navigation, pattern="^homework_page_(next|prev)$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin_menu, pattern="^admin_back$")
        ],
        name="homework",
        persistent=False
    )

    # Добавляем обработчики в правильном порядке
    application.add_handler(main_handler)  # Главный обработчик /start и ввода пароля
    application.add_handler(add_student_handler)  # Обработчик добавления студента
    application.add_handler(edit_student_handler)  # Обработчик редактирования студента
    application.add_handler(delete_student_handler)  # Обработчик удаления студента
    application.add_handler(homework_handler)  # Обработчик домашних заданий
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^(admin_|info_type_|student_info_|edit_type_|edit_student_)"))  # Общий обработчик админа
    application.add_handler(CallbackQueryHandler(handle_student_actions, pattern="^student_"))  # Общий обработчик студента
    
    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    # Добавляем первого администратора при запуске
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    if ADMIN_ID:
        db = Database()
        db.add_admin(ADMIN_ID)
    
    main() 