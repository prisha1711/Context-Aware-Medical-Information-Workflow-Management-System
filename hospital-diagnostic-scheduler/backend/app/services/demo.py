"""Demo data seeding and the 'autopilot' that plays a synthetic day (stands in for real EHR/PACS events)."""
from datetime import date

import numpy as np
from sqlalchemy.orm import Session

from synth.generator import generate_day, make_script, stat_case
from synth.truth import TESTS

from ..core.timeutil import DAY_END, DAY_START
from ..models import (Appointment, AuditLog, OperationalEvent, OptimizationRun, Patient, Prediction, Resource, StaffAvailability,
                      Technician, Test, TestOrder, User, WaitlistEntry)
from ..security import hash_password
from . import clock
from .scheduling import create_order_and_schedule, handle_event, predict_orders, recover_if_possible, run_optimization
from .ws import hub

DEMO_USERS = [("admin", "admin123", "admin", "Admin"), ("scheduler", "sched123", "scheduler", "Scheduling Desk"),
              ("doctor", "doc123", "doctor", "Dr. Demo"), ("tech", "tech123", "technician", "Technologist"), ("viewer", "view123", "viewer", "Viewer")]
TECH_DEFS = [("Tech A", ["MRI", "CT"], 480, 1050), ("Tech B", ["MRI"], 480, 1050), ("Tech C", ["CT"], 480, 1050), ("Tech D", ["MRI"], 540, 1050)]


def ensure_reference_data(db: Session):
    for u, pw, role, name in DEMO_USERS:
        if not db.query(User).filter(User.username == u).first():
            db.add(User(username=u, password_hash=hash_password(pw), role=role, full_name=name))
    for code, (mod, base) in TESTS.items():
        if not db.query(Test).filter(Test.code == code).first():
            db.add(Test(code=code, name=code.replace("_", " ").title(), modality=mod, base_minutes=base))
    if not db.query(Resource).count():
        for n, mod, room in [("MRI-1", "MRI", "Room MR1"), ("MRI-2", "MRI", "Room MR2"), ("CT-1", "CT", "Room CT1")]:
            db.add(Resource(name=n, modality=mod, room=room, unavailable=[]))
    if not db.query(Technician).count():
        for n, certs, _, _ in TECH_DEFS:
            db.add(Technician(name=n, certifications=certs))
    db.commit()


def reset_day(db: Session):
    for m in (Prediction, WaitlistEntry, Appointment, OperationalEvent, OptimizationRun, TestOrder, Patient, StaffAvailability):
        db.query(m).delete()
    for r in db.query(Resource):
        r.unavailable = []
    db.commit()


def seed_demo(db: Session, day: date | None = None, seed: int = 7, n_orders: int = 64, disruptions: bool = True) -> dict:
    day = day or date.today()
    ensure_reference_data(db)
    reset_day(db)
    techs = db.query(Technician).order_by(Technician.id).all()
    for t, (_, _, s, e) in zip(techs, TECH_DEFS):
        db.add(StaffAvailability(technician_id=t.id, day=day, start_min=s, end_min=e))
    tests = {t.code: t for t in db.query(Test)}
    orders, case_map = [], {}
    for f in generate_day(seed, n_orders):
        p = Patient(mrn=f"M{seed}-{f['id']:03d}", name=f"Patient {f['id']:03d}", age=f["age"], prior_no_shows=f["prior_no_shows"], distance_km=f["distance_km"])
        db.add(p)
        db.flush()
        o = TestOrder(patient_id=p.id, test_id=tests[f["test_code"]].id, priority=f["priority"], contrast=bool(f["contrast"]), sedation=bool(f["sedation"]),
                      inpatient=bool(f["inpatient"]), day=day, window_start_min=f["window"][0], window_end_min=f["window"][1], lead_days=f["lead_days"],
                      sms_confirmed=bool(f["sms_confirmed"]), wait_days=f["wait_days"], sim_true_duration=f["true_duration"], sim_no_show=f["will_no_show"])
        db.add(o)
        db.flush()
        orders.append(o)
        case_map[f["id"]] = o.id
    db.flush()
    for o in orders:
        db.refresh(o)
    predict_orders(db, orders, DAY_START, day)
    db.commit()
    clock.STATE.update(day=day, now=DAY_START, seed=seed, case_map=case_map, resource_ids=[r.id for r in db.query(Resource).order_by(Resource.id)],
                       script=make_script(seed, n_orders) if disruptions else [], stat_n=0)
    run = run_optimization(db, day, "initial", DAY_START, trigger="seed")
    recover_if_possible(db, day, DAY_START, trigger="seed")
    hub.publish({"type": "reset", "day": str(day)})
    return {"day": str(day), "orders": len(orders), "run_id": run.id, "scheduled": run.n_scheduled, "waitlisted": run.n_unscheduled}


