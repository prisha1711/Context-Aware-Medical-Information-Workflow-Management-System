"""Orchestration between the database and the pure scheduling core (app.core).

Modes
  initial  everything is free (start of day / full re-plan)
  insert   a new ROUTINE order: all existing bookings stay put, only the newcomer is placed
  reopt    STAT/urgent arrival, machine/staff loss, large delay: unstarted work re-optimized, running + frozen work fixed
  recover  waitlisted orders try to use freed capacity; every existing booking is fixed
"""
from datetime import date

from sqlalchemy.orm import Session

from ..config import settings
from ..core.explain import explain_job
from ..core.solve import solve
from ..core.timeutil import FREEZE, HORIZON, LEAD, REG_END_SLOT, SLOT, dur_slots, to_min, to_slot
from ..core.types import Fixed, Job, Machine, Problem, Tech, Weights
from ..ml.predict import FALLBACK_MEAN, FALLBACK_P80_MULT, get_predictor
from ..models import (Appointment, OperationalEvent, OptimizationRun, Prediction, Resource, StaffAvailability, Technician,
                      TestOrder, WaitlistEntry)
from .ws import hub

ACTIVE = ("scheduled", "in_progress")
REOPT_DELAY_THRESHOLD = 10     # minutes: smaller overruns are absorbed (re-optimizing too often thrashes the schedule)


