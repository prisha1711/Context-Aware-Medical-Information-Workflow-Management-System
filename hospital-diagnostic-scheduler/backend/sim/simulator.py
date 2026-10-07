"""In-memory discrete-event simulator of one diagnostic day (MRI-1, MRI-2, CT-1).

Plays the SAME scheduling core (app.core) that the API uses, against ground-truth outcomes that the scheduler
cannot see (true durations, real no-shows).  Used for the baseline ladder:
    FCFS  ->  Priority + greedy  ->  Optimizer without ML  ->  ML + optimizer
"""
import math
from dataclasses import dataclass, field

import numpy as np

from app.core.recovery import find_gaps
from app.core.solve import solve
from app.core.timeutil import DAY_END, DAY_START, FREEZE, HORIZON, LEAD, REG_END_SLOT, dur_slots, to_min, to_slot
from app.core.types import Fixed, Job, Machine, Problem, Tech
from app.ml.predict import FALLBACK_MEAN, FALLBACK_NO_SHOW, get_predictor
from synth.generator import generate_day, make_script, stat_case

STRATEGIES = {
    "fcfs": dict(label="FCFS", durations="avg", order="fcfs", reopt=False, recover=False, sticky=False, backend="greedy"),
    "priority": dict(label="Priority + greedy", durations="avg", order="priority", reopt=True, recover=False, sticky=False, backend="greedy"),
    "opt": dict(label="Optimizer, no ML", durations="avg", order="priority", reopt=True, recover=True, sticky=True, backend="auto"),
    "full": dict(label="ML + optimizer", durations="ml", order="priority", reopt=True, recover=True, sticky=True, backend="auto"),
}
MACHINES = [(1, "MRI", "MRI-1"), (2, "MRI", "MRI-2"), (3, "CT", "CT-1")]
TECHS = [(1, {"MRI", "CT"}, (0, HORIZON)), (2, {"MRI"}, (0, HORIZON)), (3, {"CT"}, (0, HORIZON)), (4, {"MRI"}, (12, HORIZON))]


@dataclass
class Case:
    f: dict
    id: int
    priority: int
    modality: str
    true_dur: float
    will_no_show: bool
    win: tuple
    wait_days: int
    plan_min: float = 0.0
    ns_pred: float = FALLBACK_NO_SHOW
    status: str = "new"      # new|sch|run|done|cx|ns|wait
    res: int = None
    tech: int = None
    start: float = None
    s0: float = None
    as_: float = None
    ae: float = None
    displaced: int = 0
    recovered: bool = False
    arr: float = None


