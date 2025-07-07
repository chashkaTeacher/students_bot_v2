import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters, ConversationHandler, JobQueue
)
from core.database import Database
from core.migrations import migrate_database
from handlers.admin_handlers import (
    admin_menu, handle_admin_actions, start_add_student,
    enter_name, choose_exam, enter_link, cancel,
    handle_edit_name, handle_edit_link, handle_edit_exam, handle_add_note,
    ENTER_NAME, CHOOSE_EXAM, ENTER_LINK, CONFIRM_DELETE,
    EDIT_NAME, EDIT_EXAM, EDIT_STUDENT_LINK, ADD_NOTE,
    tasks_menu,
    give_homework_menu,
    give_homework_choose_exam,
    give_homework_choose_student,
    give_homework_choose_task,
    give_homework_assign,
    give_homework_status_handler,
    GIVE_HOMEWORK_CHOOSE_EXAM, GIVE_HOMEWORK_CHOOSE_STUDENT, GIVE_HOMEWORK_CHOOSE_TASK, GIVE_HOMEWORK_STATUS, GIVE_HOMEWORK_MENU,
    handle_give_homework_variant,
    handle_give_variant_choose_exam,
    handle_give_variant_enter_link,
    GIVE_VARIANT_CHOOSE_EXAM, GIVE_VARIANT_ENTER_LINK,
    school_homework_choice, school_existing_homework, school_new_homework_title,
    school_homework_title_handler, school_homework_link_handler,
    school_homework_file_handler, school_homework_no_file_handler,
    school_note_creation_choice, school_note_title_handler, school_note_link_handler,
    school_note_file_handler, school_note_no_file_handler,
    SCHOOL_HOMEWORK_CHOICE, SCHOOL_HOMEWORK_TITLE, SCHOOL_HOMEWORK_LINK, SCHOOL_HOMEWORK_FILE,
    SCHOOL_NOTE_CHOICE, SCHOOL_NOTE_TITLE, SCHOOL_NOTE_LINK, SCHOOL_NOTE_FILE,
    show_statistics_menu, handle_statistics_exam_choice, handle_statistics_student_choice,
    STATISTICS_CHOOSE_EXAM, STATISTICS_CHOOSE_STUDENT, EDIT_TASK_STATUS,
    handle_schedule_time, handle_schedule_duration,
    SCHEDULE_CHOOSE_DAY, SCHEDULE_ENTER_TIME, SCHEDULE_ENTER_DURATION,
    handle_schedule_edit_time,
    SCHEDULE_EDIT_CHOOSE_PARAM, SCHEDULE_EDIT_DAY, SCHEDULE_EDIT_TIME, SCHEDULE_EDIT_DURATION,
    show_reschedule_settings, show_reschedule_hours_settings, show_reschedule_end_hours_settings,
    save_reschedule_hours, show_reschedule_days_settings, toggle_reschedule_day,
    show_reschedule_interval_settings, save_reschedule_interval,
    restore_reminders_from_database, check_and_send_reminders
)
from handlers.student_handlers import (
    student_menu, handle_student_actions, handle_password, ENTER_PASSWORD,
    handle_display_name_change, ENTER_DISPLAY_NAME, show_student_menu,
    handle_student_selection, handle_student_edit_action, handle_student_link_edit,
    send_student_menu_by_chat_id, show_student_notes_menu, show_student_homework_menu,
    show_student_roadmap, student_reschedule_menu, student_reschedule_start, student_reschedule_choose_week,
    student_reschedule_choose_day, student_reschedule_choose_time, student_reschedule_confirm,
    RESCHEDULE_CHOOSE_LESSON, RESCHEDULE_CHOOSE_WEEK, RESCHEDULE_CHOOSE_DAY, RESCHEDULE_CHOOSE_TIME, RESCHEDULE_CONFIRM,
    handle_student_text
)
from handlers.homework_handlers import (
    show_homework_menu,
    show_exam_menu as show_homework_exam_menu,
    handle_exam_choice as handle_homework_exam_choice,
    handle_homework_title,
    handle_homework_link,
    handle_homework_selection,
    handle_edit_action as handle_homework_edit_action,
    handle_edit_title as handle_homework_edit_title,
    handle_homework_edit_link,
    handle_delete_confirmation as handle_homework_delete_confirmation,
    handle_page_navigation as handle_homework_page_navigation,
    handle_file_choice as handle_homework_file_choice,
    handle_file_upload as handle_homework_file_upload,
    handle_admin_back,
    CHOOSE_EXAM as HOMEWORK_CHOOSE_EXAM,
    ENTER_TITLE as HOMEWORK_ENTER_TITLE,
    ENTER_LINK as HOMEWORK_ENTER_LINK,
    CONFIRM_DELETE as HOMEWORK_CONFIRM_DELETE,
    SELECT_HOMEWORK, EDIT_TITLE, EDIT_LINK,
    ASK_FOR_FILE, WAIT_FOR_FILE
)
from handlers.notes_handlers import (
    show_notes_menu,
    show_exam_menu as show_notes_exam_menu,
    handle_exam_choice as handle_notes_exam_choice,
    handle_note_title,
    handle_note_link,
    handle_note_selection,
    handle_edit_action as handle_notes_edit_action,
    handle_edit_title as handle_notes_edit_title,
    handle_note_edit_link,
    handle_delete_confirmation as handle_notes_delete_confirmation,
    handle_page_navigation as handle_notes_page_navigation,
    handle_file_choice as handle_notes_file_choice,
    handle_file_upload as handle_notes_file_upload,
    handle_admin_back,
    CHOOSE_EXAM as NOTES_CHOOSE_EXAM,
    ENTER_TITLE as NOTES_ENTER_TITLE,
    ENTER_LINK as NOTES_ENTER_LINK,
    CONFIRM_DELETE as NOTES_CONFIRM_DELETE,
    SELECT_NOTE, EDIT_TITLE, EDIT_LINK,
    ASK_FOR_FILE, WAIT_FOR_FILE
)
from handlers.common_handlers import (
    handle_start, handle_exam_preparation, handle_personal_cabinet, handle_back_to_start
)
from datetime import time, timedelta, datetime
import pytz
import asyncio

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

    # Восстанавливаем напоминания из базы данных при запуске
    restore_reminders_from_database(application.job_queue, db)

    # ГЛОБАЛЬНЫЕ обработчики для статистики (ставим до ConversationHandler-ов)
    application.add_handler(CallbackQueryHandler(handle_statistics_student_choice, pattern="^statistics_page_\\d+$"))

    # Создаем главный обработчик для команды /start и ввода пароля
    main_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", handle_start),
            CallbackQueryHandler(handle_personal_cabinet, pattern="^personal_cabinet$"),
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
        fallbacks=[
            CommandHandler("cancel", handle_start),
            CallbackQueryHandler(handle_back_to_start, pattern="^back_to_start$")
        ],
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
            CallbackQueryHandler(handle_admin_actions, pattern="^edit_student_"),
            CallbackQueryHandler(handle_admin_actions, pattern="^delete_note_"),
            CallbackQueryHandler(handle_admin_actions, pattern="^edit_task_status_"),
            CallbackQueryHandler(handle_admin_actions, pattern="^edit_task_select_"),
            CallbackQueryHandler(handle_admin_actions, pattern="^edit_task_status_set_")
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
            EDIT_STUDENT_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_link),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            ADD_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_note),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            EDIT_TASK_STATUS: [
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_task_status_"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_task_select_"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_task_status_set_")
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
            CallbackQueryHandler(show_homework_menu, pattern="^admin_homework$"),
            CallbackQueryHandler(show_homework_menu, pattern="^homework_(add|list|edit|delete)$")
        ],
        states={
            HOMEWORK_CHOOSE_EXAM: [
                CallbackQueryHandler(handle_homework_exam_choice, pattern="^homework_exam_(OGE|EGE|SCHOOL)$"),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            HOMEWORK_ENTER_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_homework_title),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            HOMEWORK_ENTER_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_homework_link),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            SELECT_HOMEWORK: [
                CallbackQueryHandler(handle_homework_selection, pattern="^homework_(edit|delete)_\d+$"),
                CallbackQueryHandler(handle_homework_edit_action, pattern="^homework_edit_(title|link|file)_\d+$"),
                CallbackQueryHandler(handle_homework_page_navigation, pattern="^homework_page_(next|prev)$"),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            EDIT_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_homework_edit_title),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            EDIT_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_homework_edit_link),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            HOMEWORK_CONFIRM_DELETE: [
                CallbackQueryHandler(handle_homework_delete_confirmation, pattern="^homework_confirm_delete_\d+$"),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            ASK_FOR_FILE: [
                CallbackQueryHandler(handle_homework_file_choice, pattern="^homework_file_(yes|no)$"),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            WAIT_FOR_FILE: [
                MessageHandler(filters.Document.ALL, handle_homework_file_upload),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            ConversationHandler.END: [
                CallbackQueryHandler(handle_homework_page_navigation, pattern="^homework_page_(next|prev)$"),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ]
        },
        fallbacks=[CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")]
    )

    # Создаем обработчик для управления конспектами
    notes_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_notes_menu, pattern="^admin_notes$"),
            CallbackQueryHandler(show_notes_menu, pattern="^notes_(add|list|edit|delete)$")
        ],
        states={
            NOTES_CHOOSE_EXAM: [
                CallbackQueryHandler(handle_notes_exam_choice, pattern="^notes_exam_(OGE|EGE|SCHOOL)$"),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            NOTES_ENTER_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note_title),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            NOTES_ENTER_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note_link),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            SELECT_NOTE: [
                CallbackQueryHandler(handle_note_selection, pattern="^notes_(edit|delete)_\d+$"),
                CallbackQueryHandler(handle_notes_edit_action, pattern="^notes_edit_(title|link|file)_\d+$"),
                CallbackQueryHandler(handle_notes_page_navigation, pattern="^notes_page_(next|prev)$"),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            EDIT_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_notes_edit_title),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            EDIT_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note_edit_link),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            ASK_FOR_FILE: [
                CallbackQueryHandler(handle_notes_file_choice, pattern="^notes_file_(yes|no)$"),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            WAIT_FOR_FILE: [
                MessageHandler(filters.Document.ALL, handle_notes_file_upload),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ],
            NOTES_CONFIRM_DELETE: [
                CallbackQueryHandler(handle_notes_delete_confirmation, pattern="^notes_confirm_delete_\d+$"),
                CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(handle_admin_back, pattern="^admin_back$")
        ],
        name="notes",
        persistent=False
    )

    # Создаем обработчик для выдачи домашнего задания через меню администратора
    give_homework_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(give_homework_menu, pattern="^admin_give_homework$")],
        states={
            GIVE_HOMEWORK_MENU: [
                CallbackQueryHandler(give_homework_choose_exam, pattern="^admin_give_homework$"),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            GIVE_HOMEWORK_CHOOSE_EXAM: [
                CallbackQueryHandler(give_homework_choose_student, pattern="^give_hw_exam_(OGE|EGE|SCHOOL)$"),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            GIVE_HOMEWORK_CHOOSE_STUDENT: [
                CallbackQueryHandler(give_homework_choose_task, pattern="^give_hw_student_\\d+$"),
                CallbackQueryHandler(school_homework_choice, pattern="^school_hw_student_\\d+$"),
                CallbackQueryHandler(give_homework_menu, pattern="^admin_give_homework$")
            ],
            GIVE_HOMEWORK_CHOOSE_TASK: [
                CallbackQueryHandler(give_homework_assign, pattern="^give_hw_task_\\d+$"),
                CallbackQueryHandler(give_homework_menu, pattern="^admin_give_homework$")
            ],
            GIVE_HOMEWORK_STATUS: [
                CallbackQueryHandler(give_homework_status_handler, pattern="^hw_status_(completed|in_progress)$"),
                CallbackQueryHandler(admin_menu, pattern="^admin_give_homework$")
            ],
            # --- Школьная программа ---
            SCHOOL_HOMEWORK_CHOICE: [
                CallbackQueryHandler(school_existing_homework, pattern="^school_existing_homework$"),
                CallbackQueryHandler(school_new_homework_title, pattern="^school_new_homework$"),
                CallbackQueryHandler(give_homework_menu, pattern="^admin_give_homework$")
            ],
            SCHOOL_HOMEWORK_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, school_homework_title_handler)
            ],
            SCHOOL_HOMEWORK_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, school_homework_link_handler)
            ],
            SCHOOL_HOMEWORK_FILE: [
                CallbackQueryHandler(school_homework_file_handler, pattern="^school_homework_file$"),
                CallbackQueryHandler(school_homework_no_file_handler, pattern="^school_homework_no_file$"),
                MessageHandler(filters.Document.ALL, school_homework_file_handler)
            ],
            SCHOOL_NOTE_CHOICE: [
                CallbackQueryHandler(school_note_creation_choice, pattern="^school_create_note$|^school_no_note$")
            ],
            SCHOOL_NOTE_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, school_note_title_handler)
            ],
            SCHOOL_NOTE_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, school_note_link_handler)
            ],
            SCHOOL_NOTE_FILE: [
                CallbackQueryHandler(school_note_file_handler, pattern="^school_note_file$"),
                CallbackQueryHandler(school_note_no_file_handler, pattern="^school_note_no_file$"),
                MessageHandler(filters.Document.ALL, school_note_file_handler)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin_menu, pattern="^admin_back$"),
            CallbackQueryHandler(admin_menu, pattern="^admin_give_homework$")
        ],
        name="give_homework",
        persistent=False
    )

    # ConversationHandler для выдачи варианта
    give_variant_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_give_homework_variant, pattern="^admin_give_homework_variant$")],
        states={
            GIVE_VARIANT_CHOOSE_EXAM: [
                CallbackQueryHandler(handle_give_variant_choose_exam, pattern="^give_variant_exam_(OGE|EGE)$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^admin_give_homework$")
            ],
            GIVE_VARIANT_ENTER_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_give_variant_enter_link),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin_menu, pattern="^admin_back$"),
            CallbackQueryHandler(admin_menu, pattern="^admin_give_homework$")
        ],
        name="give_variant",
        persistent=False
    )

    # ConversationHandler для статистики
    statistics_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(show_statistics_menu, pattern="^admin_stats$")],
        states={
            STATISTICS_CHOOSE_EXAM: [
                CallbackQueryHandler(handle_statistics_exam_choice, pattern="^statistics_exam_(EGE|OGE)$"),
                CallbackQueryHandler(handle_statistics_exam_choice, pattern="^statistics_exam_back$"),
                CallbackQueryHandler(admin_menu, pattern="^admin_back$")
            ],
            STATISTICS_CHOOSE_STUDENT: [
                CallbackQueryHandler(handle_statistics_student_choice, pattern="^statistics_student_\\d+$"),
                CallbackQueryHandler(handle_statistics_student_choice, pattern="^statistics_page_\\d+$"),
                CallbackQueryHandler(handle_statistics_exam_choice, pattern="^statistics_exam_back$"),
                CallbackQueryHandler(show_statistics_menu, pattern="^statistics_back$")
            ]
        },
        fallbacks=[CallbackQueryHandler(admin_menu, pattern="^admin_back$")],
        name="statistics",
        persistent=False
    )

    # ConversationHandler для расписания
    schedule_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_admin_actions, pattern="^schedule_(add|view|edit|delete)_student_\\d+$")
        ],
        states={
            SCHEDULE_CHOOSE_DAY: [
                CallbackQueryHandler(handle_admin_actions, pattern="^schedule_day_\\d+$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^schedule_delete_\\d+$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^schedule_edit_\\d+$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_day$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_time$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_duration$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^admin_back$")
            ],
            SCHEDULE_ENTER_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_schedule_time),
                CallbackQueryHandler(handle_admin_actions, pattern="^schedule_delete_\\d+$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^schedule_edit_\\d+$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_day$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_time$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_duration$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^admin_back$")
            ],
            SCHEDULE_ENTER_DURATION: [
                CallbackQueryHandler(handle_schedule_duration, pattern="^schedule_duration_\\d+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_schedule_duration),
                CallbackQueryHandler(handle_admin_actions, pattern="^schedule_delete_\\d+$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^schedule_edit_\\d+$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_day$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_time$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_duration$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^admin_back$")
            ],
            SCHEDULE_EDIT_DAY: [
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_day$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_time$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_duration$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_day_\\d+$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^admin_back$")
            ],
            SCHEDULE_EDIT_TIME: [
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_day$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_time$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_duration$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_schedule_edit_time),
                CallbackQueryHandler(handle_admin_actions, pattern="^admin_back$")
            ],
            SCHEDULE_EDIT_DURATION: [
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_day$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_time$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_duration$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^edit_schedule_duration_\\d+$"),
                CallbackQueryHandler(handle_admin_actions, pattern="^admin_back$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(handle_admin_actions, pattern="^admin_back$")
        ],
        name="schedule",
        persistent=False
    )

    # ConversationHandler для переноса занятия студентом
    reschedule_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(student_reschedule_menu, pattern="^student_reschedule$")],
        states={
            RESCHEDULE_CHOOSE_LESSON: [CallbackQueryHandler(student_reschedule_start, pattern="^reschedule_lesson_\\d+$")],
            RESCHEDULE_CHOOSE_WEEK: [CallbackQueryHandler(student_reschedule_choose_week, pattern="^reschedule_week_\\d+$")],
            RESCHEDULE_CHOOSE_DAY: [CallbackQueryHandler(student_reschedule_choose_day, pattern="^reschedule_day_\\d+$")],
            RESCHEDULE_CHOOSE_TIME: [
                CallbackQueryHandler(student_reschedule_choose_time, pattern="^reschedule_time_\\d{2}:\\d{2}$"),
                CallbackQueryHandler(student_reschedule_choose_time, pattern="^reschedule_time_(prev|next)$"),
                CallbackQueryHandler(student_reschedule_menu, pattern="^student_reschedule$")
            ],
            RESCHEDULE_CONFIRM: [
                CallbackQueryHandler(student_reschedule_confirm, pattern="^reschedule_confirm$"),
                CallbackQueryHandler(student_reschedule_menu, pattern="^student_reschedule$")
            ]
        },
        fallbacks=[CallbackQueryHandler(student_menu, pattern="^student_back$")],
        name="reschedule_handler",
        persistent=False
    )

    # Регистрируем обработчики
    application.add_handler(main_handler)
    application.add_handler(add_student_handler)
    application.add_handler(edit_student_handler)
    application.add_handler(delete_student_handler)
    application.add_handler(homework_handler)  # Перемещаем обработчик заданий выше
    application.add_handler(notes_handler)     # Обработчик конспектов после заданий
    application.add_handler(give_homework_handler)
    application.add_handler(give_variant_handler)
    application.add_handler(statistics_handler)
    application.add_handler(schedule_handler)
    application.add_handler(reschedule_handler)
    # application.add_handler(CommandHandler("start", handle_start))  # Убираем дублирование, так как start уже в main_handler
    application.add_handler(CommandHandler("admin", admin_menu))
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^(admin_|info_type_|student_info_|edit_type_|edit_student_|assign_note_|manual_select_notes|skip_note_assignment|assign_unassigned_note_|schedule_exam_|reschedule_settings).*$"))
    application.add_handler(CallbackQueryHandler(handle_student_actions, pattern="^notif_"))  # Обработчик уведомлений
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^admin_notif_"))  # Обработчик админских уведомлений
    application.add_handler(CallbackQueryHandler(handle_student_actions, pattern="^roadmap_page_"))  # Обработчик навигации роадмапа
    application.add_handler(CallbackQueryHandler(handle_student_actions, pattern="^student_schedule$"))  # Обработчик расписания (выше общего)
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^reschedule_settings$"))
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^reschedule_settings_hours$"))
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^reschedule_settings_days$"))
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^reschedule_settings_interval$"))
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^reschedule_day_"))
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^reschedule_interval_"))
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^reschedule_start_"))
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^reschedule_end_"))
    application.add_handler(CallbackQueryHandler(handle_student_actions, pattern="^reschedule_"))  # Обработчик переноса занятий (выше общего)
    # Обработчики главного меню
    application.add_handler(CallbackQueryHandler(handle_exam_preparation, pattern="^exam_preparation$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_start, pattern="^back_to_start$"))
    
    application.add_handler(CallbackQueryHandler(handle_student_actions, pattern="^set_avatar_"))
    application.add_handler(CallbackQueryHandler(handle_student_actions, pattern="^set_theme_"))
    application.add_handler(CallbackQueryHandler(handle_student_actions, pattern="^student_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_student_text))
    
    # Команда для проверки напоминаний (только для админа)
    application.add_handler(CommandHandler("check_reminders", check_and_send_reminders))
    
    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    # Добавляем первого администратора при запуске
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    if ADMIN_ID:
        db = Database()
        db.add_admin(ADMIN_ID)
    
    main() 