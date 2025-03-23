from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base

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
        # Проверяем, существует ли столбец
        result = connection.execute(text("""
            SELECT name FROM pragma_table_info('students') 
            WHERE name = 'notes'
        """))
        
        if not result.fetchone():
            # Если столбца нет, добавляем его
            connection.execute(text("""
                ALTER TABLE students 
                ADD COLUMN notes TEXT
            """))
            connection.commit()
            print("✅ Миграция успешно выполнена: добавлен столбец notes")

    # Создаем таблицу homework, если её нет
    if not inspector.has_table("homework"):
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE homework (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR NOT NULL,
                    link VARCHAR NOT NULL,
                    exam_type VARCHAR NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            # Создаем уникальный индекс
            connection.execute(text("""
                CREATE UNIQUE INDEX unique_title_exam 
                ON homework (title, exam_type)
            """))
            connection.commit()
            print("✅ Миграция успешно выполнена: создана таблица homework") 