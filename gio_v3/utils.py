import os
import math
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


def clean_str(value, max_len: int = 500) -> str:
    """Strip whitespace and truncate to max_len. Returns '' for None."""
    if value is None:
        return ''
    return str(value).strip()[:max_len]


def safe_float(value, default: float = 0.0, min_val=None, max_val: float = 10_000_000) -> float:
    """Convert to float, blocking NaN/Infinity and out-of-range values."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    if min_val is not None and f < min_val:
        return default
    if max_val is not None and f > max_val:
        return default
    return f
