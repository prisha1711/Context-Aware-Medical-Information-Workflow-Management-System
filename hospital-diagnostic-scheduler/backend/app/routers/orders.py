from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Patient, Test, TestOrder
from ..schemas import OrderIn
from ..services import clock
from ..services.audit import audit
from ..services.scheduling import create_order_and_schedule

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("")
def create_order(body: OrderIn, db: Session = Depends(get_db), user=Depends(require_roles("doctor", "scheduler", "admin"))):
    test = db.query(Test).filter(Test.code == body.test_code).first()
    if not test:
        raise HTTPException(404, "Unknown test code")
    day, now = clock.get_day(), clock.get_now()
    n = db.query(Patient).count() + 1
    p = Patient(mrn=f"NEW-{n:05d}", name=body.patient_name, age=body.age)
    db.add(p)
    db.flush()
    o = TestOrder(patient_id=p.id, test_id=test.id, ordered_by=user.id, priority=body.priority, contrast=body.contrast, sedation=body.sedation,
                  inpatient=body.inpatient, day=day, window_start_min=body.window_start_min, window_end_min=body.window_end_min,
                  prereq_ready_min=body.prereq_ready_min)
    run = create_order_and_schedule(db, o, now, day, user)
    audit(db, user, "create_order", "test_order", o.id, priority=o.priority, test=body.test_code)
    db.commit()
    return {"order_id": o.id, "status": o.status, "run_id": run.id, "explanation": run.explain.get(str(o.id))}


@router.get("")
def list_orders(db: Session = Depends(get_db), user=Depends(get_current_user)):
    day = clock.get_day()
    return [dict(id=o.id, patient=o.patient.name, test=o.test.code, priority=o.priority, status=o.status, wait_days=o.wait_days, displaced=o.displaced_count)
            for o in db.query(TestOrder).filter(TestOrder.day == day).order_by(TestOrder.id)]
