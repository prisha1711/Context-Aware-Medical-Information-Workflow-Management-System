"""Calibrated-ish synthetic data: historical cases for model training and a 'day' of orders for demos/benchmarks."""
import numpy as np
import pandas as pd

from .truth import TESTS, expected_duration, no_show_prob, true_duration

CODES = list(TESTS)


def _features(rng, code=None):
    code = code or CODES[rng.integers(len(CODES))]
    mod = TESTS[code][0]
    return dict(
        test_code=code, modality=mod,
        contrast=int(rng.random() < (0.45 if mod == "CT" else 0.35)),
        sedation=int(mod == "MRI" and rng.random() < 0.08),
        inpatient=int(rng.random() < 0.25),
        age=int(np.clip(rng.normal(50, 18), 18, 92)),
        hour=int(rng.integers(8, 17)), dow=int(rng.integers(0, 5)),
        tech_exp=int(rng.integers(1, 15)),
        lead_days=int(rng.integers(0, 31)), prior_no_shows=int(rng.poisson(0.4)),
        sms_confirmed=int(rng.random() < 0.6), distance_km=float(np.round(rng.gamma(2, 6), 1)),
    )


def generate_history(n: int = 6000, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        f = _features(rng)
        f["duration_min"] = round(true_duration(rng, test_code=f["test_code"], contrast=f["contrast"], sedation=f["sedation"],
                                                age=f["age"], inpatient=f["inpatient"], tech_exp=f["tech_exp"]), 1)
        p = no_show_prob(f["age"], f["lead_days"], f["prior_no_shows"], f["dow"], f["hour"], f["sms_confirmed"],
                         f["inpatient"], f["distance_km"])
        f["no_show"] = int(rng.random() < p)
        rows.append(f)
    return pd.DataFrame(rows)


def generate_day(seed: int, n_orders: int = 64) -> list:
    """One simulated day of clinician orders (already created; the scheduler has to place them)."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n_orders):
        pool = [c for c in CODES if c.startswith("CT" if i % 32 >= 17 else "MRI")]
        f = _features(rng, pool[rng.integers(len(pool))])
        f["id"] = i + 1
        f["priority"] = 1 if rng.random() < 0.15 else 2
        f["wait_days"] = int(rng.integers(1, 46))
        f["true_duration"] = true_duration(rng, test_code=f["test_code"], contrast=f["contrast"], sedation=f["sedation"],
                                           age=f["age"], inpatient=f["inpatient"], tech_exp=f["tech_exp"])
        p = no_show_prob(f["age"], f["lead_days"], f["prior_no_shows"], f["dow"], f["hour"], f["sms_confirmed"],
                         f["inpatient"], f["distance_km"])
        f["will_no_show"] = bool(rng.random() < p)
        r = rng.random()
        f["window"] = (480, 1050) if r < 0.78 else ((600, 1050) if r < 0.89 else (480, 900))
        out.append(f)
    return out


def stat_case(rng, case_id: int, modality: str, code: str | None = None) -> dict:
    code = code or [c for c in CODES if c.startswith(modality)][rng.integers(3)]
    f = _features(rng, code)
    f.update(id=case_id, priority=0, wait_days=0, window=(480, 1050), lead_days=0, will_no_show=False)
    f["true_duration"] = true_duration(rng, test_code=code, contrast=f["contrast"], sedation=f["sedation"],
                                       age=f["age"], inpatient=1, tech_exp=f["tech_exp"])
    return f


def make_script(seed: int, n_orders: int) -> list:
    """Random disruptions for a day: cancellations, one STAT arrival, maybe one machine outage. Times in minutes."""
    r = np.random.default_rng(seed + 999)
    ev = [dict(t=int(5 * round((480 + 30 + r.random() * 420) / 5)), k="cx", id=i) for i in range(1, n_orders + 1) if r.random() < 0.07]
    ev.append(dict(t=int(5 * round((600 + r.random() * 240) / 5)), k="stat", mod="MRI" if r.random() < 0.6 else "CT"))
    if r.random() < 0.4:
        ev.append(dict(t=int(5 * round((540 + r.random() * 200) / 5)), k="down", m=1 if r.random() < 0.5 else 2, len=60))
    return sorted(ev, key=lambda e: e["t"])


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "history.csv"
    generate_history().to_csv(out, index=False)
    print("wrote", out)
