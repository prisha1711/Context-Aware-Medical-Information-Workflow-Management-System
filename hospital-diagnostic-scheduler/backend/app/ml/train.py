"""Train duration (mean + p80) and no-show models. Run: python -m app.ml.train [--csv history.csv]"""
import argparse
import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.metrics import brier_score_loss, mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ..config import settings
from .features import (DURATION_CATEGORICAL, DURATION_FEATURES, DURATION_QUANTILE, NOSHOW_CATEGORICAL, NOSHOW_FEATURES)


def _prep(cols, cats):
    return ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cats)],
                             remainder="passthrough", verbose_feature_names_out=False).set_output(transform="default") \
        if cats else "passthrough"


def _regressor(kind, quantile=None):
    if kind == "xgboost":
        try:
            from xgboost import XGBRegressor
            if quantile is None:
                return XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.9)
            return XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, objective="reg:quantileerror", quantile_alpha=quantile)
        except ImportError:
            print("xgboost not installed -> falling back to sklearn")
    if quantile is None:
        return GradientBoostingRegressor(n_estimators=250, max_depth=3, learning_rate=0.06, subsample=0.9, random_state=0)
    return GradientBoostingRegressor(loss="quantile", alpha=quantile, n_estimators=250, max_depth=3, learning_rate=0.06, random_state=0)


def _classifier(kind):
    if kind == "xgboost":
        try:
            from xgboost import XGBClassifier
            return XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, eval_metric="logloss")
        except ImportError:
            print("xgboost not installed -> falling back to sklearn")
    return GradientBoostingClassifier(n_estimators=150, max_depth=3, learning_rate=0.06, random_state=0)


def _log_mlflow(name, metrics):
    if not settings.mlflow_uri:
        return
    try:
        import mlflow
        mlflow.set_tracking_uri(settings.mlflow_uri)
        with mlflow.start_run(run_name=name):
            mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
    except Exception as exc:  # tracking must never break training
        print("mlflow logging skipped:", exc)


def train_duration(df: pd.DataFrame, kind: str = "sklearn") -> dict:
    X, y = df[DURATION_FEATURES], df["duration_min"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=0)
    mean = Pipeline([("p", _prep(DURATION_FEATURES, DURATION_CATEGORICAL)), ("m", _regressor(kind))]).fit(Xtr, ytr)
    q = Pipeline([("p", _prep(DURATION_FEATURES, DURATION_CATEGORICAL)), ("m", _regressor(kind, DURATION_QUANTILE))]).fit(Xtr, ytr)
    pm, pq = mean.predict(Xte), np.maximum(q.predict(Xte), mean.predict(Xte))
    base = Xte["modality"].map(ytr.groupby(Xtr["modality"]).mean())     # "fixed average per modality" baseline
    metrics = dict(
        mae=float(mean_absolute_error(yte, pm)), rmse=float(np.sqrt(mean_squared_error(yte, pm))), r2=float(r2_score(yte, pm)),
        baseline_mae=float(mean_absolute_error(yte, base)), baseline_rmse=float(np.sqrt(mean_squared_error(yte, base))),
        p80_coverage=float((yte.values <= pq).mean()), n_train=int(len(Xtr)), n_test=int(len(Xte)), backend=kind)
    bundle = dict(mean=mean, q80=q, metrics=metrics, features=DURATION_FEATURES, trained_at=time.time(),
                  version=time.strftime("%Y%m%d-%H%M%S"))
    _save("duration", bundle)
    _log_mlflow("duration", metrics)
    return metrics


def train_no_show(df: pd.DataFrame, kind: str = "sklearn") -> dict:
    X, y = df[NOSHOW_FEATURES], df["no_show"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=0, stratify=y)
    clf = Pipeline([("p", _prep(NOSHOW_FEATURES, NOSHOW_CATEGORICAL)),
                    ("m", CalibratedClassifierCV(_classifier(kind), method="isotonic", cv=3))]).fit(Xtr, ytr)
    p = clf.predict_proba(Xte)[:, 1]
    top = p >= np.quantile(p, 0.8)
    metrics = dict(auc=float(roc_auc_score(yte, p)), brier=float(brier_score_loss(yte, p)),
                   brier_base_rate=float(brier_score_loss(yte, np.full(len(yte), ytr.mean()))),
                   base_rate=float(ytr.mean()), top_quintile_no_show_rate=float(yte.values[top].mean()),
                   n_train=int(len(Xtr)), n_test=int(len(Xte)), backend=kind)
    bundle = dict(clf=clf, metrics=metrics, features=NOSHOW_FEATURES, trained_at=time.time(), version=time.strftime("%Y%m%d-%H%M%S"))
    _save("no_show", bundle)
    _log_mlflow("no_show", metrics)
    return metrics


def _save(name, bundle):
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, settings.models_dir / f"{name}_latest.joblib")
    (settings.models_dir / f"{name}_metrics.json").write_text(json.dumps(bundle["metrics"], indent=2))


def train_all(df: pd.DataFrame | None = None, kind: str | None = None) -> dict:
    if df is None:
        from synth.generator import generate_history
        df = generate_history()
    kind = kind or settings.ml_backend
    return {"duration": train_duration(df, kind), "no_show": train_no_show(df, kind)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--backend", default=None)
    a = ap.parse_args()
    out = train_all(pd.read_csv(a.csv) if a.csv else None, a.backend)
    print(json.dumps(out, indent=2))
