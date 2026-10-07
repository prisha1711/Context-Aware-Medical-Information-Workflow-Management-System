"""Central settings. Everything is overridable through environment variables (see .env.example)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", f"sqlite:///{BACKEND_DIR}/dev.db"))
    jwt_secret: str = field(default_factory=lambda: _env("JWT_SECRET", "change-me-in-production"))
    jwt_algorithm: str = "HS256"
    jwt_minutes: int = field(default_factory=lambda: int(_env("JWT_MINUTES", "480")))
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", ""))
    cors_origins: list = field(default_factory=lambda: _env("CORS_ORIGINS", "http://localhost:5173").split(","))
    # optimizer
    solver_backend: str = field(default_factory=lambda: _env("SOLVER_BACKEND", "auto"))  # auto|cpsat|greedy
    solver_time_limit: float = field(default_factory=lambda: float(_env("SOLVER_TIME_LIMIT", "5")))
    solver_workers: int = field(default_factory=lambda: int(_env("SOLVER_WORKERS", "4")))
    # ml
    ml_backend: str = field(default_factory=lambda: _env("ML_BACKEND", "sklearn"))  # sklearn|xgboost
    models_dir: Path = field(default_factory=lambda: Path(_env("MODELS_DIR", str(BACKEND_DIR / "models"))))
    results_dir: Path = field(default_factory=lambda: Path(_env("RESULTS_DIR", str(BACKEND_DIR / "sim" / "results"))))
    mlflow_uri: str = field(default_factory=lambda: _env("MLFLOW_TRACKING_URI", ""))
    seed_demo_on_start: bool = field(default_factory=lambda: _env("SEED_DEMO_ON_START", "1") == "1")


settings = Settings()
