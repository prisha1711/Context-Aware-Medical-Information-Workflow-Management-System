"""Backend dispatcher: CP-SAT when OR-Tools is installed, greedy fallback otherwise."""
import importlib.util

from .greedy import solve_greedy
from .types import Problem, Result

HAVE_ORTOOLS = importlib.util.find_spec("ortools") is not None


def solve(p: Problem, backend: str = "auto", order: str = "priority", sticky: bool = False) -> Result:
    use_cpsat = backend == "cpsat" or (backend == "auto" and HAVE_ORTOOLS)
    if use_cpsat:
        if not HAVE_ORTOOLS:
            raise RuntimeError("SOLVER_BACKEND=cpsat but ortools is not installed (pip install ortools)")
        from .cpsat import solve_cpsat
        return solve_cpsat(p)
    return solve_greedy(p, order=order, sticky=sticky)
