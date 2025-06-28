from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timedelta
import enum
import random
import string
import re
import urllib.parse
import pytz

Base = declarative_base()

def to_moscow_time(dt: datetime) -> datetime:
    """Конвертирует время в московское время (UTC+3)"""
    if dt is None:
        return None
    
    # Если время уже с timezone, конвертируем его
    if dt.tzinfo is not None:
        moscow_tz = pytz.timezone('Europe/Moscow')
        return dt.astimezone(moscow_tz)
    
    # Если время без timezone, считаем что это UTC и конвертируем
    utc_tz = pytz.UTC
    moscow_tz = pytz.timezone('Europe/Moscow')
    utc_dt = utc_tz.localize(dt)
    return utc_dt.astimezone(moscow_tz)

def format_moscow_time(dt: datetime, format_str: str = '%d.%m.%Y в %H:%M') -> str:
    """Форматирует время в московском времени"""
    if dt is None:
        return ""
    
    moscow_dt = to_moscow_time(dt)
    return moscow_dt.strftime(format_str)

def is_valid_url(url: str) -> bool:
    """Проверяет, является ли строка валидным URL"""
    if not url or not isinstance(url, str):
        return False
    
    # Убираем пробелы в начале и конце
    url = url.strip()
    
    # Проверяем, что URL не пустой
    if not url:
        return False
    
    try:
        # Парсим URL
        result = urllib.parse.urlparse(url)
        
        # Проверяем, что есть схема (http, https, ftp и т.д.)
        if not result.scheme:
            return False
        
        # Проверяем, что есть домен
        if not result.netloc:
            return False
        
        # Проверяем, что схема поддерживается
        valid_schemes = ['http', 'https', 'ftp', 'ftps']
        if result.scheme.lower() not in valid_schemes:
            return False
        
        return True
    except Exception:
        return False

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
    show_old_homework = Column(Boolean, default=False)  # Показывать ли старые домашние задания
    last_menu_message_id = Column(Integer, nullable=True)  # ID последнего сообщения с меню

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

class StudentHomework(Base):
    __tablename__ = 'student_homework'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    homework_id = Column(Integer, ForeignKey('homework.id'), nullable=False)
    assigned_at = Column(DateTime, default=func.now())
    status = Column(String, default='assigned')

class Variant(Base):
    __tablename__ = 'variants'
    id = Column(Integer, primary_key=True)
    exam_type = Column(Enum(ExamType), nullable=False)
    link = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())

class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    type = Column(String, nullable=False)  # 'homework', 'variant', etc.
    text = Column(String, nullable=False)
    link = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    is_read = Column(Boolean, default=False)

class PushMessage(Base):
    __tablename__ = 'push_messages'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    message_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())

class StudentNote(Base):
    __tablename__ = 'student_notes'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    note_id = Column(Integer, ForeignKey('notes.id'), nullable=False)
    assigned_at = Column(DateTime, default=func.now())
    
    # Создаем уникальный индекс для предотвращения дублирования
    __table_args__ = (
        UniqueConstraint('student_id', 'note_id', name='unique_student_note'),
    )

