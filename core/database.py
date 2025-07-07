from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timedelta
import enum
import random
import string
import re
import urllib.parse
import pytz
import threading

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
    menu_message_id = Column(Integer, nullable=True)

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
    avatar_emoji = Column(String, nullable=True)  # Эмодзи-аватарка
    theme = Column(String, nullable=True)  # Тема оформления

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
        # Ищем диапазон (например, '19-21')
        range_match = re.search(r'(\d+-\d+)', self.title)
        if range_match:
            return range_match.group(1)
        # Ищем отдельное число
        number_match = re.search(r'\d+', self.title)
        if number_match:
            return int(number_match.group(0))
        # Если нет чисел, возвращаем последнее слово или всё после 'Задание'
        text = self.title.strip()
        if 'Задание' in text:
            after = text.split('Задание', 1)[1].strip()
            if after:
                return after
        # Если нет слова 'Задание', возвращаем последнее слово
        return text.split()[-1] if text else text

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
        # Ищем диапазон (например, '19-21')
        range_match = re.search(r'(\d+-\d+)', self.title)
        if range_match:
            return range_match.group(1)
        # Ищем отдельное число
        number_match = re.search(r'\d+', self.title)
        if number_match:
            return int(number_match.group(0))
        # Если нет чисел, возвращаем последнее слово или всё после 'Задание'
        text = self.title.strip()
        if 'Задание' in text:
            after = text.split('Задание', 1)[1].strip()
            if after:
                return after
        # Если нет слова 'Задание', возвращаем последнее слово
        return text.split()[-1] if text else text

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
    student_id = Column(Integer, ForeignKey('students.id'), nullable=True)  # Может быть null для админских уведомлений
    admin_id = Column(Integer, ForeignKey('admins.id'), nullable=True)  # Может быть null для студенческих уведомлений
    type = Column(String, nullable=False)  # 'homework', 'variant', 'reschedule', etc.
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

class AdminPushMessage(Base):
    __tablename__ = 'admin_push_messages'
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, nullable=False)
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

class Schedule(Base):
    __tablename__ = 'schedule'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Понедельник, 1=Вторник, ..., 6=Воскресенье
    time = Column(String, nullable=False)  # Время в формате "HH:MM"
    duration = Column(Integer, default=60)  # Длительность в минутах
    is_active = Column(Boolean, default=True)  # Активно ли занятие
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Создаем уникальный индекс для предотвращения дублирования расписания
    __table_args__ = (
        UniqueConstraint('student_id', 'day_of_week', 'time', name='unique_student_schedule'),
    )

class RescheduleRequest(Base):
    __tablename__ = 'reschedule_requests'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    schedule_id = Column(Integer, ForeignKey('schedule.id'), nullable=False)
    original_date = Column(DateTime, nullable=False)  # Текущая дата занятия
    original_time = Column(String, nullable=False)    # Текущее время занятия
    requested_date = Column(DateTime, nullable=False) # Желаемая дата
    requested_time = Column(String, nullable=False)   # Желаемое время
    status = Column(String, default='pending')        # pending, processed
    created_at = Column(DateTime, default=func.now())

class RescheduleSettings(Base):
    __tablename__ = 'reschedule_settings'
    id = Column(Integer, primary_key=True)
    work_start_time = Column(String, default="10:00")
    work_end_time = Column(String, default="19:00")
    available_days = Column(String, default="0,1,2,3,4,5,6")  # 0=пн, 6=вс
    max_weeks_ahead = Column(Integer, default=2)
    slot_interval = Column(Integer, default=15)  # интервал слотов в минутах

