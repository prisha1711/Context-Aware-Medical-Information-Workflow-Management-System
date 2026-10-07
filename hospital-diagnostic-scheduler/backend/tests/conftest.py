import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("MODELS_DIR", f"{_tmp}/models")
os.environ.setdefault("RESULTS_DIR", f"{_tmp}/results")
os.environ.setdefault("SEED_DEMO_ON_START", "0")
os.environ.setdefault("SOLVER_TIME_LIMIT", "2")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
