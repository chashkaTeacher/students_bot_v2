from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import declarative_base
from core.database import Database

Base = declarative_base()

def migrate_database():
    """Выполняет миграции базы данных"""
    engine = create_engine('sqlite:///students.db')
    Base.metadata.create_all(engine)
    
    # Миграция 1: добавление поля notes
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE students ADD COLUMN notes TEXT"))
            conn.commit()
    except Exception:
        pass  # Поле уже существует
    
    # Миграция 2: добавление поля last_menu_message_id
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE students ADD COLUMN last_menu_message_id INTEGER"))
            conn.commit()
    except Exception:
        pass  # Поле уже существует
    
    # Миграция 3: создание таблицы homework
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE homework (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR NOT NULL,
                    link VARCHAR NOT NULL,
                    exam_type VARCHAR NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    file_path VARCHAR
                )
            """))
            conn.commit()
    except Exception:
        pass  # Таблица уже существует
    
    # Миграция 4: добавление столбца file_path в таблицу homework
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE homework ADD COLUMN file_path VARCHAR"))
            conn.commit()
    except Exception:
        pass  # Столбец уже существует
    
    # Миграция 5: создание таблицы notes
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR NOT NULL,
                    link VARCHAR NOT NULL,
                    exam_type VARCHAR NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    file_path VARCHAR
                )
            """))
            conn.commit()
    except Exception:
        pass  # Таблица уже существует
    
    # Миграция 6: добавление столбца file_path в таблицу notes
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE notes ADD COLUMN file_path VARCHAR"))
            conn.commit()
    except Exception:
        pass  # Столбец уже существует
    
    # Миграция 7: создание таблицы student_homework
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE student_homework (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    homework_id INTEGER NOT NULL,
                    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR DEFAULT 'assigned',
                    FOREIGN KEY (student_id) REFERENCES students (id),
                    FOREIGN KEY (homework_id) REFERENCES homework (id)
                )
            """))
            conn.commit()
    except Exception:
        pass  # Таблица уже существует
    
    # Миграция 8: создание таблицы pending_note_assignments
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE pending_note_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    note_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    process_id VARCHAR,
                    step VARCHAR DEFAULT 'choose_note',
                    origin VARCHAR DEFAULT 'manual'
                )
            """))
            conn.commit()
    except Exception:
        pass  # Таблица уже существует
    
    # Миграция 9: добавление столбца process_id в pending_note_assignments
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE pending_note_assignments ADD COLUMN process_id VARCHAR"))
            conn.commit()
    except Exception:
        pass  # Столбец уже существует
    
    # Миграция 10: добавление столбца step в pending_note_assignments
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE pending_note_assignments ADD COLUMN step VARCHAR DEFAULT 'choose_note'"))
            conn.commit()
    except Exception:
        pass  # Столбец уже существует
    
    # Миграция 11: добавление столбца origin в pending_note_assignments
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE pending_note_assignments ADD COLUMN origin VARCHAR DEFAULT 'manual'"))
            conn.commit()
    except Exception:
        pass  # Столбец уже существует
    
    # Миграция 12: пересоздание таблицы pending_note_assignments с правильной структурой
    try:
        with engine.connect() as conn:
            # Проверяем, есть ли данные в таблице
            result = conn.execute(text("SELECT COUNT(*) FROM pending_note_assignments"))
            count = result.scalar()
            
            if count > 0:
                pass  # Есть данные, пропускаем миграцию
            else:
                # Удаляем старую таблицу и создаем новую
                conn.execute(text("DROP TABLE IF EXISTS pending_note_assignments"))
                conn.execute(text("""
                    CREATE TABLE pending_note_assignments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        student_id INTEGER NOT NULL,
                        note_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        process_id VARCHAR,
                        step VARCHAR DEFAULT 'choose_note',
                        origin VARCHAR DEFAULT 'manual'
                    )
                """))
                conn.commit()
    except Exception:
        pass  # Таблица уже существует
    
    # Миграция 13: добавление поля show_old_homework
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE students ADD COLUMN show_old_homework BOOLEAN DEFAULT 0"))
            conn.commit()
    except Exception:
        pass  # Поле уже существует
    
    # Миграция 14: создание таблицы variants
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE variants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_type VARCHAR NOT NULL,
                    link VARCHAR NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
    except Exception:
        pass  # Таблица уже существует
    
    # Миграция 15: создание таблицы notifications
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    type VARCHAR NOT NULL,
                    text TEXT NOT NULL,
                    link VARCHAR,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_read BOOLEAN DEFAULT 0,
                    FOREIGN KEY (student_id) REFERENCES students (id)
                )
            """))
            conn.commit()
    except Exception:
        pass  # Таблица уже существует
    
    # Миграция 16: создание таблицы push_messages
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE push_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES students (id)
                )
            """))
            conn.commit()
    except Exception:
        pass  # Таблица уже существует
    
    # Миграция 17: создание таблицы student_notes
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE student_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    note_id INTEGER NOT NULL,
                    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students (id),
                    FOREIGN KEY (note_id) REFERENCES notes (id)
                )
            """))
            conn.commit()
    except Exception:
        pass  # Таблица уже существует
    
    # Миграция 18: исправление столбца admin_id на user_id в pending_note_assignments
    try:
        with engine.connect() as conn:
            # Проверяем, есть ли столбец admin_id
            result = conn.execute(text("PRAGMA table_info(pending_note_assignments)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'admin_id' in columns and 'user_id' not in columns:
                # Создаем временную таблицу с правильной структурой
                conn.execute(text("""
                    CREATE TABLE pending_note_assignments_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        student_id INTEGER NOT NULL,
                        note_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        process_id VARCHAR,
                        step VARCHAR DEFAULT 'choose_note',
                        origin VARCHAR DEFAULT 'manual'
                    )
                """))
                
                # Копируем данные из старой таблицы
                conn.execute(text("""
                    INSERT INTO pending_note_assignments_new 
                    (id, user_id, student_id, note_id, created_at, process_id, step, origin)
                    SELECT id, admin_id, student_id, note_id, created_at, process_id, step, origin
                    FROM pending_note_assignments
                """))
                
                # Удаляем старую таблицу и переименовываем новую
                conn.execute(text("DROP TABLE pending_note_assignments"))
                conn.execute(text("ALTER TABLE pending_note_assignments_new RENAME TO pending_note_assignments"))
                conn.commit()
    except Exception:
        pass  # Миграция уже выполнена или не нужна

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

    # Миграция 4: Создание таблицы push_messages
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='push_messages'"))
            if not result.fetchone():
                conn.execute(text('''
                    CREATE TABLE push_messages (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        message_id INTEGER NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                '''))
                conn.commit()
                print("✅ Миграция 4 выполнена: создана таблица push_messages")
            else:
                print("ℹ️ Миграция 4 уже выполнена: таблица push_messages уже существует")
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции 4: {e}")

    # Миграция 5: Создание таблицы student_notes
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='student_notes'"))
            if not result.fetchone():
                conn.execute(text('''
                    CREATE TABLE student_notes (
                        id INTEGER PRIMARY KEY,
                        student_id INTEGER NOT NULL,
                        note_id INTEGER NOT NULL,
                        assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(student_id) REFERENCES students(id),
                        FOREIGN KEY(note_id) REFERENCES notes(id),
                        UNIQUE(student_id, note_id)
                    )
                '''))
                conn.commit()
                print("✅ Миграция 5 выполнена: создана таблица student_notes")
            else:
                print("ℹ️ Миграция 5 уже выполнена: таблица student_notes уже существует")
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции 5: {e}")

if __name__ == "__main__":
    run_migrations() 