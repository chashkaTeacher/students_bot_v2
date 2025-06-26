from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import declarative_base
from core.database import Database

Base = declarative_base()

def migrate_database():
    """Выполняет миграцию базы данных"""
    engine = create_engine('sqlite:///students.db')
    
    # Проверяем наличие таблицы students
    inspector = inspect(engine)
    if not inspector.has_table("students"):
        Base.metadata.create_all(engine)
        return
    
    # Получаем список существующих колонок
    columns = inspector.get_columns("students")
    column_names = [col["name"] for col in columns]
    
    # Добавляем новые колонки, если их нет
    with engine.connect() as connection:
        if "display_name" not in column_names:
            connection.execute(text("ALTER TABLE students ADD COLUMN display_name VARCHAR"))
        connection.commit()

    # Добавляем столбец notes в таблицу students, если его нет
    with engine.connect() as connection:
        # Проверяем, существует ли столбец notes
        result = connection.execute(text("""
            SELECT name FROM pragma_table_info('students') 
            WHERE name = 'notes'
        """))
        if not result.fetchone():
            connection.execute(text("""
                ALTER TABLE students 
                ADD COLUMN notes TEXT
            """))
            connection.commit()
            print("✅ Миграция успешно выполнена: добавлен столбец notes")

    # Добавляем столбец last_menu_message_id в таблицу students, если его нет
    with engine.connect() as connection:
        result = connection.execute(text("""
            SELECT name FROM pragma_table_info('students') 
            WHERE name = 'last_menu_message_id'
        """))
        if not result.fetchone():
            connection.execute(text("""
                ALTER TABLE students 
                ADD COLUMN last_menu_message_id INTEGER
            """))
            connection.commit()
            print("✅ Миграция: добавлен столбец last_menu_message_id")

    # Создаем таблицу homework, если её нет
    if not inspector.has_table("homework"):
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE homework (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR NOT NULL,
                    link VARCHAR NOT NULL,
                    exam_type VARCHAR NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    file_path VARCHAR
                )
            """))
            # Создаем уникальный индекс
            connection.execute(text("""
                CREATE UNIQUE INDEX unique_title_exam 
                ON homework (title, exam_type)
            """))
            connection.commit()
            print("✅ Миграция успешно выполнена: создана таблица homework")
    else:
        # Проверяем наличие столбца file_path в таблице homework
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT name FROM pragma_table_info('homework') 
                WHERE name = 'file_path'
            """))
            
            if not result.fetchone():
                connection.execute(text("""
                    ALTER TABLE homework 
                    ADD COLUMN file_path VARCHAR
                """))
                connection.commit()
                print("✅ Миграция успешно выполнена: добавлен столбец file_path в таблицу homework")

    # Создаем таблицу notes, если её нет
    if not inspector.has_table("notes"):
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR NOT NULL,
                    link VARCHAR NOT NULL,
                    exam_type VARCHAR NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    file_path VARCHAR
                )
            """))
            # Создаем уникальный индекс
            connection.execute(text("""
                CREATE UNIQUE INDEX unique_note_title_exam 
                ON notes (title, exam_type)
            """))
            connection.commit()
            print("✅ Миграция успешно выполнена: создана таблица notes")
    else:
        # Проверяем наличие столбца file_path в таблице notes
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT name FROM pragma_table_info('notes') 
                WHERE name = 'file_path'
            """))
            
            if not result.fetchone():
                connection.execute(text("""
                    ALTER TABLE notes 
                    ADD COLUMN file_path VARCHAR
                """))
                connection.commit()
                print("✅ Миграция успешно выполнена: добавлен столбец file_path в таблицу notes")

    # Создаем таблицу student_homework, если её нет
    if not inspector.has_table("student_homework"):
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE student_homework (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    homework_id INTEGER NOT NULL,
                    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR DEFAULT 'assigned',
                    FOREIGN KEY(student_id) REFERENCES students(id),
                    FOREIGN KEY(homework_id) REFERENCES homework(id)
                )
            """))
            connection.commit()
            print("✅ Миграция успешно выполнена: создана таблица student_homework")

def run_migrations():
    """Запускает все миграции базы данных"""
    db = Database()
    engine = db.engine
    
    # Миграция 1: Добавление поля show_old_homework в таблицу students
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(students)"))
            columns = [row[1] for row in result.fetchall()]
            if 'show_old_homework' not in columns:
                conn.execute(text("ALTER TABLE students ADD COLUMN show_old_homework BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("✅ Миграция 1 выполнена: добавлено поле show_old_homework")
            else:
                print("ℹ️ Миграция 1 уже выполнена: поле show_old_homework уже существует")
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции 1: {e}")

    # Миграция 2: Создание таблицы variants
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='variants'"))
            if not result.fetchone():
                conn.execute(text('''
                    CREATE TABLE variants (
                        id INTEGER PRIMARY KEY,
                        exam_type VARCHAR(20) NOT NULL,
                        link TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                '''))
                conn.commit()
                print("✅ Миграция 2 выполнена: создана таблица variants")
            else:
                print("ℹ️ Миграция 2 уже выполнена: таблица variants уже существует")
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции 2: {e}")

    # Миграция 3: Создание таблицы notifications
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"))
            if not result.fetchone():
                conn.execute(text('''
                    CREATE TABLE notifications (
                        id INTEGER PRIMARY KEY,
                        student_id INTEGER NOT NULL,
                        type VARCHAR(20) NOT NULL,
                        text TEXT NOT NULL,
                        link TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_read BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY(student_id) REFERENCES students(id)
                    )
                '''))
                conn.commit()
                print("✅ Миграция 3 выполнена: создана таблица notifications")
            else:
                print("ℹ️ Миграция 3 уже выполнена: таблица notifications уже существует")
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции 3: {e}")

if __name__ == "__main__":
    run_migrations() 