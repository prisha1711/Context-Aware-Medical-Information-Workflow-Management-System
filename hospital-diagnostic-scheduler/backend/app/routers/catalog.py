from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..ml.predict import get_predictor
from ..models import Resource, Technician, Test

router = APIRouter(tags=["catalog"], dependencies=[Depends(get_current_user)])


@router.get("/tests")
def tests(db: Session = Depends(get_db)):
    return [dict(id=t.id, code=t.code, name=t.name, modality=t.modality, base_minutes=t.base_minutes) for t in db.query(Test)]


@router.get("/resources")
def resources(db: Session = Depends(get_db)):
    return [dict(id=r.id, name=r.name, modality=r.modality, room=r.room, unavailable=r.unavailable) for r in db.query(Resource)]


@router.get("/technicians")
def technicians(db: Session = Depends(get_db)):
    return [dict(id=t.id, name=t.name, certifications=t.certifications) for t in db.query(Technician)]


@router.get("/ml/status")
def ml_status():
    return get_predictor().status


@router.post("/ml/train", dependencies=[Depends(require_roles("admin"))])
def ml_train():
    """Retrains on synthetic history (swap in de-identified SMCW history via app.ml.train --csv)."""
    from ..ml.train import train_all
    metrics = train_all()
    get_predictor().reload()
    return metrics
