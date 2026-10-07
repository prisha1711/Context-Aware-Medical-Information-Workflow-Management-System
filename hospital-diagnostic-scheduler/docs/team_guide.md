# Working on this repo as a team

| Area | Folder | Good first tasks |
|---|---|---|
| Optimizer | `backend/app/core` | add technician breaks, room conflicts, idle-time objective; tune stage time limits |
| ML | `backend/app/ml`, `backend/synth` | calibrate generator to SMCW patterns; try XGBoost; add drift monitoring |
| API / DB | `backend/app/routers`, `services`, `models.py` | Alembic migrations, notifications, pagination, multi-day scheduling |
| Simulation / evaluation | `backend/sim` | more strategies, sensitivity analysis, fairness metrics |
| Frontend | `frontend/src` | order form, drag-to-explain, mobile layout, role-based views |
| Docs / governance | `docs` | weights elicitation, data governance, report |

Branching: `main` is protected; use `feature/<area>-<short-name>` and open a PR; CI must pass.
Run `make test` before pushing. Never commit real patient data; `.gitignore` already excludes models, databases and results.
