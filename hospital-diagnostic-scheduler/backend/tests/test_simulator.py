from app.ml.train import train_all
from sim.simulator import STRATEGIES, run_day


def test_every_strategy_completes_a_day():
    train_all()
    for key in STRATEGIES:
        m = run_day(11, key, n_orders=40, time_limit=0.5)
        assert m["served"] > 10 and m["utilization"] > 0


def test_priority_handling_serves_stat_much_faster_than_fcfs():
    train_all()
    fcfs = [run_day(s, "fcfs", n_orders=48)["stat_wait"] for s in range(20, 26)]
    prio = [run_day(s, "priority", n_orders=48)["stat_wait"] for s in range(20, 26)]
    assert sum(prio) < sum(fcfs)


def test_recovery_recovers_something_on_average():
    train_all()
    rec = [run_day(s, "full", n_orders=64, time_limit=0.5)["recovered"] for s in range(30, 34)]
    assert sum(rec) > 0
