from app.config import settings
from app.ml.predict import Predictor
from app.ml.train import train_duration, train_no_show
from synth.generator import generate_day, generate_history


def test_history_is_sane():
    h = generate_history(1500, seed=3)
    assert h.groupby("modality").duration_min.mean()["MRI"] > h.groupby("modality").duration_min.mean()["CT"]
    assert 0.03 < h.no_show.mean() < 0.25


def test_duration_model_beats_modality_average_and_p80_is_calibrated():
    h = generate_history(4000, seed=5)
    m = train_duration(h)
    assert m["mae"] < m["baseline_mae"]
    assert 0.7 < m["p80_coverage"] < 0.9


def test_no_show_model_is_better_than_chance():
    m = train_no_show(generate_history(5000, seed=6))
    assert m["auc"] > 0.62


def test_predictor_serves_and_falls_back():
    train_duration(generate_history(1500, seed=7))
    pr = Predictor()
    rows = generate_day(1, 6)
    out = pr.predict_duration(rows)
    assert len(out) == 6 and all(p80 >= mean > 0 for mean, p80 in out)
    for f in settings.models_dir.glob("*.joblib"):
        f.unlink()
    assert Predictor().predict_no_show(rows) == [0.10] * 6
