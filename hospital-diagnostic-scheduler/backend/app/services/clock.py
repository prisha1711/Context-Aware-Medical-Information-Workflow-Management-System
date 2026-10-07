"""Demo clock. Real deployments would use wall-clock time; the demo needs to fast-forward a day.
Single-process state - fine for the demo, use a DB row or Redis key if you run several workers."""
from datetime import date

from ..core.timeutil import DAY_START

STATE = {"day": date.today(), "now": DAY_START, "script": [], "seed": 7}


def get_now() -> int:
    return STATE["now"]


def get_day() -> date:
    return STATE["day"]
