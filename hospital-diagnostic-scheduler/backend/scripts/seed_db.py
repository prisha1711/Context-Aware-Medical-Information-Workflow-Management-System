"""python -m scripts.seed_db [--seed 7] [--orders 64]  -> creates tables, users, catalog and a demo day."""
import argparse
from datetime import date

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.services.demo import seed_demo

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--orders", type=int, default=64)
ap.add_argument("--no-disruptions", action="store_true")
a = ap.parse_args()
Base.metadata.create_all(engine)
with SessionLocal() as db:
    print(seed_demo(db, date.today(), a.seed, a.orders, not a.no_disruptions))
