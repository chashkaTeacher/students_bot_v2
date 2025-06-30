import requests
from datetime import datetime, timedelta, date
from icalendar import Calendar
import pytz
from typing import List, Dict, Optional
from dateutil.rrule import rrulestr

class ICalCalendarSync:
    def __init__(self, ical_url: str):
        self.ical_url = ical_url
        self.moscow_tz = pytz.timezone('Europe/Moscow')
        self._cached_events = None
        self._cache_time = None
        self._cache_duration = timedelta(minutes=5)  # Кэшируем на 5 минут
    
    def _fetch_calendar(self) -> Optional[Calendar]:
        """Загружает календарь из iCal URL"""
        try:
            response = requests.get(self.ical_url, timeout=10)
            response.raise_for_status()
            cal = Calendar.from_ical(response.content)
            return cal
        except Exception as e:
            return None
    
    def _get_events_for_date(self, date: datetime) -> List[Dict]:
        """Получает события для конкретной даты"""
        now = datetime.now()
        
        # Проверяем кэш
        if (self._cached_events is not None and 
            self._cache_time is not None and 
            now - self._cache_time < self._cache_duration):
            return self._filter_events_for_date(self._cached_events, date)
        
        # Загружаем календарь
        cal = self._fetch_calendar()
        if not cal:
            return []
        
        # Определяем диапазон дат для фильтрации (только будущие 30 дней)
        start_date = now
        end_date = now + timedelta(days=30)
        # Приводим к московскому времени, если нужно
        if start_date.tzinfo is None:
            start_date = self.moscow_tz.localize(start_date)
        else:
            start_date = start_date.astimezone(self.moscow_tz)
        if end_date.tzinfo is None:
            end_date = self.moscow_tz.localize(end_date)
        else:
            end_date = end_date.astimezone(self.moscow_tz)
        
        # Парсим события с фильтрацией по дате
        events = []
        event_count = 0
        filtered_count = 0
        
        for component in cal.walk():
            if component.name == "VEVENT":
                event_count += 1
                # Проверяем, есть ли RRULE (повторяемое событие)
                rrule_raw = component.get('rrule')
                if rrule_raw:
                    # Получаем время начала
                    start = component.get('dtstart')
                    end = component.get('dtend')
                    if not start or not end:
                        continue
                    start_dt = start.dt
                    end_dt = end.dt
                    # Приводим к московскому времени
                    if isinstance(start_dt, datetime):
                        if start_dt.tzinfo is None:
                            start_dt = self.moscow_tz.localize(start_dt)
                        else:
                            start_dt = start_dt.astimezone(self.moscow_tz)
                    if isinstance(end_dt, datetime):
                        if end_dt.tzinfo is None:
                            end_dt = self.moscow_tz.localize(end_dt)
                        else:
                            end_dt = end_dt.astimezone(self.moscow_tz)
                    # Разворачиваем RRULE
                    rrule_str = "RRULE:" + rrule_raw.to_ical().decode()
                    rule = rrulestr(rrule_str, dtstart=start_dt)
                    for occur in rule.between(start_date, end_date, inc=True):
                        # Для каждого повторения создаём отдельное событие
                        duration = end_dt - start_dt
                        occur_end = occur + duration
                        event = {
                            'start': occur,
                            'end': occur_end,
                            'summary': str(component.get('summary', 'Без названия')),
                            'description': str(component.get('description', '')),
                            'location': str(component.get('location', '')),
                            'is_all_day': False
                        }
                        # Фильтрация по диапазону дат
                        if start_date.date() <= occur.date() <= end_date.date():
                            events.append(event)
                            filtered_count += 1
                else:
                    event = self._parse_event(component)
                    if event:
                        # Проверяем, попадает ли событие в нужный диапазон дат
                        event_start = event['start']
                        if isinstance(event_start, datetime):
                            event_date = event_start.date()
                        else:
                            event_date = event_start
                        
                        if start_date.date() <= event_date <= end_date.date():
                            events.append(event)
                            filtered_count += 1
        
        # Обновляем кэш
        self._cached_events = events
        self._cache_time = now
        
        return self._filter_events_for_date(events, date)
    
    def _parse_event(self, component) -> Optional[Dict]:
        """Парсит событие из iCal компонента"""
        try:
            start = component.get('dtstart')
            if not start:
                return None
            end = component.get('dtend')
            if not end:
                return None

            start_dt = start.dt
            end_dt = end.dt
            # Корректное определение all-day
            is_all_day = False
            if isinstance(start_dt, date) and not isinstance(start_dt, datetime):
                is_all_day = True
                start_dt = datetime.combine(start_dt, datetime.min.time())
                end_dt = datetime.combine(end_dt, datetime.min.time())
            elif isinstance(start_dt, datetime) and isinstance(end_dt, datetime):
                # Приводим к московскому времени
                if start_dt.tzinfo is None:
                    start_dt = self.moscow_tz.localize(start_dt)
                else:
                    start_dt = start_dt.astimezone(self.moscow_tz)
                
                if end_dt.tzinfo is None:
                    end_dt = self.moscow_tz.localize(end_dt)
                else:
                    end_dt = end_dt.astimezone(self.moscow_tz)
                
                # Проверяем, не является ли это событием на весь день по времени
                if (start_dt.hour == 0 and start_dt.minute == 0 and 
                    end_dt.hour == 0 and end_dt.minute == 0):
                    is_all_day = True
                    # Используем время 09:00-10:00 по умолчанию
                    start_dt = start_dt.replace(hour=9, minute=0, second=0, microsecond=0)
                    end_dt = start_dt.replace(hour=10, minute=0, second=0, microsecond=0)
            return {
                'start': start_dt,
                'end': end_dt,
                'summary': str(component.get('summary', 'Без названия')),
                'description': str(component.get('description', '')),
                'location': str(component.get('location', '')),
                'is_all_day': is_all_day
            }
        except Exception as e:
            return None
    
    def _filter_events_for_date(self, events: List[Dict], target_date: datetime) -> List[Dict]:
        """Фильтрует события для конкретной даты с учетом временной зоны"""
        # Приводим target_date к московскому времени
        if isinstance(target_date, datetime):
            if target_date.tzinfo is None:
                target_date = self.moscow_tz.localize(target_date)
            else:
                target_date = target_date.astimezone(self.moscow_tz)
        else:
            target_date = datetime.combine(target_date, datetime.min.time())
            target_date = self.moscow_tz.localize(target_date)

        target_date_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        target_date_end = target_date_start + timedelta(days=1)

        filtered_events = []
        for event in events:
            event_start = event['start'].astimezone(self.moscow_tz)
            event_end = event['end'].astimezone(self.moscow_tz)

            # Проверяем пересечение с целевой датой
            if (event_start < target_date_end and event_end > target_date_start):
                filtered_events.append(event)

        return filtered_events
    
    def get_busy_times(self, date: datetime) -> List[Dict]:
        """Получает занятые временные слоты на указанную дату"""
        events = self._get_events_for_date(date)
        
        busy_times = []
        for event in events:
            # Приводим время к московскому часовому поясу
            start_moscow = event['start'].astimezone(self.moscow_tz)
            end_moscow = event['end'].astimezone(self.moscow_tz)
            
            # Для событий на весь день добавляем весь рабочий день как занятое время
            if event.get('is_all_day', False):
                busy_times.append({
                    'start': datetime.strptime("09:00", "%H:%M").time(),
                    'end': datetime.strptime("18:00", "%H:%M").time(),
                    'title': f"{event['summary']} (весь день)"
                })
            else:
                busy_times.append({
                    'start': start_moscow.time(),
                    'end': end_moscow.time(),
                    'title': event['summary']
                })
        
        return busy_times
    
    def is_time_busy(self, date: datetime, time: str, duration: int) -> bool:
        """Проверяет, занято ли указанное время"""
        busy_times = self.get_busy_times(date)
        
        if not busy_times:
            return False
        
        # Конвертируем время в datetime для сравнения
        time_obj = datetime.strptime(time, "%H:%M").time()
        end_time = (datetime.combine(date, time_obj) + timedelta(minutes=duration)).time()
        
        for busy in busy_times:
            # Проверяем пересечение
            if (time_obj < busy['end'] and end_time > busy['start']):
                return True
        
        return False
    
    def get_available_slots(self, date: datetime, start_time: str, end_time: str, 
                          slot_duration: int, slot_interval: int) -> List[Dict]:
        """Получает доступные слоты с учетом занятого времени в календаре"""
        busy_times = self.get_busy_times(date)
        
        # Конвертируем время в datetime
        start_dt = datetime.strptime(start_time, "%H:%M").time()
        end_dt = datetime.strptime(end_time, "%H:%M").time()
        
        # Генерируем все возможные слоты
        slots = []
        current_time = start_dt
        
        while current_time < end_dt:
            # Проверяем, помещается ли занятие в этот слот
            slot_end = (datetime.combine(date, current_time) + 
                       timedelta(minutes=slot_duration)).time()
            
            if slot_end <= end_dt:
                # Проверяем, не занято ли время
                is_busy = False
                for busy in busy_times:
                    if (current_time < busy['end'] and slot_end > busy['start']):
                        is_busy = True
                        break
                
                if not is_busy:
                    slots.append({
                        'time': current_time.strftime("%H:%M"),
                        'end_time': slot_end.strftime("%H:%M"),
                        'display': f"{current_time.strftime('%H:%M')}-{slot_end.strftime('%H:%M')}"
                    })
            
            # Переходим к следующему слоту
            current_time = (datetime.combine(date, current_time) + 
                          timedelta(minutes=slot_interval)).time()
        
        return slots
    
    def clear_cache(self):
        """Очищает кэш календаря"""
        self._cached_events = None
        self._cache_time = None

# Глобальный экземпляр для использования в других модулях
# URL вашего iCal календаря
ICAL_URL = "https://calendar.google.com/calendar/ical/c6a174e0d5559b6c25bec08b7871ce611a7c9215d99b63d39e611e4f54a8245b%40group.calendar.google.com/private-8a5f0c715b1237d70c9a84fe41426113/basic.ics"
ical_sync = ICalCalendarSync(ICAL_URL) 