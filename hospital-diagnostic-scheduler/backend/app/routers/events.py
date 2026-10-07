from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import OperationalEvent
from ..schemas import EventIn
from ..services import clock
from ..services.audit import audit
from ..services.scheduling import handle_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("")
def post_event(body: EventIn, db: Session = Depends(get_db), user=Depends(require_roles("scheduler", "technician", "admin"))):
    payload = body.model_dump(exclude={"type"}, exclude_none=True)
    try:
        out = handle_event(db, clock.get_day(), clock.get_now(), body.type, payload, user)
    except (ValueError, KeyError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    audit(db, user, f"event:{body.type}", "operational_event", out["event_id"], **payload)
    db.commit()
    return out


@router.get("")
def list_events(limit: int = 50, db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(OperationalEvent).filter(OperationalEvent.day == clock.get_day()).order_by(OperationalEvent.id.desc()).limit(limit)
    return [dict(id=e.id, type=e.type, at_min=e.at_min, payload=e.payload, note=e.note, run_id=e.run_id) for e in q]
