from datetime import date

from sqlalchemy.orm import Session

from ..core.timeutil import DAY_END, DAY_START
from ..models import Appointment, OperationalEvent, OptimizationRun, TestOrder


def compute_kpis(db: Session, day: date) -> dict:
    appts = db.query(Appointment).filter(Appointment.day == day).all()
    done = [a for a in appts if a.status == "completed"]
    reg = [a for a in done if not a.recovered and a.source != "stat" and a.actual_start_min is not None]
    delays = [max(0, a.actual_start_min - a.first_start_min) for a in reg]
    stat = [a for a in done if a.source == "stat" and a.actual_start_min is not None]
    ot = 0
    for rid in {a.resource_id for a in done}:
        ot += max(0, max([DAY_END] + [a.actual_end_min for a in done if a.resource_id == rid and a.actual_end_min]) - DAY_END)
    used = sum((a.actual_end_min - a.actual_start_min) for a in done if a.actual_end_min is not None)
    n_res = max(1, len({a.resource_id for a in appts}))
    events = db.query(OperationalEvent).filter(OperationalEvent.day == day).all()
    freed = sum(1 for e in events if e.type in ("cancellation", "no_show", "early_completion"))
    recovered = sum(1 for a in appts if a.recovered)
    runs = db.query(OptimizationRun).filter(OptimizationRun.day == day).all()
    return dict(
        served=len(done), scheduled=sum(a.status in ("scheduled", "in_progress") for a in appts),
        waitlisted=db.query(TestOrder).filter(TestOrder.day == day, TestOrder.status == "waitlisted").count(),
        avg_delay_min=round(sum(delays) / len(delays), 1) if delays else 0.0, max_delay_min=max(delays + [0]),
        stat_wait_min=round(sum(a.actual_start_min - a.first_start_min for a in stat) / len(stat), 1) if stat else 0.0,
        overtime_min=ot, utilization_pct=round(100 * used / (n_res * (DAY_END - DAY_START)), 1),
        slots_freed=freed, slots_recovered=recovered, fill_rate_pct=round(100 * min(1, recovered / freed), 1) if freed else 0.0,
        plan_moves=sum(a.moves for a in appts), optimization_runs=len(runs),
        avg_solve_ms=int(sum(r.solve_ms for r in runs) / len(runs)) if runs else 0,
        max_displaced=max([o.displaced_count for o in db.query(TestOrder).filter(TestOrder.day == day)] + [0]))
