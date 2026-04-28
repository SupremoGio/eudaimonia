import os
from datetime import datetime
from zoneinfo import ZoneInfo

_APP_TZ = ZoneInfo(os.environ.get("TZ_APP", "America/Mexico_City"))


def now_local() -> datetime:
    """Current datetime in the app timezone (Mexico City by default)."""
    return datetime.now(_APP_TZ)


def today_str() -> str:
    """Today's date in app timezone as ISO string (YYYY-MM-DD)."""
    return now_local().date().isoformat()


def today_date():
    """Today's date object in app timezone."""
    return now_local().date()
