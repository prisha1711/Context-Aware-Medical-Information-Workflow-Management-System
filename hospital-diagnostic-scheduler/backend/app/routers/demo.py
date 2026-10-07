import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..core.solve import HAVE_ORTOOLS
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..schemas import AdvanceIn, SeedIn, StatIn
from ..services import clock
from ..services.audit import audit
from ..services.demo import advance, inject_stat, seed_demo

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/seed")
def seed(body: SeedIn, db: Session = Depends(get_db), user=Depends(require_roles("admin", "scheduler"))):
    out = seed_demo(db, date.today(), body.seed, body.n_orders, body.disruptions)
    audit(db, user, "seed_demo", "system", None, **body.model_dump())
    db.commit()
    return out


@router.post("/advance")
def adv(body: AdvanceIn, db: Session = Depends(get_db), user=Depends(require_roles("admin", "scheduler"))):
    return advance(db, body.minutes)


@router.post("/stat")
def stat(body: StatIn, db: Session = Depends(get_db), user=Depends(require_roles("admin", "scheduler", "doctor"))):
    try:
        o, run = inject_stat(db, clock.get_day(), clock.get_now(), body.test_code, None, user)
    except (AttributeError, KeyError):
        raise HTTPException(404, "Unknown test code")
    return {"order_id": o.id, "status": o.status, "run_id": run.id, "explanation": run.explain.get(str(o.id))}


@router.get("/clock")
def get_clock(user=Depends(get_current_user)):
    return {"day": str(clock.get_day()), "now": clock.get_now(), "pending_script_events": len(clock.STATE["script"]),
            "solver": "cpsat" if (HAVE_ORTOOLS and settings.solver_backend != "greedy") else "greedy"}


@router.get("/benchmarks")
def benchmarks(user=Depends(get_current_user)):
    f = settings.results_dir / "latest.json"
    if not f.exists():
        raise HTTPException(404, "No benchmark yet. Run: python -m sim.benchmark --days 20")
    return json.loads(f.read_text())
