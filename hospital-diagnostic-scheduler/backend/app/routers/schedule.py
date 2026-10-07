from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.recovery import find_gaps
from ..core.timeutil import HORIZON, LEAD, REG_END_SLOT, to_min, to_slot
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Appointment, OptimizationRun
from ..services import clock
from ..services.audit import audit
from ..services.kpis import compute_kpis
from ..services.scheduling import ACTIVE, build_problem, recover_if_possible, run_optimization
from ..services.serialize import appointment_dicts, waitlist_dicts

router = APIRouter(tags=["schedule"], dependencies=[Depends(get_current_user)])


@router.get("/schedule")
def schedule(db: Session = Depends(get_db)):
    day = clock.get_day()
    return {"day": str(day), "now": clock.get_now(), "appointments": appointment_dicts(db, day)}


@router.get("/waitlist")
def waitlist(db: Session = Depends(get_db)):
    return waitlist_dicts(db, clock.get_day())


@router.get("/capacity")
def capacity(db: Session = Depends(get_db)):
    day, now = clock.get_day(), clock.get_now()
    appts = db.query(Appointment).filter(Appointment.day == day, Appointment.status.in_(ACTIVE)).all()
    p = build_problem(db, day, now, [], appts)
    names = {m.id: m.name for m in p.machines}
    return [dict(resource=names[r], start_min=to_min(a), end_min=to_min(b), minutes=(b - a) * 5)
            for r, a, b in find_gaps(p, to_slot(now + LEAD), REG_END_SLOT, min_len=4)]


@router.get("/kpis")
def kpis(db: Session = Depends(get_db)):
    return compute_kpis(db, clock.get_day())


@router.post("/schedule/optimize")
def optimize(db: Session = Depends(get_db), user=Depends(require_roles("scheduler", "admin"))):
    """Manual full re-optimization of everything that has not started yet."""
    day, now = clock.get_day(), clock.get_now()
    run = run_optimization(db, day, "reopt", now, trigger="manual")
    recover_if_possible(db, day, now, trigger="manual")
    audit(db, user, "manual_optimize", "optimization_run", run.id)
    db.commit()
    return {"run_id": run.id, "backend": run.backend, "status": run.status, "moved": run.n_moved, "solve_ms": run.solve_ms}


@router.get("/runs")
def runs(limit: int = 30, db: Session = Depends(get_db)):
    q = db.query(OptimizationRun).filter(OptimizationRun.day == clock.get_day()).order_by(OptimizationRun.id.desc()).limit(limit)
    return [dict(id=r.id, mode=r.mode, trigger=r.trigger, backend=r.backend, status=r.status, solve_ms=r.solve_ms, scheduled=r.n_scheduled,
                 unscheduled=r.n_unscheduled, moved=r.n_moved, recovered=r.n_recovered, stages=r.stages, created_at=r.created_at) for r in q]


@router.get("/appointments/{appt_id}/explain")
def explain(appt_id: int, db: Session = Depends(get_db)):
    a = db.get(Appointment, appt_id)
    if not a:
        raise HTTPException(404, "Appointment not found")
    run = db.get(OptimizationRun, a.last_run_id) if a.last_run_id else None
    ex = (run.explain or {}).get(str(a.order_id)) if run else None
    return {"appointment_id": a.id, "run_id": a.last_run_id, "mode": run.mode if run else None, "trigger": run.trigger if run else None,
            "explanation": ex or {"summary": "No optimization record for this appointment.", "details": []}}