# ---------------------------------------------------------------- features / predictions
def order_features(db: Session, o: TestOrder, now_min: int, day: date) -> dict:
    p, t = o.patient, o.test
    return dict(test_code=t.code, modality=t.modality, contrast=int(o.contrast), sedation=int(o.sedation), inpatient=int(o.inpatient),
                age=p.age, hour=min(16, max(8, now_min // 60)), dow=day.weekday() % 5, tech_exp=6, lead_days=o.lead_days,
                prior_no_shows=p.prior_no_shows, sms_confirmed=int(o.sms_confirmed), distance_km=p.distance_km)


def predict_orders(db: Session, orders: list, now_min: int, day: date):
    pr = get_predictor()
    rows = [order_features(db, o, now_min, day) for o in orders]
    dur, ns = pr.predict_duration(rows), pr.predict_no_show(rows)
    v = pr.status
    for o, (mean, p80), p in zip(orders, dur, ns):
        db.add(Prediction(order_id=o.id, kind="duration", value=mean, p80=p80, model_version=str(v["duration_model"])))
        db.add(Prediction(order_id=o.id, kind="no_show", value=p, model_version=str(v["no_show_model"])))
    db.flush()


def _latest_predictions(db: Session, order_ids: list) -> dict:
    out = {}
    if not order_ids:
        return out
    for p in db.query(Prediction).filter(Prediction.order_id.in_(order_ids)).order_by(Prediction.id):
        out.setdefault(p.order_id, {})[p.kind] = p
    return out


# ---------------------------------------------------------------- problem building
def build_problem(db: Session, day: date, now: int, free_orders: list, fixed_appts: list, recover: bool = False) -> Problem:
    preds = _latest_predictions(db, [o.id for o in free_orders])
    active = {a.order_id: a for a in db.query(Appointment).filter(Appointment.day == day, Appointment.status == "scheduled")}
    jobs, now_slot = [], to_slot(now)
    for o in free_orders:
        pd_ = preds.get(o.id, {})
        dp = pd_.get("duration")
        planned = dp.p80 if dp else FALLBACK_MEAN[o.test.modality] * FALLBACK_P80_MULT
        ns = pd_["no_show"].value if "no_show" in pd_ else 0.1
        earliest = max(now_slot, to_slot(o.window_start_min), to_slot(o.prereq_ready_min or 0))
        latest = min(HORIZON, to_slot(o.window_end_min, up=False))
        if recover:
            earliest, latest = max(earliest, to_slot(now + LEAD)), min(latest, REG_END_SLOT)
        a = active.get(o.id)
        jobs.append(Job(id=o.id, modality=o.test.modality, priority=o.priority, duration=dur_slots(planned), earliest=earliest,
                        latest_end=latest, wait_days=o.wait_days, displaced=o.displaced_count, no_show_prob=ns,
                        prev_start=to_slot(a.start_min, up=False) if a else None, prev_resource=a.resource_id if a else None))
    machines = [Machine(r.id, r.modality, r.name, [(to_slot(s, up=False), to_slot(e)) for s, e in (r.unavailable or [])])
                for r in db.query(Resource).order_by(Resource.id)]
    avail = {}
    for s in db.query(StaffAvailability).filter(StaffAvailability.day == day):
        avail[s.technician_id] = (to_slot(s.start_min), to_slot(s.end_min, up=False))
    techs = [Tech(t.id, set(t.certifications), avail.get(t.id, (0, HORIZON)), t.name) for t in db.query(Technician).order_by(Technician.id)]
    fixed = []
    for a in fixed_appts:
        s = to_slot(a.start_min, up=False)
        e = s + max(1, (a.planned_end_min - a.start_min) // SLOT)
        if a.status == "in_progress":
            e = max(e, now_slot + 1)
        fixed.append(Fixed(a.resource_id, a.technician_id, s, e, a.order_id))
    return Problem(jobs, machines, techs, fixed, Weights(), time_limit=settings.solver_time_limit, workers=settings.solver_workers, reg_end=REG_END_SLOT)


# ---------------------------------------------------------------- applying a result
def _waitlist(db: Session, o: TestOrder, day: date):
    w = db.query(WaitlistEntry).filter(WaitlistEntry.order_id == o.id).first()
    if w is None:
        db.add(WaitlistEntry(order_id=o.id, day=day, windows=[[o.window_start_min, o.window_end_min]]))
    else:
        w.status = "waiting"


def apply_result(db: Session, day: date, mode: str, res, problem: Problem, orders: list, run: OptimizationRun, source: str) -> dict:
    names = {m.id: m.name for m in problem.machines}
    moved = recovered = 0
    for o in orders:
        a = res.assignments.get(o.id)
        appt = db.query(Appointment).filter(Appointment.order_id == o.id, Appointment.status == "scheduled").first()
        if a:
            start, end = to_min(a.start), to_min(a.end)
            planned = (a.end - a.start) * SLOT - 5
            if appt is None:
                appt = Appointment(order_id=o.id, resource_id=a.resource_id, technician_id=a.tech_id, day=day, start_min=start,
                                   planned_end_min=end, planned_minutes=planned, first_start_min=start, source=source)
                db.add(appt)
            else:
                if appt.start_min != start or appt.resource_id != a.resource_id:
                    moved += 1
                    appt.moves += 1
                    if start > appt.start_min:
                        o.displaced_count += 1
                appt.resource_id, appt.technician_id, appt.start_min, appt.planned_end_min, appt.planned_minutes = a.resource_id, a.tech_id, start, end, planned
            if mode == "recover":
                appt.recovered, appt.source = True, "recovery"
                recovered += 1
                w = db.query(WaitlistEntry).filter(WaitlistEntry.order_id == o.id).first()
                if w:
                    w.status = "recovered"
            o.status = "scheduled"
            db.flush()
            appt.last_run_id = run.id
        elif mode != "recover":
            if appt is not None:
                appt.status = "displaced"
                o.displaced_count += 1
                moved += 1
            o.status = "waitlisted"
            _waitlist(db, o, day)
    run.explain = {str(o.id): explain_job(problem, res, o.id, names) for o in orders}
    return dict(moved=moved, recovered=recovered)


def run_optimization(db: Session, day: date, mode: str, now: int, trigger: str = "", trigger_event: OperationalEvent | None = None,
                     new_orders: list | None = None, source: str | None = None) -> OptimizationRun:
    all_orders = db.query(TestOrder).filter(TestOrder.day == day, TestOrder.status.in_(("pending", "scheduled", "waitlisted"))).all()
    appts = db.query(Appointment).filter(Appointment.day == day, Appointment.status.in_(ACTIVE)).all()
    by_id = {o.id: o for o in all_orders}
    if mode == "initial":
        free, fixed = all_orders, [a for a in appts if a.status == "in_progress"]
    elif mode == "insert":
        free, fixed = list(new_orders or []), appts
    elif mode == "reopt":
        frozen = [a for a in appts if a.status == "scheduled" and now <= a.start_min < now + FREEZE]
        flex_ids = {a.order_id for a in appts if a.status == "scheduled" and a not in frozen}
        free = [by_id[i] for i in flex_ids if i in by_id] + [o for o in (new_orders or []) if o.id not in flex_ids]
        fixed = [a for a in appts if a.status == "in_progress"] + frozen
    elif mode == "recover":
        free, fixed = [o for o in all_orders if o.status == "waitlisted"], appts
    else:
        raise ValueError(mode)
    problem = build_problem(db, day, now, free, fixed, recover=(mode == "recover"))
    res = solve(problem, backend=settings.solver_backend, order="priority", sticky=True)
    run = OptimizationRun(day=day, mode=mode, trigger=trigger, trigger_event_id=getattr(trigger_event, "id", None), backend=res.backend,
                          status=res.status, stages=res.stages, solve_ms=res.solve_ms, n_scheduled=len(res.assignments),
                          n_unscheduled=len(res.unscheduled))
    db.add(run)
    db.flush()
    stats = apply_result(db, day, mode, res, problem, free, run, source or {"recover": "recovery", "reopt": "reopt"}.get(mode, mode))
    run.n_moved, run.n_recovered = stats["moved"], stats["recovered"]
    if trigger_event is not None:
        trigger_event.run_id = run.id
    db.commit()
    hub.publish({"type": "schedule_updated", "run_id": run.id, "mode": mode, "trigger": trigger, "moved": run.n_moved,
                 "recovered": run.n_recovered, "backend": run.backend})
    return run


# ---------------------------------------------------------------- orders
def create_order_and_schedule(db: Session, order: TestOrder, now: int, day: date, user=None) -> OptimizationRun:
    db.add(order)
    db.flush()
    db.refresh(order)
    predict_orders(db, [order], now, day)
    mode = "reopt" if order.priority <= 1 else "insert"
    ev = None
    if order.priority == 0:
        ev = OperationalEvent(type="stat_order", day=day, at_min=now, payload={"order_id": order.id}, created_by=getattr(user, "id", None),
                              note="STAT order arrived (priority set by clinician)")
        db.add(ev)
        db.flush()
    run = run_optimization(db, day, mode, now, trigger=f"new_{['stat', 'urgent', 'routine'][order.priority]}_order", trigger_event=ev,
                           new_orders=[order], source="stat" if order.priority == 0 else mode)
    recover_if_possible(db, day, now)
    return run


def recover_if_possible(db: Session, day: date, now: int, trigger: str = "sweep", ev=None):
    if db.query(TestOrder).filter(TestOrder.day == day, TestOrder.status == "waitlisted").count():
        return run_optimization(db, day, "recover", now, trigger=trigger, trigger_event=ev)
    return None


# ---------------------------------------------------------------- events
def handle_event(db: Session, day: date, now: int, type_: str, payload: dict, user=None) -> dict:
    ev = OperationalEvent(type=type_, day=day, at_min=now, payload=payload, appointment_id=payload.get("appointment_id"),
                          resource_id=payload.get("resource_id"), created_by=getattr(user, "id", None))
    db.add(ev)
    db.flush()
    appt = db.get(Appointment, payload["appointment_id"]) if payload.get("appointment_id") else None
    runs, note = [], ""
    if type_ in ("cancellation", "no_show"):
        if not appt or appt.status != "scheduled":
            raise ValueError("appointment must be in 'scheduled' status")
        appt.status = "cancelled" if type_ == "cancellation" else "no_show"
        appt.order.status = "cancelled" if type_ == "cancellation" else "no_show"
        note = f"Slot {appt.resource.name} {appt.start_min // 60:02d}:{appt.start_min % 60:02d} released"
        db.flush()
        runs.append(recover_if_possible(db, day, now, trigger=type_, ev=ev))
    elif type_ == "early_completion":
        if not appt or appt.status != "in_progress":
            raise ValueError("appointment must be in progress")
        appt.status, appt.actual_end_min, appt.order.status = "completed", now, "completed"
        db.flush()
        runs.append(recover_if_possible(db, day, now, trigger=type_, ev=ev))
    elif type_ == "delay":
        minutes = int(payload.get("minutes", 15))
        if not appt or appt.status != "in_progress":
            raise ValueError("appointment must be in progress")
        appt.planned_end_min += minutes
        db.flush()
        if minutes >= REOPT_DELAY_THRESHOLD:
            runs.append(run_optimization(db, day, "reopt", now, trigger="delay", trigger_event=ev))
            runs.append(recover_if_possible(db, day, now, trigger="delay"))
        else:
            note = f"Delay of {minutes} min absorbed (below {REOPT_DELAY_THRESHOLD} min re-optimization threshold)"
    elif type_ in ("machine_down", "machine_up"):
        r = db.get(Resource, payload["resource_id"])
        if type_ == "machine_down":
            r.unavailable = list(r.unavailable or []) + [[now, now + int(payload.get("duration_min", 90))]]
        else:
            r.unavailable = [w for w in (r.unavailable or []) if w[1] <= now]
        db.flush()
        runs.append(run_optimization(db, day, "reopt", now, trigger=type_, trigger_event=ev))
        runs.append(recover_if_possible(db, day, now, trigger=type_))
    elif type_ == "staff_unavailable":
        a = db.query(StaffAvailability).filter(StaffAvailability.technician_id == payload["technician_id"], StaffAvailability.day == day).first()
        if a:
            a.end_min = min(a.end_min, now)
        db.flush()
        runs.append(run_optimization(db, day, "reopt", now, trigger=type_, trigger_event=ev))
        runs.append(recover_if_possible(db, day, now, trigger=type_))
    else:
        raise ValueError(f"unsupported event type {type_}")
    ev.note = ev.note or note
    db.commit()
    runs = [r for r in runs if r]
    hub.publish({"type": "event", "event": type_, "event_id": ev.id, "note": ev.note})
    return {"event_id": ev.id, "runs": [r.id for r in runs], "note": ev.note}