class PendingNoteAssignment(Base):
    __tablename__ = 'pending_note_assignments'
    id = Column(Integer, primary_key=True)
    process_id = Column(String, nullable=False, unique=True)  # UUID процесса
    user_id = Column(Integer, nullable=False)
    note_id = Column(Integer, nullable=True)
    student_id = Column(Integer, nullable=True)
    step = Column(String, nullable=True)  # этап процесса (например, 'choose_note', 'confirm')
    origin = Column(String, nullable=True)  # источник процесса (например, 'give_homework', 'check_unassigned')
    created_at = Column(DateTime, default=func.now())

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
            # Удаляем связанные уведомления
            session.query(Notification).filter_by(student_id=student_id).delete()
            # Удаляем связанные push-сообщения
            session.query(PushMessage).filter_by(user_id=student_id).delete()
            # Удаляем связанные назначения домашних заданий
            session.query(StudentHomework).filter_by(student_id=student_id).delete()
            # Удаляем самого студента
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
        """Обновляет тип экзамена студента и очищает нерелевантные назначения"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                old_exam_type = student.exam_type
                student.exam_type = new_exam_type
                
                # Если тип экзамена изменился, очищаем нерелевантные назначения
                if old_exam_type != new_exam_type:
                    # Удаляем назначения домашних заданий старого типа экзамена
                    old_homeworks = session.query(StudentHomework).join(Homework).filter(
                        StudentHomework.student_id == student_id,
                        Homework.exam_type == old_exam_type
                    ).all()
                    
                    for sh in old_homeworks:
                        session.delete(sh)
                    
                    # Удаляем назначения конспектов старого типа экзамена
                    old_notes = session.query(StudentNote).join(Note).filter(
                        StudentNote.student_id == student_id,
                        Note.exam_type == old_exam_type
                    ).all()
                    
                    for sn in old_notes:
                        session.delete(sn)
                    
                    # Очищаем уведомления и push-сообщения
                    session.query(Notification).filter_by(student_id=student_id).delete()
                    session.query(PushMessage).filter_by(user_id=student_id).delete()
                
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

    def update_student_settings(self, student_id: int, display_name: str = None, show_old_homework: bool = None):
        """Обновляет настройки студента"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                if display_name is not None:
                    student.display_name = display_name
                if show_old_homework is not None:
                    student.show_old_homework = show_old_homework
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
                student.show_old_homework = False
                session.commit()
        finally:
            session.close()

    def update_student_show_old_homework(self, student_id: int, show_old: bool):
        """Обновляет настройку показа старых домашних заданий"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                student.show_old_homework = show_old
                session.commit()
        finally:
            session.close()

    def get_homeworks_for_student_with_filter(self, student_id: int, show_old: bool = None) -> list:
        """Получает домашние задания для студента с учетом настройки показа старых заданий"""
        session = self.Session()
        try:
            # Получаем все назначенные задания
            assigned = session.query(StudentHomework).filter_by(student_id=student_id).all()
            
            if not assigned:
                return []
            
            # Если show_old не указан, берем из настроек студента
            if show_old is None:
                student = session.query(Student).filter_by(id=student_id).first()
                show_old = student.show_old_homework if student else False
            
            # Получаем информацию о заданиях
            homeworks = []
            for sh in assigned:
                homework = session.query(Homework).filter_by(id=sh.homework_id).first()
                if homework:
                    homeworks.append((homework, sh.assigned_at))
            
            # Сортируем по номеру в названии (1, 2, 3, 11, 23...)
            homeworks.sort(key=lambda x: x[0].get_task_number())
            
            # Если не показывать старые, возвращаем только самое новое (последнее по номеру)
            if not show_old and homeworks:
                return [homeworks[-1]]
            
            return homeworks
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

    def is_homework_assigned_to_student(self, student_id: int, homework_id: int) -> bool:
        """Проверяет, назначено ли задание студенту"""
        session = self.Session()
        try:
            existing = session.query(StudentHomework).filter_by(
                student_id=student_id, 
                homework_id=homework_id
            ).first()
            return existing is not None
        finally:
            session.close()

    def assign_homework_to_student(self, student_id: int, homework_id: int) -> bool:
        session = self.Session()
        try:
            # Проверяем, не назначено ли уже это задание этому студенту
            existing = session.query(StudentHomework).filter_by(student_id=student_id, homework_id=homework_id).first()
            if existing:
                # Если задание уже назначено, обновляем дату назначения
                existing.assigned_at = datetime.now()
                session.commit()
                return True
            else:
                # Если задание не назначено, создаем новую запись
                sh = StudentHomework(student_id=student_id, homework_id=homework_id)
                session.add(sh)
                session.commit()
                return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def get_homeworks_for_student(self, student_id: int) -> list:
        session = self.Session()
        try:
            return session.query(StudentHomework).filter_by(student_id=student_id).all()
        finally:
            session.close()

    def add_variant(self, exam_type: ExamType, link: str) -> bool:
        session = self.Session()
        try:
            variant = Variant(exam_type=exam_type, link=link)
            session.add(variant)
            session.commit()
            return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def get_latest_variant(self, exam_type: ExamType):
        session = self.Session()
        try:
            return session.query(Variant).filter_by(exam_type=exam_type).order_by(Variant.created_at.desc()).first()
        finally:
            session.close()

    def add_notification(self, student_id: int, notif_type: str, text: str, link: str = None):
        session = self.Session()
        try:
            notif = Notification(student_id=student_id, type=notif_type, text=text, link=link)
            session.add(notif)
            session.commit()
        finally:
            session.close()

    def get_notifications(self, student_id: int, only_unread: bool = False):
        session = self.Session()
        try:
            q = session.query(Notification).filter_by(student_id=student_id)
            if only_unread:
                q = q.filter_by(is_read=False)
            return q.order_by(Notification.created_at.asc()).all()
        finally:
            session.close()

    def mark_notifications_read(self, student_id: int):
        session = self.Session()
        try:
            session.query(Notification).filter_by(student_id=student_id, is_read=False).update({Notification.is_read: True})
            session.commit()
        finally:
            session.close()

    def has_unread_notifications(self, student_id: int) -> bool:
        session = self.Session()
        try:
            return session.query(Notification).filter_by(student_id=student_id, is_read=False).count() > 0
        finally:
            session.close()

    def update_student_menu_message_id(self, student_id: int, message_id: int):
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                student.last_menu_message_id = message_id
                session.commit()
        finally:
            session.close()

    def get_student_menu_message_id(self, student_id: int) -> int:
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                return student.last_menu_message_id
            return None
        finally:
            session.close()

    def clear_notifications(self, student_id: int):
        session = self.Session()
        try:
            session.query(Notification).filter_by(student_id=student_id).delete()
            session.commit()
        finally:
            session.close()

    def add_push_message(self, user_id: int, message_id: int):
        session = self.Session()
        try:
            push = PushMessage(user_id=user_id, message_id=message_id)
            session.add(push)
            session.commit()
        finally:
            session.close()

    def get_push_messages(self, user_id: int):
        session = self.Session()
        try:
            return session.query(PushMessage).filter_by(user_id=user_id).all()
        finally:
            session.close()

    def clear_push_messages(self, user_id: int):
        """Очищает push-сообщения пользователя"""
        session = self.Session()
        try:
            push_messages = session.query(PushMessage).filter_by(user_id=user_id).all()
            for msg in push_messages:
                session.delete(msg)
            session.commit()
        finally:
            session.close()

    # Методы для работы с конспектами учеников
    def assign_note_to_student(self, student_id: int, note_id: int) -> bool:
        """Назначает конспект ученику"""
        session = self.Session()
        try:
            # Проверяем, не назначен ли уже этот конспект этому ученику
            existing = session.query(StudentNote).filter_by(
                student_id=student_id, 
                note_id=note_id
            ).first()
            
            if existing:
                # Если конспект уже назначен, обновляем дату назначения
                existing.assigned_at = datetime.now()
                session.commit()
                return True
            else:
                # Если конспект не назначен, создаем новую запись
                student_note = StudentNote(student_id=student_id, note_id=note_id)
                session.add(student_note)
                session.commit()
                return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def is_note_assigned_to_student(self, student_id: int, note_id: int) -> bool:
        """Проверяет, назначен ли конспект ученику"""
        session = self.Session()
        try:
            existing = session.query(StudentNote).filter_by(
                student_id=student_id, 
                note_id=note_id
            ).first()
            return existing is not None
        finally:
            session.close()

    def get_notes_for_student(self, student_id: int) -> list:
        """Получает список конспектов, назначенных ученику"""
        session = self.Session()
        try:
            student_notes = session.query(StudentNote).filter_by(student_id=student_id).all()
            notes = []
            for sn in student_notes:
                note = session.query(Note).filter_by(id=sn.note_id).first()
                if note:
                    notes.append(note)
            # Сортируем конспекты по номеру
            return sorted(notes, key=lambda note: note.get_task_number())
        finally:
            session.close()

    def get_students_with_matching_homework(self, note: Note) -> list:
        """Получает список учеников с домашними заданиями, подходящими к конспекту"""
        session = self.Session()
        try:
            # Получаем всех учеников того же типа экзамена
            students = session.query(Student).filter_by(exam_type=note.exam_type).all()
            matching_students = []
            
            for student in students:
                # Получаем домашние задания ученика
                student_homeworks = session.query(StudentHomework).filter_by(student_id=student.id).all()
                
                for sh in student_homeworks:
                    homework = session.query(Homework).filter_by(id=sh.homework_id).first()
                    if homework and self._is_homework_note_match(homework, note):
                        matching_students.append(student)
                        break  # Если нашли подходящее задание, переходим к следующему ученику
            
            return matching_students
        finally:
            session.close()

    def get_unassigned_notes_for_students(self) -> list:
        """Получает список конспектов, которые можно выдать ученикам"""
        session = self.Session()
        try:
            unassigned = []
            all_notes = session.query(Note).all()
            
            for note in all_notes:
                # Ищем учеников с соответствующими заданиями
                matching_students = self.get_students_with_matching_homework(note)
                
                # Фильтруем тех, кому конспект еще не выдан
                unassigned_students = []
                for student in matching_students:
                    if not self.is_note_assigned_to_student(student.id, note.id):
                        unassigned_students.append(student)
                
                if unassigned_students:
                    unassigned.append((note, len(unassigned_students)))
            
            return unassigned
        finally:
            session.close()

    def _is_homework_note_match(self, homework: Homework, note: Note) -> bool:
        """Проверяет, подходит ли конспект к домашнему заданию"""
        # Извлекаем номера из названий
        hw_number = homework.get_task_number()
        note_number = note.get_task_number()
        
        # Если номера совпадают, это точное совпадение
        if hw_number == note_number and hw_number != float('inf'):
            return True
        
        # Если номера не совпадают, проверяем по ключевым словам
        hw_keywords = self._extract_keywords(homework.title)
        note_keywords = self._extract_keywords(note.title)
        
        similarity = self._calculate_similarity(hw_keywords, note_keywords)
        return similarity > 0.7  # Порог схожести 70%

    def _extract_keywords(self, title: str) -> list:
        """Извлекает ключевые слова из названия"""
        # Убираем стоп-слова и приводим к нижнему регистру
        stop_words = {'задача', 'задание', 'конспект', 'по', 'в', 'на', 'для', 'и', 'или', 'с', 'от', 'до'}
        words = title.lower().split()
        return [w for w in words if w not in stop_words and len(w) > 2]

    def _calculate_similarity(self, keywords1: list, keywords2: list) -> float:
        """Вычисляет схожесть по ключевым словам"""
        if not keywords1 or not keywords2:
            return 0.0
        
        common = set(keywords1) & set(keywords2)
        total = set(keywords1) | set(keywords2)
        return len(common) / len(total) if total else 0.0 

    def add_pending_note_assignment_with_process(self, process_id: str, user_id: int, student_id: int = None, note_id: int = None, step: str = None, origin: str = None):
        session = self.Session()
        try:
            assignment = PendingNoteAssignment(process_id=process_id, user_id=user_id, student_id=student_id, note_id=note_id, step=step, origin=origin)
            session.add(assignment)
            session.commit()
        finally:
            session.close()

    def get_pending_note_assignment_by_process(self, process_id: str) -> PendingNoteAssignment:
        session = self.Session()
        try:
            return session.query(PendingNoteAssignment).filter_by(process_id=process_id).first()
        finally:
            session.close()

    def update_pending_note_assignment(self, process_id: str, **kwargs):
        session = self.Session()
        try:
            assignment = session.query(PendingNoteAssignment).filter_by(process_id=process_id).first()
            if assignment:
                for k, v in kwargs.items():
                    setattr(assignment, k, v)
                session.commit()
        finally:
            session.close()

    def delete_pending_note_assignment_by_process(self, process_id: str):
        session = self.Session()
        try:
            session.query(PendingNoteAssignment).filter_by(process_id=process_id).delete()
            session.commit()
        finally:
            session.close()

    def clear_old_pending_note_assignments(self, minutes: int = 10):
        session = self.Session()
        try:
            threshold = datetime.now() - timedelta(minutes=minutes)
            session.query(PendingNoteAssignment).filter(PendingNoteAssignment.created_at < threshold).delete()
            session.commit()
        finally:
            session.close() 