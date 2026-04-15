from datetime import datetime, timedelta
import pytz

MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def get_moscow_now():
    """Получение текущего времени по МСК"""
    return datetime.now(MOSCOW_TZ)


def format_datetime_moscow(dt: datetime) -> str:
    """Форматирование даты в МСК"""
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    moscow_dt = dt.astimezone(MOSCOW_TZ)
    return moscow_dt.strftime("%Y-%m-%d %H:%M:%S")


def get_end_date(days: int) -> datetime:
    """Получение даты окончания подписки"""
    return datetime.utcnow() + timedelta(days=days)