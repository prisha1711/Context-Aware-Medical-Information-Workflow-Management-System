# AI-Powered Dynamic Diagnostic Scheduling & Slot Recovery

Decision-support for **when and where** a clinician-ordered MRI/CT test can be done. It does not diagnose, does not decide whether a test is
needed and does not set clinical urgency (the clinician marks STAT / Urgent / Routine).

**Loop:** history + live data → ML predictions (duration p80, no-show risk) → CP-SAT optimization → live schedule →
event monitor (cancel, no-show, delay, STAT, machine down, staff out) → re-optimize or recover the slot from the waitlist.

Built for the Med-Tech Club project with SMCW (extension of *Context-Aware Hospital Information and Workflow Network*).

## Quick start (Docker)
```bash
cp .env.example .env
docker compose up --build
# API docs  http://localhost:8000/docs     Dashboard  http://localhost:5173
```
Demo logins: `admin/admin123`, `scheduler/sched123`, `doctor/doc123`, `tech/tech123`, `viewer/view123`.
Press **Play** in the dashboard, or inject events (cancel, no-show, delay, machine down, STAT) and watch slots get recovered.

## Local development (no Docker)
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.ml.train                 # trains duration + no-show models on synthetic history
python -m sim.benchmark --days 20      # baseline ladder -> sim/results/latest.json (shown in the dashboard)
uvicorn app.main:app --reload          # SQLite by default; set DATABASE_URL for Postgres
cd ../frontend && npm install && npm run dev
python -m pytest -q                    # from backend/
```

## Repository map
```
backend/app/core      pure scheduling core: types, greedy baseline, CP-SAT model, recovery, explanations  (no web/db deps)
backend/app/ml        features, training (sklearn or XGBoost), serving with safe fallbacks, optional MLflow
backend/app/services  DB <-> core orchestration, events, KPIs, demo autopilot, WebSocket hub
backend/app/routers   FastAPI endpoints (auth/RBAC, orders, schedule, events, demo, ws)
backend/synth         synthetic ground truth + data generator (replace with de-identified SMCW history)
backend/sim           discrete-event day simulator + Monte-Carlo benchmark of the baseline ladder
backend/tests         unit, solver, ML, simulation and API tests
frontend/src          React + TypeScript dashboard (timeline, KPIs, waitlist, explanations, benchmark chart)
docs                  architecture, weights elicitation plan, team guide
```

## Baseline ladder (evaluated by `sim.benchmark`)
FCFS → Priority + greedy → **Optimizer without ML** → **ML + optimizer**. The gap between the last two isolates what the ML adds.
Metrics: patients served, average and maximum day-of delay, STAT wait, overtime, utilization, slots recovered / freed, plan moves, max displacements.

## Honest status of this demo
* Data is **synthetic**. Numbers are illustrative, not evidence for SMCW until the generator is calibrated on real patterns.
* Objective weights are **placeholders** (see `docs/weights_elicitation.md`).
* Without OR-Tools installed, the optimizer falls back to a greedy solver with the same hard constraints (the benchmark prints which backend ran).
* Explanations are rule-based reconstructions, not solver internals.
* Not production ready: no Alembic migrations, simplified auth, single-process demo clock, no notification service, one-day horizon.

## Next steps
Alembic migrations · calibrate generator + weights with SMCW · technician breaks and room conflicts · multi-day waitlist · notifications ·
drift monitoring and scheduled retraining from `appointments.actual_*` · data-governance review before any real data.
