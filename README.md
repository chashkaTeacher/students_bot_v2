# Student Bot

Telegram бот для управления студентами и домашними заданиями.

## Функциональность

- Управление студентами (добавление, редактирование, удаление)
- Управление домашними заданиями
- Разделение по типам экзаменов (ОГЭ, ЕГЭ, Школьная программа)
- Система заметок для студентов
- Административный интерфейс
- Студенческий интерфейс

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/your-username/student-bot.git
cd student-bot
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` и добавьте необходимые переменные окружения:
```
TELEGRAM_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_id
```

5. Запустите бота:
```bash
python bot.py
```

## Структура проекта

```
student_bot/
├── bot.py              # Основной файл бота
├── requirements.txt    # Зависимости проекта
├── .env               # Переменные окружения
├── .gitignore         # Игнорируемые файлы
├── core/              # Основные компоненты
│   ├── database.py    # Работа с базой данных
│   └── migrations.py  # Миграции базы данных
└── handlers/          # Обработчики команд
    ├── admin_handlers.py    # Обработчики для администраторов
    ├── student_handlers.py  # Обработчики для студентов
    ├── homework_handlers.py # Обработчики домашних заданий
    └── common_handlers.py   # Общие обработчики
```

## Использование

1. Запустите бота командой `/start`
2. Введите пароль для доступа к административной панели
3. Используйте меню для управления студентами и домашними заданиями

## Лицензия

MIT 