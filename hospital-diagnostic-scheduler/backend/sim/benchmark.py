"""Monte-Carlo baseline ladder.  python -m sim.benchmark --days 20
Same seeds (common random numbers) for every strategy.  Writes sim/results/latest.json for the dashboard."""
import argparse
import json
import time

import numpy as np

from app.config import settings
from app.core.solve import HAVE_ORTOOLS
from app.ml.predict import get_predictor
from app.ml.train import train_all
from sim.simulator import STRATEGIES, run_day

KEYS = ["served", "avg_delay", "max_delay", "stat_wait", "overtime", "utilization", "recovered", "fill_rate", "moves", "max_displaced"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=20)
    ap.add_argument("--orders", type=int, default=64)
    ap.add_argument("--seed0", type=int, default=1000)
    ap.add_argument("--time-limit", type=float, default=1.0)
    ap.add_argument("--backend", default=None, help="auto|cpsat|greedy for optimizer strategies")
    a = ap.parse_args(argv)
    if get_predictor().dur is None:
        print("no trained models found -> training on synthetic history")
        train_all()
        get_predictor().reload()
    out = dict(days=a.days, orders=a.orders, ortools=HAVE_ORTOOLS, created=time.strftime("%Y-%m-%d %H:%M"), strategies={})
    for key, cfg in STRATEGIES.items():
        rows = [run_day(a.seed0 + d, key, n_orders=a.orders, backend=a.backend if cfg["backend"] == "auto" else None, time_limit=a.time_limit)
                for d in range(a.days)]
        out["strategies"][key] = dict(label=cfg["label"], backend=rows[0]["backend"],
                                      mean={k: float(np.mean([r[k] for r in rows])) for k in KEYS},
                                      sem={k: float(np.std([r[k] for r in rows], ddof=1) / np.sqrt(len(rows))) if len(rows) > 1 else 0.0 for k in KEYS})
        print(f"{cfg['label']:<20} {rows[0]['backend']:<14}", {k: round(out['strategies'][key]['mean'][k], 1) for k in KEYS[:6]})
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    (settings.results_dir / "latest.json").write_text(json.dumps(out, indent=2))
    print("wrote", settings.results_dir / "latest.json")


if __name__ == "__main__":
    main()
