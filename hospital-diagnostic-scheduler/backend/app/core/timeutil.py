"""Time grid. The solver works in 5-minute slots counted from DAY_START; the DB stores minutes after midnight."""
import math

SLOT = 5            # minutes per solver slot
DAY_START = 8 * 60  # 08:00
DAY_END = 17 * 60   # 17:00 regular close
OVERTIME_MAX = 30   # minutes of overtime the solver may use (penalised)
TURN = 5            # turnover/cleaning minutes added after every case
LEAD = 30           # minimum notice (min) before a recovered slot can start
FREEZE = 15         # appointments starting within this many minutes are frozen during re-optimization
REG_END_SLOT = (DAY_END - DAY_START) // SLOT
HORIZON = (DAY_END + OVERTIME_MAX - DAY_START) // SLOT


def to_slot(minute: float, up: bool = True) -> int:
    """Minutes after midnight -> slot index (clamped at 0)."""
    s = (minute - DAY_START) / SLOT
    return max(0, math.ceil(s - 1e-9) if up else math.floor(s + 1e-9))


def to_min(slot: int) -> int:
    return DAY_START + slot * SLOT


def dur_slots(minutes: float) -> int:
    """Planned minutes (+ turnover) -> whole slots."""
    return max(1, math.ceil((minutes + TURN) / SLOT - 1e-9))


def fmt(minute: float) -> str:
    return f"{int(minute) // 60:02d}:{int(minute) % 60:02d}"