def _fire_script(db, day, now, e):
    st = clock.STATE
    if e["k"] == "cx":
        oid = st["case_map"].get(e["id"])
        a = db.query(Appointment).filter(Appointment.order_id == oid, Appointment.status == "scheduled").first() if oid else None
        if a:
            handle_event(db, day, now, "cancellation", {"appointment_id": a.id})
    elif e["k"] == "down":
        handle_event(db, day, now, "machine_down", {"resource_id": st["resource_ids"][e["m"] - 1], "duration_min": e["len"]})
    elif e["k"] == "stat":
        st["stat_n"] += 1
        f = stat_case(np.random.default_rng(st["seed"] * 31 + st["stat_n"]), 9000 + st["stat_n"], e["mod"])
        inject_stat(db, day, now, f["test_code"], f)


def inject_stat(db: Session, day: date, now: int, test_code: str, f: dict | None = None, user=None):
    """Create a patient + STAT order and schedule it. `f` carries hidden demo truth when called by the autopilot."""
    f = f or stat_case(np.random.default_rng(now), 9500 + now, TESTS[test_code][0], test_code)
    n = db.query(Patient).count() + 1
    p = Patient(mrn=f"STAT-{day:%m%d}-{n:04d}", name=f"STAT Patient {n}", age=f["age"], prior_no_shows=0, distance_km=5.0)
    db.add(p)
    db.flush()
    t = db.query(Test).filter(Test.code == test_code).first()
    o = TestOrder(patient_id=p.id, test_id=t.id, priority=0, contrast=bool(f["contrast"]), sedation=bool(f["sedation"]), inpatient=True, day=day,
                  window_start_min=DAY_START, window_end_min=DAY_END + 30, sim_true_duration=f["true_duration"], sim_no_show=False, ordered_by=getattr(user, "id", None))
    run = create_order_and_schedule(db, o, now, day, user)
    return o, run


def advance(db: Session, minutes: int = 15) -> dict:
    st, day = clock.STATE, clock.STATE["day"]
    fired = 0
    for _ in range(max(1, minutes // 5)):
        st["now"] += 5
        now = st["now"]
        while st["script"] and st["script"][0]["t"] <= now:
            _fire_script(db, day, now, st["script"].pop(0))
            fired += 1
        trigger_reopt = False
        for a in db.query(Appointment).filter(Appointment.day == day, Appointment.status == "in_progress").all():
            true = a.order.sim_true_duration or a.planned_minutes
            if now < a.actual_start_min + true:
                continue
            pe = a.actual_start_min + a.planned_minutes
            if now < pe - 15:
                handle_event(db, day, now, "early_completion", {"appointment_id": a.id})
                fired += 1
                continue
            a.status, a.actual_end_min, a.order.status = "completed", now, "completed"
            if now > pe + 10:
                db.add(OperationalEvent(type="delay", day=day, at_min=now, payload={"appointment_id": a.id, "minutes": int(now - pe), "auto": True},
                                        appointment_id=a.id, note=f"Overran plan by {int(now - pe)} min"))
                trigger_reopt = True
            db.commit()
        if trigger_reopt:
            run_optimization(db, day, "reopt", now, trigger="overrun")
            recover_if_possible(db, day, now, trigger="overrun")
        running = db.query(Appointment).filter(Appointment.day == day, Appointment.status == "in_progress").all()
        busy_res, busy_tech = {a.resource_id for a in running}, {a.technician_id for a in running}
        for r in db.query(Resource).order_by(Resource.id):
            if r.id in busy_res or any(s <= now < e for s, e in (r.unavailable or [])):
                continue
            a = (db.query(Appointment).filter(Appointment.day == day, Appointment.resource_id == r.id, Appointment.status == "scheduled")
                 .order_by(Appointment.start_min).first())
            if not a or a.start_min > now:
                continue
            if a.order.sim_no_show:
                if now >= a.start_min + 10:
                    handle_event(db, day, now, "no_show", {"appointment_id": a.id})
                    fired += 1
            elif a.technician_id not in busy_tech:
                a.status, a.actual_start_min = "in_progress", now
                busy_tech.add(a.technician_id)
                db.commit()
        # periodic sweep: capacity also appears simply because time passes
        if now % 15 == 0:
            recover_if_possible(db, day, now, trigger="sweep")
    hub.publish({"type": "clock", "now": st["now"]})
    return {"now": st["now"], "events_fired": fired}
