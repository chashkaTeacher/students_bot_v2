from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import enum
import random
import string
import re

Base = declarative_base()

class ExamType(enum.Enum):
    OGE = "ОГЭ"
    EGE = "ЕГЭ"
    SCHOOL = "Школьная программа"

class Admin(Base):
    __tablename__ = 'admins'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)

class Student(Base):
    __tablename__ = 'students'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    telegram_id = Column(Integer, unique=True, nullable=True)
    password = Column(String, nullable=False)
    exam_type = Column(Enum(ExamType))
    lesson_link = Column(String)
    notes = Column(String)
    display_name = Column(String, nullable=True)

class Homework(Base):
    __tablename__ = 'homework'
    
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    link = Column(String, nullable=False)
    exam_type = Column(Enum(ExamType), nullable=False)
    created_at = Column(DateTime, default=func.now())
    file_path = Column(String, nullable=True)  # Путь к файлу домашнего задания
    
    # Создаем уникальный индекс для комбинации title и exam_type
    __table_args__ = (
        UniqueConstraint('title', 'exam_type', name='unique_title_exam_type'),
    )

    def get_task_number(self):
        """Извлекает номер задания из заголовка"""
        # Ищем числа в заголовке
        numbers = re.findall(r'\d+(?:-\d+)?', self.title)
        if not numbers:
            return float('inf')  # Если нет номера, помещаем в конец списка
        
        # Берем первое найденное число
        number = numbers[0]
        if '-' in number:
            # Если это диапазон (например, "19-21"), берем первое число
            number = number.split('-')[0]
        return int(number)

class Note(Base):
    __tablename__ = 'notes'
    
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    link = Column(String, nullable=False)
    exam_type = Column(Enum(ExamType), nullable=False)
    created_at = Column(DateTime, default=func.now())
    file_path = Column(String, nullable=True)  # Путь к файлу конспекта
    
    # Создаем уникальный индекс для комбинации title и exam_type
    __table_args__ = (
        UniqueConstraint('title', 'exam_type', name='unique_note_title_exam_type'),
    )

    def get_task_number(self):
        """Извлекает номер задания из заголовка"""
        # Ищем числа в заголовке
        numbers = re.findall(r'\d+(?:-\d+)?', self.title)
        if not numbers:
            return float('inf')  # Если нет номера, помещаем в конец списка
        
        # Берем первое найденное число
        number = numbers[0]
        if '-' in number:
            # Если это диапазон (например, "19-21"), берем первое число
            number = number.split('-')[0]
        return int(number)

