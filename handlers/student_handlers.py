from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from core.database import Database
from telegram.constants import ParseMode
import os
import datetime

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
    db = context.bot_data['db']
    unread_count = len(db.get_notifications(student.id, only_unread=True)) if student else 0
    notif_text = f"🔔 Уведомления ({unread_count})" if unread_count else "🔔 Уведомления"
    
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
            InlineKeyboardButton(notif_text, callback_data="student_notifications")
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
        msg = await update.callback_query.edit_message_text(
            text=greeting,
            reply_markup=reply_markup
        )
        # Сохраняем message_id в базе
        db.update_student_menu_message_id(student.id, msg.message_id)
    else:
        msg = await update.message.reply_text(
            text=greeting,
            reply_markup=reply_markup
        )
        db.update_student_menu_message_id(student.id, msg.message_id)

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню настроек"""
    user_id = update.effective_user.id
    student = context.bot_data['db'].get_student_by_telegram_id(user_id)
    
    # Определяем текст кнопки в зависимости от текущей настройки
    show_old_text = "👁️ Скрыть старые задания" if student.show_old_homework else "👁️ Показывать старые задания"
    
    keyboard = [
        [
            InlineKeyboardButton("👤 Изменить отображаемое имя", callback_data="student_change_name")
        ],
        [
            InlineKeyboardButton(show_old_text, callback_data="student_toggle_old_homework")
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
    
    # Обрабатываем возможную ошибку устаревшего callback query
    try:
        await query.answer()
    except Exception as e:
        # Игнорируем ошибку устаревшего query
        pass
    
    db: Database = context.bot_data['db']
    user_id = query.from_user.id
    student = db.get_student_by_telegram_id(user_id)

    if query.data == "student_homework":
        # Получаем домашние задания с учетом настройки
        homeworks_data = db.get_homeworks_for_student_with_filter(student.id)
        
        if not homeworks_data:
            await query.edit_message_text(
                text="📚 У вас пока нет выданных домашних заданий.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="student_back")]])
            )
            return
        
        # Создаем список кнопок с группировкой
        keyboard = []
        
        # Разделяем на старые и актуальное задание
        if len(homeworks_data) > 1:
            old_homeworks = homeworks_data[:-1]  # Все кроме последнего
            current_homework = homeworks_data[-1]  # Последнее (актуальное)
            
            # Группируем старые задания по 2 в ряд
            for i in range(0, len(old_homeworks), 2):
                row = []
                for j in range(2):
                    if i + j < len(old_homeworks):
                        homework, _ = old_homeworks[i + j]
                        button_text = f"📚 {homework.title[:25]}{'...' if len(homework.title) > 25 else ''}"
                        row.append(InlineKeyboardButton(button_text, callback_data=f"student_hw_{homework.id}"))
                keyboard.append(row)
            
            # Добавляем актуальное задание отдельной строкой внизу
            current_hw, _ = current_homework
            keyboard.append([InlineKeyboardButton(f"🆕 {current_hw.title}", callback_data=f"student_hw_{current_hw.id}")])
        else:
            # Если только одно задание
            homework, _ = homeworks_data[0]
            keyboard.append([InlineKeyboardButton(f"🆕 {homework.title}", callback_data=f"student_hw_{homework.id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="student_back")])
        
        # Формируем текст с информацией о настройке
        settings_info = ""
        if not student.show_old_homework and len(homeworks_data) > 1:
            settings_info = "\n\nℹ️ Показано только актуальное задание. Включите показ старых заданий в настройках, чтобы увидеть все."
        
        await query.edit_message_text(
            text=f"📚 Ваши выданные домашние задания:{settings_info}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    elif query.data.startswith("student_hw_file_"):
        hw_id = int(query.data.split("_")[-1])
        hw = db.get_homework_by_id(hw_id)
        if not hw:
            await query.message.reply_text(f"❌ Задание не найдено (id={hw_id})")
        elif not hw.file_path:
            await query.message.reply_text(f"❌ У задания нет файла (id={hw_id})")
        else:
            abs_path = os.path.abspath(os.path.normpath(hw.file_path))
            if not os.path.exists(abs_path):
                await query.message.reply_text(f"❌ Файл не найден: {abs_path}")
            else:
                # Сначала убираем меню (заменяем на "⏳ Отправка файла...")
                try:
                    await query.edit_message_text(text="⏳ Отправка файла...")
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        raise
                # Затем отправляем файл отдельным сообщением
                try:
                    await query.message.reply_document(document=abs_path, caption=f"📝 {hw.title}")
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
        
        # Определяем, является ли это актуальным заданием (последним в списке)
        homeworks_data = db.get_homeworks_for_student_with_filter(student.id)
        is_current = False
        if homeworks_data:
            is_current = homeworks_data[-1][0].id == hw_id
        
        # Формируем текст с статусом
        status_text = "🆕 Актуальное задание" if is_current else "📚 Предыдущее задание"
        
        buttons = [[InlineKeyboardButton("Ссылка на задание", url=hw.link)]]
        if hw.file_path:
            buttons.append([InlineKeyboardButton("Скачать файл", callback_data=f"student_hw_file_{hw_id}")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_homework")])
        
        await query.edit_message_text(
            text=f"📝 <b>{hw.title}</b>\n\n{status_text}",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return
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
        issued_date = variant.created_at.strftime('%d.%m.%Y') if variant.created_at else "-"
        # Вычисляем ближайший следующий понедельник
        dt = variant.created_at or datetime.datetime.now()
        days_ahead = 0 if dt.weekday() == 0 else 7 - dt.weekday()
        next_monday = dt + datetime.timedelta(days=days_ahead)
        deadline = next_monday.strftime('%d.%m.%Y')
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
        start = page * per_page
        end = start + per_page
        page_notifications = notifications[start:end]
        notif_texts = []
        for i, notif in enumerate(page_notifications, 1):
            status = "🆕 " if not notif.is_read else "📋 "
            dt = notif.created_at.strftime('%d.%m.%Y в %H:%M') if notif.created_at else ""
            # Тип уведомления на кириллице с эмодзи
            if notif.type == 'homework':
                notif_type = "📚 Домашнее задание"
            elif notif.type == 'variant':
                notif_type = "📄 Вариант"
            else:
                notif_type = "📢 Уведомление"
            
            # Форматируем текст уведомления
            text = f"<b>{status}{notif_type}</b>\n"
            text += f"📅 <i>{dt}</i>\n"
            text += f"📝 {notif.text}"
            
            if notif.link:
                text += f"\n🔗 <a href='{notif.link}'>Открыть ссылку</a>"
            
            # Добавляем разделитель между уведомлениями (кроме последнего)
            if i < len(page_notifications):
                text += "\n─────────────"
            
            notif_texts.append(text)
        
        text = "\n\n".join(notif_texts)
        db.mark_notifications_read(student.id)
        nav_buttons = []
        if start > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="notif_prev"))
        if end < total:
            nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data="notif_next"))
        buttons = []
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([InlineKeyboardButton("🗑️ Очистить все", callback_data="notif_clear")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_back")])
        
        # Красивый заголовок с информацией о страницах
        header = f"🔔 <b>Ваши уведомления</b>\n"
        header += f"📊 Всего: {total} | Страница {page + 1} из {(total + per_page - 1) // per_page}\n"
        header += "─────────────\n\n"
        
        await query.edit_message_text(
            text=header + text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False
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
        start = page * per_page
        end = start + per_page
        page_notifications = notifications[start:end]
        notif_texts = []
        for i, notif in enumerate(page_notifications, 1):
            status = "🆕 " if not notif.is_read else "📋 "
            dt = notif.created_at.strftime('%d.%m.%Y в %H:%M') if notif.created_at else ""
            # Тип уведомления на кириллице с эмодзи
            if notif.type == 'homework':
                notif_type = "📚 Домашнее задание"
            elif notif.type == 'variant':
                notif_type = "📄 Вариант"
            else:
                notif_type = "📢 Уведомление"
            
            # Форматируем текст уведомления
            text = f"<b>{status}{notif_type}</b>\n"
            text += f"📅 <i>{dt}</i>\n"
            text += f"📝 {notif.text}"
            
            if notif.link:
                text += f"\n🔗 <a href='{notif.link}'>Открыть ссылку</a>"
            
            # Добавляем разделитель между уведомлениями (кроме последнего)
            if i < len(page_notifications):
                text += "\n─────────────"
            
            notif_texts.append(text)
        
        text = "\n\n".join(notif_texts)
        db.mark_notifications_read(student.id)
        nav_buttons = []
        if start > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="notif_prev"))
        if end < total:
            nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data="notif_next"))
        buttons = []
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([InlineKeyboardButton("🗑️ Очистить все", callback_data="notif_clear")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_back")])
        
        # Красивый заголовок с информацией о страницах
        header = f"🔔 <b>Ваши уведомления</b>\n"
        header += f"📊 Всего: {total} | Страница {page + 1} из {(total + per_page - 1) // per_page}\n"
        header += "─────────────\n\n"
        
        await query.edit_message_text(
            text=header + text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False
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
        start = page * per_page
        end = start + per_page
        page_notifications = notifications[start:end]
        notif_texts = []
        for i, notif in enumerate(page_notifications, 1):
            status = "🆕 " if not notif.is_read else "📋 "
            dt = notif.created_at.strftime('%d.%m.%Y в %H:%M') if notif.created_at else ""
            # Тип уведомления на кириллице с эмодзи
            if notif.type == 'homework':
                notif_type = "📚 Домашнее задание"
            elif notif.type == 'variant':
                notif_type = "📄 Вариант"
            else:
                notif_type = "📢 Уведомление"
            
            # Форматируем текст уведомления
            text = f"<b>{status}{notif_type}</b>\n"
            text += f"📅 <i>{dt}</i>\n"
            text += f"📝 {notif.text}"
            
            if notif.link:
                text += f"\n🔗 <a href='{notif.link}'>Открыть ссылку</a>"
            
            # Добавляем разделитель между уведомлениями (кроме последнего)
            if i < len(page_notifications):
                text += "\n─────────────"
            
            notif_texts.append(text)
        
        text = "\n\n".join(notif_texts)
        db.mark_notifications_read(student.id)
        nav_buttons = []
        if start > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="notif_prev"))
        if end < total:
            nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data="notif_next"))
        buttons = []
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([InlineKeyboardButton("🗑️ Очистить все", callback_data="notif_clear")])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="student_back")])
        
        # Красивый заголовок с информацией о страницах
        header = f"🔔 <b>Ваши уведомления</b>\n"
        header += f"📊 Всего: {total} | Страница {page + 1} из {(total + per_page - 1) // per_page}\n"
        header += "─────────────\n\n"
        
        await query.edit_message_text(
            text=header + text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False
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

async def handle_student_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    
    # Обрабатываем возможную ошибку устаревшего callback query
    try:
        await query.answer()
    except Exception as e:
        # Игнорируем ошибку устаревшего query
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

async def handle_student_edit_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор действия при редактировании"""
    query = update.callback_query
    
    # Обрабатываем возможную ошибку устаревшего callback query
    try:
        await query.answer()
    except Exception as e:
        # Игнорируем ошибку устаревшего query
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

async def send_student_menu_by_chat_id(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Отправляет меню студента по chat_id (без update), удаляя предыдущее меню если оно есть"""
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
            # Игнорируем ошибку, если сообщение уже удалено или не найдено
            pass
    # Считаем количество непрочитанных уведомлений
    unread_count = len(db.get_notifications(student.id, only_unread=True))
    notif_text = f"🔔 Уведомления ({unread_count})" if unread_count else "🔔 Уведомления"
    keyboard = [
        [InlineKeyboardButton("📚 Домашнее задание", callback_data="student_homework")],
        [InlineKeyboardButton("📝 Конспекты", callback_data="student_notes")],
        [InlineKeyboardButton("📅 Расписание", callback_data="student_schedule"), InlineKeyboardButton("🔗 Подключиться к занятию", callback_data="student_join_lesson")],
        [InlineKeyboardButton("📄 Актуальный вариант", callback_data="student_current_variant")],
        [InlineKeyboardButton(notif_text, callback_data="student_notifications")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="student_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    display_name = student.display_name or student.name
    greeting = f"👋 Привет, {display_name}!"
    msg = await context.bot.send_message(chat_id=chat_id, text=greeting, reply_markup=reply_markup)
    db.update_student_menu_message_id(student.id, msg.message_id) 