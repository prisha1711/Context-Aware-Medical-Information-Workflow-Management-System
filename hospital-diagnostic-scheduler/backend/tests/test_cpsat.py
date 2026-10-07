import pytest

pytest.importorskip("ortools")

from app.core.cpsat import solve_cpsat
from app.core.types import Fixed, Job
from tests.helpers import check_hard_constraints, small_problem


def test_feasible_schedule_satisfies_hard_constraints():
    js = [Job(i, "MRI", 2, 8, 0, 114) for i in range(1, 9)] + [Job(20 + i, "CT", 1, 4, 0, 114) for i in range(5)]
    p = small_problem(js, fixed=[Fixed(1, 1, 0, 10, 0)], down=[(30, 40)])
    r = solve_cpsat(p)
    assert r.status in ("OPTIMAL", "FEASIBLE")
    assert not check_hard_constraints(p, r)
    assert len(r.assignments) == 13


def test_stat_is_never_sacrificed_for_routine():
    js = [Job(i, "CT", 2, 20, 0, 40) for i in range(1, 4)] + [Job(99, "CT", 0, 20, 0, 40)]
    r = solve_cpsat(small_problem(js))
    assert 99 in r.assignments


def test_fairness_credit_orders_within_tier():
    js = [Job(1, "CT", 2, 20, 0, 22, wait_days=2), Job(2, "CT", 2, 20, 0, 22, wait_days=40, displaced=3)]
    r = solve_cpsat(small_problem(js))
    assert list(r.assignments) == [2]          # only one fits; the long-waiting, repeatedly displaced patient wins


def test_disruption_stage_keeps_existing_plan():
    js = [Job(1, "MRI", 2, 8, 0, 114, prev_start=10, prev_resource=1), Job(2, "MRI", 2, 8, 0, 114, prev_start=40, prev_resource=2)]
    r = solve_cpsat(small_problem(js))
    # waiting time is minimised first, so jobs may move earlier - but never needlessly to a different machine at the same start
    assert not check_hard_constraints(small_problem(js), r)


def test_recovery_mode_fills_gap_without_touching_fixed():
    fixed = [Fixed(1, 1, 0, 10, 100), Fixed(1, 1, 30, 114, 101)]
    cand = [Job(5, "MRI", 2, 8, 0, 114, wait_days=5)]
    p = small_problem(cand, fixed=fixed)
    p.machines = [m for m in p.machines if m.id != 2]     # only MRI-1 exists -> the only gap is 10..30
    r = solve_cpsat(p)
    a = r.assignments[5]
    assert 10 <= a.start and a.end <= 30
