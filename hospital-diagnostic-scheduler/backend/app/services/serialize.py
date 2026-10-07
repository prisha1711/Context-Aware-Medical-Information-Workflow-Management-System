from datetime import date

from sqlalchemy.orm import Session

from ..models import Appointment, Prediction, TestOrder


def appointment_dicts(db: Session, day: date) -> list:
    appts = db.query(Appointment).filter(Appointment.day == day).order_by(Appointment.start_min).all()
    ids = [a.order_id for a in appts]
    preds = {}
    for p in db.query(Prediction).filter(Prediction.order_id.in_(ids)).order_by(Prediction.id) if ids else []:
        preds.setdefault(p.order_id, {})[p.kind] = p
    out = []
    for a in appts:
        o, pr = a.order, preds.get(a.order_id, {})
        out.append(dict(id=a.id, order_id=a.order_id, patient=o.patient.name, test_code=o.test.code, modality=o.test.modality, priority=o.priority,
                        resource_id=a.resource_id, resource=a.resource.name, technician_id=a.technician_id, start_min=a.start_min,
                        end_min=a.planned_end_min, planned_minutes=a.planned_minutes, status=a.status, recovered=a.recovered, moves=a.moves,
                        source=a.source, actual_start_min=a.actual_start_min, actual_end_min=a.actual_end_min, wait_days=o.wait_days,
                        displaced=o.displaced_count, pred_mean=pr["duration"].value if "duration" in pr else None,
                        pred_p80=pr["duration"].p80 if "duration" in pr else None, no_show_prob=pr["no_show"].value if "no_show" in pr else None))
    return out


def waitlist_dicts(db: Session, day: date) -> list:
    from ..core.types import Job, Weights
    orders = db.query(TestOrder).filter(TestOrder.day == day, TestOrder.status == "waitlisted").all()
    preds = {}
    for p in db.query(Prediction).filter(Prediction.order_id.in_([o.id for o in orders])).order_by(Prediction.id) if orders else []:
        preds.setdefault(p.order_id, {})[p.kind] = p
    w = Weights()
    rows = []
    for o in orders:
        ns = preds.get(o.id, {}).get("no_show")
        job = Job(o.id, o.test.modality, o.priority, 1, wait_days=o.wait_days, displaced=o.displaced_count, no_show_prob=ns.value if ns else 0.1)
        rows.append((w.rank_key(job), dict(order_id=o.id, patient=o.patient.name, test_code=o.test.code, modality=o.test.modality, priority=o.priority,
                                           wait_days=o.wait_days, displaced=o.displaced_count, no_show_prob=job.no_show_prob)))
    return [r for _, r in sorted(rows, key=lambda x: x[0])]
