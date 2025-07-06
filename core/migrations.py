from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import declarative_base
from core.database import Base
import sqlite3
import os

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
    
    # Миграция 16: создание таблицы schedule
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    time VARCHAR NOT NULL,
                    duration INTEGER DEFAULT 60,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students (id),
                    UNIQUE(student_id, day_of_week, time)
                )
            """))
            conn.commit()
    except Exception:
        pass  # Таблица уже существует
    
    # Миграция 17: создание таблицы push_messages
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
    
    # Миграция 18: создание таблицы student_notes
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
    
    # Миграция 19: исправление столбца admin_id на user_id в pending_note_assignments
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
    engine = create_engine('sqlite:///students.db')
    
    # Миграция 1: Добавление поля show_old_homework в таблицу students
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(students)"))
            columns = [row[1] for row in result.fetchall()]
            if 'show_old_homework' not in columns:
                conn.execute(text("ALTER TABLE students ADD COLUMN show_old_homework BOOLEAN DEFAULT FALSE"))
                conn.commit()
    except Exception as e:
        pass

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
    except Exception as e:
        pass

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
    except Exception as e:
        pass

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
    except Exception as e:
        pass

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
    except Exception as e:
        pass

    # Миграция 6: Добавление таблиц для переносов
    try:
        with engine.connect() as conn:
            # Проверяем, существует ли таблица reschedule_requests
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='reschedule_requests'"))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE reschedule_requests (
                        id INTEGER PRIMARY KEY,
                        student_id INTEGER NOT NULL,
                        schedule_id INTEGER NOT NULL,
                        original_date DATETIME NOT NULL,
                        original_time VARCHAR NOT NULL,
                        requested_date DATETIME NOT NULL,
                        requested_time VARCHAR NOT NULL,
                        status VARCHAR DEFAULT 'pending',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students (id),
                        FOREIGN KEY (schedule_id) REFERENCES schedule (id)
                    )
                """))
                
            # Проверяем, существует ли таблица reschedule_settings
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='reschedule_settings'"))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE reschedule_settings (
                        id INTEGER PRIMARY KEY,
                        work_start_time VARCHAR DEFAULT '10:00',
                        work_end_time VARCHAR DEFAULT '19:00',
                        available_days VARCHAR DEFAULT '0,1,2,3,4,5,6',
                        max_weeks_ahead INTEGER DEFAULT 2,
                        slot_interval INTEGER DEFAULT 15
                    )
                """))
                
                # Добавляем настройки по умолчанию
                conn.execute(text("""
                    INSERT INTO reschedule_settings (work_start_time, work_end_time, available_days, max_weeks_ahead, slot_interval)
                    VALUES ('10:00', '19:00', '0,1,2,3,4,5,6', 2, 15)
                """))
                
            conn.commit()
            
    except Exception as e:
        pass

def run_all_migrations():
    db_path = 'students.db'
    if not os.path.exists(db_path):
        print('База данных не найдена!')
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Добавление поля menu_message_id в admins
    cursor.execute("PRAGMA table_info(admins);")
    columns = [col[1] for col in cursor.fetchall()]
    if 'menu_message_id' not in columns:
        cursor.execute("ALTER TABLE admins ADD COLUMN menu_message_id INTEGER;")

    # 2. Добавление поля admin_id в notifications
    cursor.execute("PRAGMA table_info(notifications);")
    columns = [col[1] for col in cursor.fetchall()]
    if 'admin_id' not in columns:
        cursor.execute("ALTER TABLE notifications ADD COLUMN admin_id INTEGER;")

    # 3. Создание таблицы admin_push_messages
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_push_messages'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE admin_push_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    # 4. Исправление ограничений в notifications (если нужно)
    # Проверяем, есть ли нужные столбцы и ограничения
    cursor.execute("PRAGMA table_info(notifications);")
    columns = [col[1] for col in cursor.fetchall()]
    if 'admin_id' in columns and 'student_id' in columns:
        # Проверим, есть ли нужные ограничения (FOREIGN KEY)
        cursor.execute("PRAGMA foreign_key_list(notifications);")
        fks = cursor.fetchall()
        fk_students = any('students' in fk for fk in fks)
        fk_admins = any('admins' in fk for fk in fks)
        if not (fk_students and fk_admins):
            # Делаем пересоздание таблицы
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications_new (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER,
                    admin_id INTEGER,
                    type VARCHAR(20) NOT NULL,
                    text TEXT NOT NULL,
                    link TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_read BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY(student_id) REFERENCES students(id),
                    FOREIGN KEY(admin_id) REFERENCES admins(id)
                )
            """)
            cursor.execute("""
                INSERT INTO notifications_new (id, student_id, admin_id, type, text, link, created_at, is_read)
                SELECT id, student_id, admin_id, type, text, link, created_at, is_read
                FROM notifications
            """)
            cursor.execute("DROP TABLE notifications")
            cursor.execute("ALTER TABLE notifications_new RENAME TO notifications")

    conn.commit()
    conn.close()

    # 5. Добавление полей avatar_emoji и theme в таблицу students
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(students)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'avatar_emoji' not in columns:
                conn.execute(text("ALTER TABLE students ADD COLUMN avatar_emoji VARCHAR"))
                conn.commit()
                
            if 'theme' not in columns:
                conn.execute(text("ALTER TABLE students ADD COLUMN theme VARCHAR"))
                conn.commit()
    except Exception as e:
        pass

if __name__ == "__main__":
    run_all_migrations() 