from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  (register tables)
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import auth, catalog, demo, events, orders, schedule, ws
from .services.demo import ensure_reference_data, seed_demo
from .services.ws import hub


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)      # MVP: no migrations yet (add Alembic before any real deployment)
    with SessionLocal() as db:
        ensure_reference_data(db)
        if settings.seed_demo_on_start and not db.query(models.TestOrder).count():
            seed_demo(db)
    await hub.start()
    yield


app = FastAPI(title="Diagnostic Scheduling & Slot Recovery", version="0.1.0", lifespan=lifespan,
              description="Decision-support for WHEN/WHERE a clinician-ordered test can be done. No diagnosis, no clinical decisions.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
for r in (auth.router, catalog.router, orders.router, schedule.router, events.router, demo.router, ws.router):
    app.include_router(r)


@app.get("/health")
def health():
    return {"status": "ok"}