class DaySim:
    def __init__(self, seed: int, strategy: str, n_orders: int = 64, backend: str | None = None,
                 time_limit: float = 1.0, disruptions: bool = True):
        self.cfg = STRATEGIES[strategy]
        self.backend = backend or self.cfg["backend"]
        self.seed, self.time_limit = seed, time_limit
        self.now = DAY_START
        self.rng = np.random.default_rng(seed + 12345)
        self.down = {m[0]: [] for m in MACHINES}
        self.rec = self.freed = self.moves = 0
        self.cases = {}
        raw = generate_day(seed, n_orders)
        for f in raw:
            self._add(f)
        self._set_plan_durations(list(self.cases.values()))
        self.script = make_script(seed, n_orders) if disruptions else []
        self.last_backend = ""
        self._initial_plan()

    # ---- setup -----------------------------------------------------------------------------------
    def _add(self, f):
        self.cases[f["id"]] = Case(f=f, id=f["id"], priority=f["priority"], modality=f["modality"], true_dur=f["true_duration"],
                                   will_no_show=f["will_no_show"], win=f["window"], wait_days=f["wait_days"])

    def _set_plan_durations(self, cases):
        if self.cfg["durations"] == "ml":
            pr = get_predictor()
            rows = [c.f for c in cases]
            for c, (mean, p80), ns in zip(cases, pr.predict_duration(rows), pr.predict_no_show(rows)):
                c.plan_min, c.ns_pred = p80, ns
        else:
            for c in cases:
                c.plan_min = FALLBACK_MEAN[c.modality]

    # ---- problem construction --------------------------------------------------------------------
    def _job(self, c: Case, recover=False) -> Job:
        earliest = max(to_slot(self.now), to_slot(c.win[0]))
        latest = min(HORIZON, to_slot(c.win[1], up=False))
        if recover:
            earliest = max(earliest, to_slot(self.now + LEAD))
            latest = min(latest, REG_END_SLOT)
        return Job(id=c.id, modality=c.modality, priority=c.priority, duration=dur_slots(c.plan_min), earliest=earliest,
                   latest_end=latest, wait_days=c.wait_days, displaced=c.displaced, no_show_prob=c.ns_pred if self.cfg["durations"] == "ml" else 0.0,
                   prev_start=to_slot(c.start, up=False) if c.start is not None and c.status == "sch" else None,
                   prev_resource=c.res if c.status == "sch" else None)

    def _fixed(self, c: Case) -> Fixed:
        s = to_slot(c.start, up=False)
        e = s + dur_slots(c.plan_min)
        if c.status == "run":
            e = max(e, to_slot(self.now) + 1)
        return Fixed(c.res, c.tech, s, e, c.id)

    def _problem(self, jobs, fixed_cases) -> Problem:
        machines = [Machine(i, mod, n, [(to_slot(a, up=False), to_slot(b)) for a, b in self.down[i]]) for i, mod, n in MACHINES]
        techs = [Tech(i, set(c), sh) for i, c, sh in TECHS]
        return Problem(jobs, machines, techs, [self._fixed(c) for c in fixed_cases], time_limit=self.time_limit, workers=1,
                       reg_end=REG_END_SLOT)

    def _solve(self, p, order=None, big=False):
        if big:
            p.time_limit *= 5
        r = solve(p, backend=self.backend, order=order or self.cfg["order"], sticky=self.cfg["sticky"])
        self.last_backend = r.backend
        return r

    # ---- planning --------------------------------------------------------------------------------
    def _initial_plan(self):
        jobs = [self._job(c) for c in self.cases.values()]
        r = self._solve(self._problem(jobs, []), big=True)
        for c in self.cases.values():
            a = r.assignments.get(c.id)
            if a:
                c.status, c.res, c.tech, c.start, c.s0 = "sch", a.resource_id, a.tech_id, to_min(a.start), to_min(a.start)
            else:
                c.status = "wait"
        self.moves = 0

    def _apply(self, r, cases, recovering=False):
        for c in cases:
            a = r.assignments.get(c.id)
            if a:
                new = to_min(a.start)
                if recovering:
                    c.status, c.recovered, c.s0 = "sch", True, new
                    self.rec += 1
                elif c.start is not None and (new != c.start or a.resource_id != c.res):
                    self.moves += 1
                    if new > c.start:
                        c.displaced += 1
                if c.s0 is None:
                    c.s0 = new
                c.res, c.tech, c.start, c.status = a.resource_id, a.tech_id, new, "sch"
            elif not recovering:
                if c.status == "sch":
                    c.displaced += 1
                    self.moves += 1
                c.status, c.res, c.tech, c.start = "wait", None, None, None

    def replan(self):
        frozen = [c for c in self.cases.values() if c.status == "sch" and self.now <= c.start < self.now + FREEZE]
        flex = [c for c in self.cases.values() if (c.status == "sch" and c not in frozen) or c.status == "new"]
        fixed = [c for c in self.cases.values() if c.status == "run"] + frozen
        r = self._solve(self._problem([self._job(c) for c in flex], fixed))
        self._apply(r, flex)

    def recover(self):
        cand = [c for c in self.cases.values() if c.status == "wait"]
        if not cand:
            return
        fixed = [c for c in self.cases.values() if c.status in ("sch", "run")]
        r = self._solve(self._problem([self._job(c, recover=True) for c in cand], fixed), order="priority")
        self._apply(r, cand, recovering=True)

    def _react(self, ev):
        if ev:
            if self.cfg["reopt"]:
                self.replan()
            if self.cfg["recover"]:
                self.recover()

    # ---- events ----------------------------------------------------------------------------------
    def _fire(self, e) -> bool:
        if e["k"] == "cx":
            c = self.cases.get(e["id"])
            if c and c.status == "sch":
                c.status = "cx"
                self.freed += 1
                return True
            return False
        if e["k"] == "down":
            self.down[e["m"]].append((self.now, self.now + e["len"]))
            return True
        if e["k"] == "stat":
            f = stat_case(self.rng, 1000 + len(self.cases), e["mod"])
            self._add(f)
            c = self.cases[f["id"]]
            self._set_plan_durations([c])
            c.arr = self.now
            if self.cfg["reopt"]:
                self.replan()
            else:                                    # FCFS: append to the end of the queue, nothing else moves
                fixed = [x for x in self.cases.values() if x.status in ("sch", "run")]
                last = max([to_slot(x.start, up=False) + dur_slots(x.plan_min) for x in fixed if x.modality == c.modality] + [to_slot(self.now)])
                j = self._job(c)
                j.earliest = max(j.earliest, last)
                r = self._solve(self._problem([j], fixed), order="fcfs")
                self._apply(r, [c])
            c.s0 = c.start
            return bool(self.cfg["recover"])
        return False

    # ---- clock -----------------------------------------------------------------------------------
    def step(self) -> bool:
        self.now += 5
        ev = False
        while self.script and self.script[0]["t"] <= self.now:
            ev |= self._fire(self.script.pop(0))
        for c in self.cases.values():
            if c.status == "run" and self.now >= c.as_ + c.true_dur:
                c.status, c.ae = "done", self.now
                pe = c.start + c.plan_min
                if self.now < pe - 15:
                    self.freed += 1
                    ev = True
                elif self.now > pe + 10:
                    ev = True
        busy_t = {c.tech for c in self.cases.values() if c.status == "run"}
        for mid, _, _ in MACHINES:
            if any(a <= self.now < b for a, b in self.down[mid]) or any(c.status == "run" and c.res == mid for c in self.cases.values()):
                continue
            q = sorted((c for c in self.cases.values() if c.status == "sch" and c.res == mid), key=lambda c: c.start)
            if not q or q[0].start > self.now:
                continue
            c = q[0]
            if c.will_no_show:
                if self.now >= c.start + 10:
                    c.status = "ns"
                    self.freed += 1
                    ev = True
            elif c.tech not in busy_t:
                c.status, c.as_, c.start = "run", self.now, self.now
                busy_t.add(c.tech)
        if ev:
            self._react(ev)
        elif self.cfg["recover"] and self.now % 15 == 0:   # periodic sweep: capacity also appears as time passes
            self.recover()
        return self.now < DAY_END + 90

    def run(self):
        while self.step():
            pass
        return self.metrics()

    # ---- metrics ---------------------------------------------------------------------------------
    def metrics(self) -> dict:
        done = [c for c in self.cases.values() if c.status == "done"]
        reg = [c for c in done if c.arr is None and not c.recovered and c.s0 is not None]
        stat_all = [c for c in self.cases.values() if c.arr is not None]
        end = DAY_END + 90
        mean = lambda a: float(np.mean(a)) if a else 0.0
        ot = sum(max(0, max([DAY_END] + [c.ae for c in done if c.res == m[0]]) - DAY_END) for m in MACHINES)
        used = sum(c.true_dur for c in done)
        disp = [c.displaced for c in self.cases.values()]
        return dict(served=len(done), avg_delay=mean([max(0, c.as_ - c.s0) for c in reg]),
                    max_delay=max([max(0, c.as_ - c.s0) for c in reg] + [0]), stat_wait=mean([(c.as_ if c.status == 'done' else end) - c.arr for c in stat_all]),  # unserved STAT counted as waiting until close
                    
                    overtime=ot, utilization=100 * used / (3 * (DAY_END - DAY_START)), recovered=self.rec, freed=self.freed,
                    fill_rate=100 * min(1, self.rec / self.freed) if self.freed else 0.0, moves=self.moves,
                    max_displaced=max(disp + [0]), mean_displaced=mean(disp),
                    waitlist_left=sum(c.status == "wait" for c in self.cases.values()))


def run_day(seed: int, strategy: str, **kw) -> dict:
    s = DaySim(seed, strategy, **kw)
    m = s.run()
    m["backend"] = s.last_backend
    return m