class Database:
    def __init__(self):
        self.engine = create_engine('sqlite:///students.db')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _generate_password(self, length=8):
        """Генерирует случайный пароль"""
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))

    def create_student(self, name: str, exam_type: ExamType = None, lesson_link: str = None) -> dict:
        """Создает нового студента и возвращает его данные"""
        session = self.Session()
        try:
            password = self._generate_password()
            student = Student(
                name=name,
                password=password,
                exam_type=exam_type,
                lesson_link=lesson_link
            )
            session.add(student)
            session.commit()
            
            # Создаем словарь с данными студента
            student_data = {
                'name': student.name,
                'exam_type': student.exam_type.value if student.exam_type else None,
                'lesson_link': student.lesson_link,
                'password': student.password
            }
            return student_data
        finally:
            session.close()

    def is_admin(self, telegram_id: int) -> bool:
        session = self.Session()
        try:
            admin = session.query(Admin).filter_by(telegram_id=telegram_id).first()
            return admin is not None
        finally:
            session.close()

    def add_admin(self, telegram_id: int, username: str = None):
        session = self.Session()
        try:
            existing_admin = session.query(Admin).filter_by(telegram_id=telegram_id).first()
            if not existing_admin:
                admin = Admin(telegram_id=telegram_id, username=username)
                session.add(admin)
                session.commit()
        finally:
            session.close()

    def get_student_by_telegram_id(self, telegram_id: int) -> Student:
        session = self.Session()
        try:
            return session.query(Student).filter_by(telegram_id=telegram_id).first()
        finally:
            session.close()

    def get_student_by_password(self, password: str) -> Student:
        session = self.Session()
        try:
            return session.query(Student).filter_by(password=password).first()
        finally:
            session.close()

    def get_student_by_id(self, student_id: int) -> Student:
        """Получает студента по его ID"""
        session = self.Session()
        try:
            return session.query(Student).filter_by(id=student_id).first()
        finally:
            session.close()

    def update_student_telegram_id(self, student_id: int, telegram_id: int):
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                student.telegram_id = telegram_id
                session.commit()
        finally:
            session.close()

    def get_all_students(self) -> list:
        session = self.Session()
        try:
            return session.query(Student).all()
        finally:
            session.close()

    def get_students_by_exam_type(self, exam_type: ExamType) -> list:
        """Получает список студентов по типу экзамена"""
        session = self.Session()
        try:
            return session.query(Student).filter_by(exam_type=exam_type).all()
        finally:
            session.close()

    def delete_student(self, student_id: int):
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                session.delete(student)
                session.commit()
        finally:
            session.close()

    def update_student_name(self, student_id: int, new_name: str):
        """Обновляет имя студента"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                student.name = new_name
                session.commit()
        finally:
            session.close()

    def update_student_exam_type(self, student_id: int, new_exam_type: ExamType):
        """Обновляет тип экзамена студента"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                student.exam_type = new_exam_type
                session.commit()
        finally:
            session.close()

    def update_student_link(self, student_id: int, new_link: str):
        """Обновляет ссылку на занятие студента"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                student.lesson_link = new_link
                session.commit()
        finally:
            session.close()

    def add_student_note(self, student_id: int, note: str):
        """Добавляет заметку к студенту"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                if student.notes:
                    student.notes += f"\n{note}"
                else:
                    student.notes = note
                session.commit()
        finally:
            session.close()

    def delete_student_note(self, student_id: int):
        """Удаляет заметку студента"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                student.notes = None
                session.commit()
                return True
            return False
        finally:
            session.close()

    def update_student_settings(self, student_id: int, display_name: str = None):
        """Обновляет настройки студента"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                if display_name is not None:
                    student.display_name = display_name
                session.commit()
        finally:
            session.close()

    def reset_student_settings(self, student_id: int):
        """Сбрасывает настройки студента на значения по умолчанию"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                student.display_name = None
                session.commit()
        finally:
            session.close()

    def add_homework(self, title: str, link: str, exam_type: ExamType, file_path: str = None) -> bool:
        """Добавляет новое домашнее задание"""
        session = self.Session()
        try:
            # Проверяем уникальность названия для выбранного экзамена
            existing = session.query(Homework).filter_by(
                title=title,
                exam_type=exam_type
            ).first()
            
            if existing:
                return False
            
            homework = Homework(
                title=title,
                link=link,
                exam_type=exam_type,
                file_path=file_path
            )
            session.add(homework)
            session.commit()
            return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def get_homework_by_exam(self, exam_type: ExamType) -> list:
        """Получает отсортированный список домашних заданий по типу экзамена"""
        session = self.Session()
        try:
            homeworks = session.query(Homework).filter_by(exam_type=exam_type).all()
            # Сортируем задания по номеру
            return sorted(homeworks, key=lambda hw: hw.get_task_number())
        finally:
            session.close()

    def get_homework_by_id(self, homework_id: int) -> Homework:
        """Получает домашнее задание по ID"""
        session = self.Session()
        try:
            return session.query(Homework).filter_by(id=homework_id).first()
        finally:
            session.close()

    def update_homework(self, homework_id: int, title: str = None, link: str = None, exam_type: ExamType = None, file_path: str = None) -> bool:
        """Обновляет информацию о домашнем задании"""
        session = self.Session()
        try:
            homework = session.query(Homework).filter_by(id=homework_id).first()
            if not homework:
                return False

            # Если меняется название или тип экзамена, проверяем уникальность
            if (title or exam_type) and (title != homework.title or exam_type != homework.exam_type):
                existing = session.query(Homework).filter_by(
                    title=title or homework.title,
                    exam_type=exam_type or homework.exam_type
                ).filter(Homework.id != homework_id).first()
                
                if existing:
                    return False

            if title:
                homework.title = title
            if link:
                homework.link = link
            if exam_type:
                homework.exam_type = exam_type
            if file_path:
                homework.file_path = file_path

            session.commit()
            return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def delete_homework(self, homework_id: int) -> bool:
        """Удаляет домашнее задание"""
        session = self.Session()
        try:
            homework = session.query(Homework).filter_by(id=homework_id).first()
            if homework:
                session.delete(homework)
                session.commit()
                return True
            return False
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def add_note(self, title: str, link: str, exam_type: ExamType, file_path: str = None) -> bool:
        """Добавляет новый конспект"""
        session = self.Session()
        try:
            # Проверяем уникальность названия для выбранного экзамена
            existing = session.query(Note).filter_by(
                title=title,
                exam_type=exam_type
            ).first()
            
            if existing:
                return False
            
            note = Note(
                title=title,
                link=link,
                exam_type=exam_type,
                file_path=file_path
            )
            session.add(note)
            session.commit()
            return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def get_notes_by_exam(self, exam_type: ExamType) -> list:
        """Получает отсортированный список конспектов по типу экзамена"""
        session = self.Session()
        try:
            notes = session.query(Note).filter_by(exam_type=exam_type).all()
            # Сортируем конспекты по номеру
            return sorted(notes, key=lambda note: note.get_task_number())
        finally:
            session.close()

    def get_note_by_id(self, note_id: int) -> Note:
        """Получает конспект по ID"""
        session = self.Session()
        try:
            return session.query(Note).filter_by(id=note_id).first()
        finally:
            session.close()

    def update_note(self, note_id: int, title: str = None, link: str = None, exam_type: ExamType = None, file_path: str = None) -> bool:
        """Обновляет информацию о конспекте"""
        session = self.Session()
        try:
            note = session.query(Note).filter_by(id=note_id).first()
            if not note:
                return False

            # Если меняется название или тип экзамена, проверяем уникальность
            if (title or exam_type) and (title != note.title or exam_type != note.exam_type):
                existing = session.query(Note).filter_by(
                    title=title or note.title,
                    exam_type=exam_type or note.exam_type
                ).filter(Note.id != note_id).first()
                
                if existing:
                    return False

            if title:
                note.title = title
            if link:
                note.link = link
            if exam_type:
                note.exam_type = exam_type
            if file_path:
                note.file_path = file_path

            session.commit()
            return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def delete_note(self, note_id: int) -> bool:
        """Удаляет конспект"""
        session = self.Session()
        try:
            note = session.query(Note).filter_by(id=note_id).first()
            if note:
                session.delete(note)
                session.commit()
                return True
            return False
        except:
            session.rollback()
            return False
        finally:
            session.close() 