class ScheduledReminder(Base):
    __tablename__ = 'scheduled_reminders'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    schedule_id = Column(Integer, ForeignKey('schedule.id'), nullable=False)
    reminder_time = Column(DateTime, nullable=False)  # Время, когда должно сработать напоминание
    lesson_time = Column(DateTime, nullable=False)    # Время самого занятия
    is_sent = Column(Boolean, default=False)          # Отправлено ли уже напоминание
    created_at = Column(DateTime, default=func.now())
    
    # Создаем уникальный индекс для предотвращения дублирования
    __table_args__ = (
        UniqueConstraint('student_id', 'schedule_id', 'reminder_time', name='unique_reminder'),
    )

class Database:
    _slots_cache = {}
    _slots_cache_lock = threading.Lock()
    _slots_cache_ttl = 600  # 10 минут в секундах

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
                student.avatar_emoji = None
                student.theme = None
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
        """Получает домашние задания для студента с учетом настройки показа старых заданий
        Исключает "виртуальные" задания (без ссылки и файла) и задания со статусом "не пройдено" (по последнему назначению) из списка."""
        session = self.Session()
        try:
            not_passed_statuses = {'not_passed', 'not completed', 'notcompleted', 'Не пройдено', 'not passed'}
            # Получаем все назначения для студента
            assigned = session.query(StudentHomework).filter_by(student_id=student_id).all()
            if not assigned:
                return []
            # Если show_old не указан, берем из настроек студента
            if show_old is None:
                student = session.query(Student).filter_by(id=student_id).first()
                show_old = student.show_old_homework if student else False
            # Для каждого homework_id берём только последнюю запись (по assigned_at)
            last_assignments = {}
            for sh in assigned:
                if sh.homework_id not in last_assignments or sh.assigned_at > last_assignments[sh.homework_id].assigned_at:
                    last_assignments[sh.homework_id] = sh
            # Получаем информацию о заданиях
            homeworks = []
            for sh in last_assignments.values():
                homework = session.query(Homework).filter_by(id=sh.homework_id).first()
                if homework:
                    # Фильтруем "виртуальные" задания: нет ссылки и нет файла
                    if (not homework.link or homework.link.strip() == "") and (not homework.file_path or homework.file_path.strip() == ""):
                        continue
                    # Фильтруем задания со статусом "не пройдено" (по последнему назначению)
                    if sh.status and sh.status.strip().lower() in {s.lower() for s in not_passed_statuses}:
                        continue
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
                # Если задание уже назначено, обновляем дату назначения и сбрасываем статус
                existing.assigned_at = datetime.now()
                existing.status = 'assigned'  # Сбрасываем статус на "выдано"
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

    def update_homework_status(self, student_id: int, homework_id: int, status: str) -> bool:
        """Обновляет статус домашнего задания для студента. Если записи нет — создаёт новую."""
        session = self.Session()
        try:
            student_homework = session.query(StudentHomework).filter_by(
                student_id=student_id, 
                homework_id=homework_id
            ).first()
            if student_homework:
                student_homework.status = status
                session.commit()
                return True
            else:
                # Если записи нет — создаём новую
                new_sh = StudentHomework(student_id=student_id, homework_id=homework_id, status=status)
                session.add(new_sh)
                session.commit()
                return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def get_homework_status_for_student(self, student_id: int, exam_type: ExamType) -> dict:
        """Получает статусы заданий ученика по номеру задания"""
        session = self.Session()
        try:
            # Получаем все назначенные задания ученика данного типа экзамена
            student_homeworks = session.query(StudentHomework).join(Homework).filter(
                StudentHomework.student_id == student_id,
                Homework.exam_type == exam_type
            ).all()
            
            statuses = {}
            for sh in student_homeworks:
                homework = session.query(Homework).filter_by(id=sh.homework_id).first()
                if homework:
                    task_number = homework.get_task_number()
                    if task_number != float('inf'):  # Исключаем задания без номера
                        statuses[task_number] = sh.status
            
            return statuses
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

    def add_admin_notification(self, admin_id: int, notif_type: str, text: str, link: str = None):
        session = self.Session()
        try:
            notif = Notification(admin_id=admin_id, type=notif_type, text=text, link=link)
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

    def get_admin_notifications(self, admin_id: int, only_unread: bool = False):
        session = self.Session()
        try:
            q = session.query(Notification).filter_by(admin_id=admin_id)
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

    def mark_admin_notifications_read(self, admin_id: int):
        session = self.Session()
        try:
            session.query(Notification).filter_by(admin_id=admin_id, is_read=False).update({Notification.is_read: True})
            session.commit()
        finally:
            session.close()

    def has_unread_notifications(self, student_id: int) -> bool:
        session = self.Session()
        try:
            return session.query(Notification).filter_by(student_id=student_id, is_read=False).count() > 0
        finally:
            session.close()

    def has_unread_admin_notifications(self, admin_id: int) -> bool:
        session = self.Session()
        try:
            return session.query(Notification).filter_by(admin_id=admin_id, is_read=False).count() > 0
        finally:
            session.close()

    def clear_notifications(self, student_id: int):
        session = self.Session()
        try:
            session.query(Notification).filter_by(student_id=student_id).delete()
            session.commit()
        finally:
            session.close()

    def clear_admin_notifications(self, admin_id: int):
        session = self.Session()
        try:
            session.query(Notification).filter_by(admin_id=admin_id).delete()
            session.commit()
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

    def add_admin_push_message(self, admin_id: int, message_id: int):
        """Добавляет push-сообщение администратора"""
        session = self.Session()
        try:
            push = AdminPushMessage(admin_id=admin_id, message_id=message_id)
            session.add(push)
            session.commit()
        finally:
            session.close()

    def get_admin_push_messages(self, admin_id: int):
        """Получает push-сообщения администратора"""
        session = self.Session()
        try:
            return session.query(AdminPushMessage).filter_by(admin_id=admin_id).all()
        finally:
            session.close()

    def clear_admin_push_messages(self, admin_id: int):
        """Очищает push-сообщения администратора"""
        session = self.Session()
        try:
            push_messages = session.query(AdminPushMessage).filter_by(admin_id=admin_id).all()
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

    # Методы для работы с расписанием
    def add_schedule(self, student_id: int, day_of_week: int, time: str, duration: int = 60) -> bool:
        """Добавляет занятие в расписание студента"""
        session = self.Session()
        try:
            # Проверяем, нет ли уже занятия в это время в этот день
            existing = session.query(Schedule).filter_by(
                student_id=student_id,
                day_of_week=day_of_week,
                time=time
            ).first()
            
            if existing:
                return False  # Занятие уже существует
            
            schedule = Schedule(
                student_id=student_id,
                day_of_week=day_of_week,
                time=time,
                duration=duration
            )
            session.add(schedule)
            session.commit()
            return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def get_student_schedule(self, student_id: int) -> list:
        """Получает расписание студента"""
        session = self.Session()
        try:
            return session.query(Schedule).filter_by(
                student_id=student_id,
                is_active=True
            ).order_by(Schedule.day_of_week, Schedule.time).all()
        finally:
            session.close()

    def update_schedule(self, schedule_id: int, day_of_week: int = None, time: str = None, duration: int = None, is_active: bool = None) -> bool:
        """Обновляет занятие в расписании"""
        session = self.Session()
        try:
            schedule = session.query(Schedule).filter_by(id=schedule_id).first()
            if not schedule:
                return False
            
            # Проверяем конфликты при изменении дня или времени
            if day_of_week is not None or time is not None:
                new_day = day_of_week if day_of_week is not None else schedule.day_of_week
                new_time = time if time is not None else schedule.time
                
                # Проверяем, нет ли уже занятия в это время в этот день (исключая текущее занятие)
                existing = session.query(Schedule).filter_by(
                    student_id=schedule.student_id,
                    day_of_week=new_day,
                    time=new_time
                ).filter(Schedule.id != schedule_id).first()
                
                if existing:
                    return False  # Конфликт с существующим занятием
            
            if day_of_week is not None:
                schedule.day_of_week = day_of_week
            if time is not None:
                schedule.time = time
            if duration is not None:
                schedule.duration = duration
            if is_active is not None:
                schedule.is_active = is_active
            
            schedule.updated_at = datetime.now()
            session.commit()
            return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def delete_schedule(self, schedule_id: int) -> bool:
        """Удаляет занятие из расписания"""
        session = self.Session()
        try:
            schedule = session.query(Schedule).filter_by(id=schedule_id).first()
            if schedule:
                session.delete(schedule)
                session.commit()
                return True
            return False
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def get_next_lesson(self, student_id: int) -> dict:
        """Получает информацию о следующем занятии студента"""
        session = self.Session()
        try:
            now = datetime.now()
            current_day = now.weekday()  # 0=Понедельник, 6=Воскресенье
            current_time = now.strftime("%H:%M")
            
            # Получаем все активные занятия студента
            schedules = session.query(Schedule).filter_by(
                student_id=student_id,
                is_active=True
            ).order_by(Schedule.day_of_week, Schedule.time).all()
            
            if not schedules:
                return None
            
            # Ищем следующее занятие
            for schedule in schedules:
                if schedule.day_of_week > current_day or (schedule.day_of_week == current_day and schedule.time > current_time):
                    # Вычисляем дату следующего занятия
                    days_ahead = schedule.day_of_week - current_day
                    if days_ahead < 0:
                        days_ahead += 7
                    next_lesson_date = now + timedelta(days=days_ahead)
                    
                    return {
                        'schedule': schedule,
                        'date': next_lesson_date,
                        'day_name': self._get_day_name(schedule.day_of_week),
                        'time': schedule.time,
                        'duration': schedule.duration
                    }
            
            # Если не нашли в этой неделе, берем первое занятие следующей недели
            first_schedule = schedules[0]
            days_ahead = (7 - current_day + first_schedule.day_of_week) % 7
            if days_ahead == 0:
                days_ahead = 7
            next_lesson_date = now + timedelta(days=days_ahead)
            
            return {
                'schedule': first_schedule,
                'date': next_lesson_date,
                'day_name': self._get_day_name(first_schedule.day_of_week),
                'time': first_schedule.time,
                'duration': first_schedule.duration
            }
        finally:
            session.close()

    def _get_day_name(self, day_of_week: int) -> str:
        """Возвращает название дня недели"""
        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        return days[day_of_week]

    # Методы для работы с переносами
    def add_reschedule_request(self, student_id: int, schedule_id: int, original_date: datetime, 
                              original_time: str, requested_date: datetime, requested_time: str) -> bool:
        """Добавляет запрос на перенос занятия"""
        session = self.Session()
        try:
            request = RescheduleRequest(
                student_id=student_id,
                schedule_id=schedule_id,
                original_date=original_date,
                original_time=original_time,
                requested_date=requested_date,
                requested_time=requested_time
            )
            session.add(request)
            session.commit()
            return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def create_reschedule_request(self, student_id: int, schedule_id: int, requested_date: datetime, 
                                 requested_time: str, status: str = 'pending') -> dict:
        """Создает запрос на перенос занятия и возвращает словарь с нужными полями"""
        session = self.Session()
        try:
            schedule = session.query(Schedule).filter_by(id=schedule_id).first()
            if not schedule:
                return None
            now = datetime.now()
            current_day = schedule.day_of_week
            current_date = now + timedelta(days=(current_day - now.weekday()) % 7)
            if current_date < now:
                current_date += timedelta(days=7)
            request = RescheduleRequest(
                student_id=student_id,
                schedule_id=schedule_id,
                original_date=current_date,
                original_time=schedule.time,
                requested_date=requested_date,
                requested_time=requested_time,
                status=status
            )
            session.add(request)
            session.commit()
            # Сохраняем нужные значения сразу
            return {
                'id': request.id,
                'student_id': request.student_id,
                'schedule_id': request.schedule_id,
                'original_date': request.original_date,
                'original_time': request.original_time,
                'requested_date': request.requested_date,
                'requested_time': request.requested_time,
                'status': request.status,
                'created_at': request.created_at
            }
        except Exception as e:
            session.rollback()
            print(f"Ошибка при создании запроса на перенос: {e}")
            return None
        finally:
            session.close()

    def get_reschedule_settings(self) -> RescheduleSettings:
        """Получает настройки переносов"""
        session = self.Session()
        try:
            settings = session.query(RescheduleSettings).first()
            if not settings:
                # Создаем настройки по умолчанию
                settings = RescheduleSettings()
                session.add(settings)
                session.commit()
            return settings
        finally:
            session.close()

    def update_reschedule_settings(self, **kwargs) -> bool:
        """Обновляет настройки переносов"""
        session = self.Session()
        try:
            settings = session.query(RescheduleSettings).first()
            if not settings:
                settings = RescheduleSettings()
                session.add(settings)
            
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            session.commit()
            return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def get_available_slots_for_day(self, date: datetime, lesson_duration: int) -> list:
        """Получает доступные слоты для занятия заданной длительности на конкретную дату с кэшированием"""
        session = self.Session()
        try:
            settings = self.get_reschedule_settings()
            day_of_week = date.weekday()
            available_days = [int(d) for d in settings.available_days.split(',')]
            if day_of_week not in available_days:
                return []

            # --- Кэширование ---
            # Ключ кэша: (student_id, date, duration)
            # Для совместимости с текущим кодом, определим student_id через расписание (если есть)
            student_id = None
            try:
                # Получаем расписание для этого дня
                schedule = session.query(Schedule).filter_by(day_of_week=day_of_week, is_active=True).first()
                if schedule:
                    student_id = schedule.student_id
            except Exception:
                pass
            cache_key = (student_id, date.date().isoformat(), lesson_duration)
            now_ts = datetime.now().timestamp()
            with self._slots_cache_lock:
                cache_entry = self._slots_cache.get(cache_key)
                if cache_entry:
                    slots, ts = cache_entry
                    if now_ts - ts < self._slots_cache_ttl:
                        return slots
            # --- Конец блока кэширования ---

            # ... существующий код получения слотов ...
            start_time = datetime.strptime(settings.work_start_time, "%H:%M").time()
            end_time = datetime.strptime(settings.work_end_time, "%H:%M").time()
            now = datetime.now()
            if date.date() == now.date():
                current_hour = now.hour
                current_minute = now.minute
                adjusted_hour = current_hour + 1
                if adjusted_hour >= 24:
                    return []
                start_time = max(start_time, datetime.strptime(f"{adjusted_hour:02d}:{current_minute:02d}", "%H:%M").time())
            try:
                from .ical_sync import ical_sync
                slots = ical_sync.get_available_slots(
                    date=date,
                    start_time=start_time.strftime("%H:%M"),
                    end_time=end_time.strftime("%H:%M"),
                    slot_duration=lesson_duration,
                    slot_interval=settings.slot_interval
                )
                filtered_slots = []
                for slot in slots:
                    if self.is_slot_available(date, slot['time'], lesson_duration):
                        filtered_slots.append(slot)
                slots = filtered_slots
            except ImportError:
                slots = []
            except Exception as e:
                slots = []
            if not slots:
                # Старая логика (если iCal недоступен)
                slots = []
                current_time = start_time
                while current_time < end_time:
                    slot_end = datetime.combine(date, current_time) + timedelta(minutes=lesson_duration)
                    slot_end_time = slot_end.time()
                    if slot_end_time <= end_time:
                        if self.is_slot_available(date, current_time.strftime("%H:%M"), lesson_duration):
                            slots.append({
                                'time': current_time.strftime('%H:%M'),
                                'end_time': slot_end_time.strftime('%H:%M'),
                                'display': f"{current_time.strftime('%H:%M')}-{slot_end_time.strftime('%H:%M')}"
                            })
                    current_time = (datetime.combine(date, current_time) + timedelta(minutes=settings.slot_interval)).time()
            # --- Сохраняем в кэш ---
            with self._slots_cache_lock:
                self._slots_cache[cache_key] = (slots, now_ts)
            return slots
        finally:
            session.close()

    def is_slot_available(self, date: datetime, time: str, duration: int) -> bool:
        """Проверяет, доступен ли слот для занятия заданной длительности"""
        session = self.Session()
        try:
            day_of_week = date.weekday()
            
            # Получаем все занятия в этот день недели
            schedules = session.query(Schedule).filter_by(
                day_of_week=day_of_week,
                is_active=True
            ).all()
            
            # Проверяем пересечения с существующими занятиями
            requested_start = datetime.strptime(time, "%H:%M")
            requested_end = requested_start + timedelta(minutes=duration)
            
            for schedule in schedules:
                schedule_start = datetime.strptime(schedule.time, "%H:%M")
                schedule_end = schedule_start + timedelta(minutes=schedule.duration)
                
                # Проверяем пересечение
                if (requested_start < schedule_end and requested_end > schedule_start):
                    return False  # Есть пересечение
            
            # Проверяем iCal календарь (если доступен)
            try:
                from .ical_sync import ical_sync
                if ical_sync.is_time_busy(date, time, duration):
                    return False  # Время занято в календаре
            except ImportError:
                # Если модуль iCal недоступен, пропускаем проверку
                pass
            
            return True  # Нет пересечений
        finally:
            session.close()

    def get_available_days_for_week(self, week_start: datetime, lesson_duration: int) -> list:
        """Получает доступные дни для недели с учетом длительности занятия"""
        settings = self.get_reschedule_settings()
        available_days = [int(d) for d in settings.available_days.split(',')]
        now = datetime.now()
        days = []
        for i in range(7):
            if i in available_days:
                date = week_start + timedelta(days=i)
                # Проверяем, что дата не в прошлом
                if date.date() > now.date():
                    # Будущие дни недели — всегда доступны
                    slots = self.get_available_slots_for_day(date, lesson_duration)
                    if slots:
                        days.append({
                            'date': date,
                            'day_name': self._get_day_name(i),
                            'slots_count': len(slots)
                        })
                elif date.date() == now.date():
                    # Сегодня — только если есть хотя бы один слот с временем позже текущего
                    slots = self.get_available_slots_for_day(date, lesson_duration)
                    future_slots = [slot for slot in slots if datetime.strptime(slot['time'], "%H:%M").time() > now.time()]
                    if future_slots:
                        days.append({
                            'date': date,
                            'day_name': self._get_day_name(i),
                            'slots_count': len(future_slots)
                        })
        return days

    def get_schedule_by_id(self, schedule_id: int) -> Schedule:
        """Получает занятие по ID"""
        session = self.Session()
        try:
            return session.query(Schedule).filter_by(id=schedule_id).first()
        finally:
            session.close()

    def get_admin_telegram_id(self) -> int:
        """Получает telegram_id администратора для отправки уведомлений"""
        session = self.Session()
        try:
            admin = session.query(Admin).first()
            return admin.telegram_id if admin else None
        finally:
            session.close()

    def get_admin_ids(self) -> list:
        """Получает список всех telegram_id администраторов"""
        session = self.Session()
        try:
            admins = session.query(Admin).all()
            return [admin.telegram_id for admin in admins]
        finally:
            session.close()

    def get_admin_by_telegram_id(self, telegram_id: int):
        session = self.Session()
        try:
            return session.query(Admin).filter_by(telegram_id=telegram_id).first()
        finally:
            session.close()

    def get_admin_menu_message_id(self, admin_id: int):
        session = self.Session()
        try:
            admin = session.query(Admin).filter_by(id=admin_id).first()
            return admin.menu_message_id if admin else None
        finally:
            session.close()

    def update_admin_menu_message_id(self, admin_id: int, message_id: int):
        session = self.Session()
        try:
            admin = session.query(Admin).filter_by(id=admin_id).first()
            if admin:
                admin.menu_message_id = message_id
                session.commit()
        finally:
            session.close()

    def set_student_avatar(self, student_id: int, avatar_emoji: str):
        """Устанавливает эмодзи-аватарку студенту"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                student.avatar_emoji = avatar_emoji
                session.commit()
        finally:
            session.close()

    def set_student_theme(self, student_id: int, theme: str):
        """Устанавливает тему оформления студенту"""
        session = self.Session()
        try:
            student = session.query(Student).filter_by(id=student_id).first()
            if student:
                student.theme = theme
                session.commit()
        finally:
            session.close()

    def add_scheduled_reminder(self, student_id: int, schedule_id: int, reminder_time: datetime, lesson_time: datetime) -> bool:
        """Добавляет запланированное напоминание в базу данных"""
        session = self.Session()
        try:
            reminder = ScheduledReminder(
                student_id=student_id,
                schedule_id=schedule_id,
                reminder_time=reminder_time,
                lesson_time=lesson_time,
                is_sent=False
            )
            session.add(reminder)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f'[reminder] Ошибка при добавлении напоминания в БД: {e}')
            return False
        finally:
            session.close()

    def get_pending_reminders(self, current_time: datetime = None) -> list:
        from pytz import timezone
        moscow_tz = timezone('Europe/Moscow')
        if current_time is None:
            current_time = datetime.now(moscow_tz)
        elif current_time.tzinfo is None:
            current_time = moscow_tz.localize(current_time)
        session = self.Session()
        try:
            reminders = session.query(ScheduledReminder).filter(
                ScheduledReminder.reminder_time <= current_time,
                ScheduledReminder.is_sent == False
            ).all()
            return reminders
        finally:
            session.close()

    def mark_reminder_sent(self, reminder_id: int) -> bool:
        """Отмечает напоминание как отправленное"""
        session = self.Session()
        try:
            reminder = session.query(ScheduledReminder).filter_by(id=reminder_id).first()
            if reminder:
                reminder.is_sent = True
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f'[reminder] Ошибка при отметке напоминания как отправленного: {e}')
            return False
        finally:
            session.close()

    def clear_old_reminders(self, days: int = 7) -> int:
        """Удаляет старые напоминания (отправленные или просроченные)"""
        cutoff_date = datetime.now() - timedelta(days=days)
        session = self.Session()
        try:
            deleted_count = session.query(ScheduledReminder).filter(
                (ScheduledReminder.is_sent == True) | 
                (ScheduledReminder.reminder_time < cutoff_date)
            ).delete()
            session.commit()
            return deleted_count
        except Exception as e:
            session.rollback()
            print(f'[reminder] Ошибка при удалении старых напоминаний: {e}')
            return 0
        finally:
            session.close()

    def get_student_reminders(self, student_id: int) -> list:
        """Получает все напоминания для конкретного студента"""
        session = self.Session()
        try:
            reminders = session.query(ScheduledReminder).filter_by(student_id=student_id).all()
            return reminders
        finally:
            session.close()

    def delete_student_reminders(self, student_id: int) -> int:
        """Удаляет все напоминания для конкретного студента"""
        session = self.Session()
        try:
            deleted_count = session.query(ScheduledReminder).filter_by(student_id=student_id).delete()
            session.commit()
            return deleted_count
        except Exception as e:
            session.rollback()
            print(f'[reminder] Ошибка при удалении напоминаний студента: {e}')
            return 0
        finally:
            session.close() 