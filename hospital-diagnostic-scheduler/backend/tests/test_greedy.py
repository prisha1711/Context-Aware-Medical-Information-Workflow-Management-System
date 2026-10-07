from app.core.greedy import solve_greedy
from app.core.types import Fixed, Job
from tests.helpers import check_hard_constraints, small_problem


def jobs(n, modality="MRI", prio=2, dur=8):
    return [Job(i, modality, prio, dur, earliest=0, latest_end=114) for i in range(1, n + 1)]


def test_no_overlaps_and_modality():
    p = small_problem(jobs(10) + [Job(50 + i, "CT", 2, 3, 0, 114) for i in range(6)])
    r = solve_greedy(p)
    assert not check_hard_constraints(p, r)
    assert len(r.assignments) == 16


def test_respects_downtime_and_fixed():
    p = small_problem(jobs(2), fixed=[Fixed(2, 2, 0, 30, 99)], down=[(0, 20)])
    r = solve_greedy(p)
    assert not check_hard_constraints(p, r)
    assert all(a.start >= 20 for a in r.assignments.values() if a.resource_id == 1)
    assert all(a.start >= 30 for a in r.assignments.values() if a.resource_id == 2)


def test_stat_beats_routine_when_capacity_scarce():
    js = [Job(i, "CT", 2, 20, 0, 40) for i in range(1, 4)] + [Job(99, "CT", 0, 20, 0, 40)]
    r = solve_greedy(small_problem(js))
    assert 99 in r.assignments and len(r.assignments) == 2 and len(r.unscheduled) == 2


def test_sticky_keeps_existing_slot():
    j = Job(1, "MRI", 2, 8, earliest=0, latest_end=114, prev_start=40, prev_resource=2)
    r = solve_greedy(small_problem([j]), sticky=True)
    a = r.assignments[1]
    assert (a.start, a.resource_id) == (40, 2)


def test_patient_window_is_hard():
    j = Job(1, "MRI", 2, 8, earliest=10, latest_end=15)   # window shorter than the case
    r = solve_greedy(small_problem([j]))
    assert r.unscheduled == [1]


def test_technician_shift_is_hard():
    from app.core.types import Tech
    p = small_problem(jobs(1), techs=[Tech(1, {"MRI"}, (0, 5))])
    assert solve_greedy(p).unscheduled == [1]
