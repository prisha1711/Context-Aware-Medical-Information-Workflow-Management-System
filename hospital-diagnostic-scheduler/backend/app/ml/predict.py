"""Serving wrapper. Falls back to transparent heuristics if no trained model exists, so the API always works."""
import threading

import joblib
import numpy as np
import pandas as pd

from ..config import settings
from .features import DURATION_FEATURES, NOSHOW_FEATURES

FALLBACK_MEAN = {"MRI": 40.0, "CT": 16.0}   # fixed modality averages (also the "no-ML" baseline)
FALLBACK_P80_MULT = 1.29
FALLBACK_NO_SHOW = 0.10


class Predictor:
    def __init__(self):
        self._lock = threading.Lock()
        self.dur = None
        self.ns = None
        self.reload()

    def reload(self):
        with self._lock:
            d, n = settings.models_dir / "duration_latest.joblib", settings.models_dir / "no_show_latest.joblib"
            self.dur = joblib.load(d) if d.exists() else None
            self.ns = joblib.load(n) if n.exists() else None

    @property
    def status(self):
        return {"duration_model": self.dur["version"] if self.dur else "fallback-average",
                "no_show_model": self.ns["version"] if self.ns else "fallback-base-rate",
                "duration_metrics": self.dur["metrics"] if self.dur else None,
                "no_show_metrics": self.ns["metrics"] if self.ns else None}

    def predict_duration(self, rows: list) -> list:
        """-> [(mean_min, p80_min)]"""
        if not rows:
            return []
        if self.dur is None:
            return [(FALLBACK_MEAN[r["modality"]], FALLBACK_MEAN[r["modality"]] * FALLBACK_P80_MULT) for r in rows]
        X = pd.DataFrame(rows)[DURATION_FEATURES]
        mean, q = self.dur["mean"].predict(X), self.dur["q80"].predict(X)
        return [(float(m), float(max(m, p))) for m, p in zip(mean, q)]

    def predict_no_show(self, rows: list) -> list:
        if not rows:
            return []
        if self.ns is None:
            return [FALLBACK_NO_SHOW] * len(rows)
        return [float(x) for x in self.ns["clf"].predict_proba(pd.DataFrame(rows)[NOSHOW_FEATURES])[:, 1]]


_predictor = None


def get_predictor() -> Predictor:
    global _predictor
    if _predictor is None:
        _predictor = Predictor()
    return _predictor
