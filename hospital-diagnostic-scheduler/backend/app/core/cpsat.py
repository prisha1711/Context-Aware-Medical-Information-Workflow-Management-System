"""OR-Tools CP-SAT model: multi-resource diagnostic scheduling with lexicographic objectives.

Decision per job: scheduled or not, start slot, machine, technician.
Hard constraints
  H1 machine modality matches job modality
  H2 one case at a time per machine (NoOverlap incl. running/frozen cases and downtime)
  H3 one case at a time per technician (NoOverlap incl. committed work)
  H4 technician holds the required certification and the case lies inside the technician's shift
  H5 case lies inside the patient window / prerequisite-ready time / horizon
Objective stages (each stage is optimised, then its optimum is locked before the next one):
  1. unscheduled value        (tier value + fairness credit; tiers can never be traded off)
  2. maximum patient wait
  3. weighted total wait
  4. overtime
  5. disruption               (jobs that lose their previous slot/machine)
"""
import time

from .types import Assignment, Problem, Result


def solve_cpsat(p: Problem) -> Result:
    from ortools.sat.python import cp_model  # imported lazily so the rest of the code runs without OR-Tools

    t0 = time.time()
    m = cp_model.CpModel()
    H = p.horizon
    mach_iv = {mc.id: [] for mc in p.machines}
    tech_iv = {k.id: [] for k in p.techs}

    for f in p.fixed:
        size = f.end - f.start
        if size <= 0:
            continue
        if f.resource_id in mach_iv:
            mach_iv[f.resource_id].append(m.NewFixedSizeIntervalVar(f.start, size, f"fx_m_{f.job_id}"))
        if f.tech_id in tech_iv:
            tech_iv[f.tech_id].append(m.NewFixedSizeIntervalVar(f.start, size, f"fx_t_{f.job_id}"))
    for mc in p.machines:
        for a, b in mc.down:
            if b > a:
                mach_iv[mc.id].append(m.NewFixedSizeIntervalVar(a, b - a, f"down_{mc.id}_{a}"))

    V = {}
    forced_out = []
    for j in p.jobs:
        lo, hi = max(0, j.earliest), min(H, j.latest_end) - j.duration
        mach = [mc for mc in p.machines if mc.modality == j.modality]
        need = j.cert or j.modality
        techs = [k for k in p.techs if need in k.certs and k.shift[0] <= hi and k.shift[1] >= lo + j.duration]
        if hi < lo or not mach or not techs:
            forced_out.append(j.id)
            continue
        start = m.NewIntVar(lo, hi, f"s{j.id}")
        pres = m.NewBoolVar(f"p{j.id}")
        mv, tv = {}, {}
        for mc in mach:
            b = m.NewBoolVar(f"m{j.id}_{mc.id}")
            mach_iv[mc.id].append(m.NewOptionalIntervalVar(start, j.duration, start + j.duration, b, f"mi{j.id}_{mc.id}"))
            mv[mc.id] = b
        for k in techs:
            b = m.NewBoolVar(f"t{j.id}_{k.id}")
            tech_iv[k.id].append(m.NewOptionalIntervalVar(start, j.duration, start + j.duration, b, f"ti{j.id}_{k.id}"))
            m.Add(start >= k.shift[0]).OnlyEnforceIf(b)
            m.Add(start + j.duration <= k.shift[1]).OnlyEnforceIf(b)
            tv[k.id] = b
        m.Add(sum(mv.values()) == pres)
        m.Add(sum(tv.values()) == pres)
        if j.prev_start is not None and lo <= j.prev_start <= hi:
            m.AddHint(start, j.prev_start)
        V[j.id] = dict(job=j, start=start, pres=pres, mv=mv, tv=tv)

    for ivs in list(mach_iv.values()) + list(tech_iv.values()):
        if len(ivs) > 1:
            m.AddNoOverlap(ivs)

    w = p.weights
    unsched, maxw, tot_wait, tot_ot, disrupt = [], m.NewIntVar(0, H, "maxwait"), [], [], []
    for jid, v in V.items():
        j, s, pres = v["job"], v["start"], v["pres"]
        unsched.append(w.value(j) * (1 - pres))
        wait = s - max(0, j.earliest)
        m.Add(maxw >= wait).OnlyEnforceIf(pres)
        tot_wait.append(w.wait_mult[j.priority] * wait)
        ot = m.NewIntVar(0, H, f"ot{jid}")
        m.Add(ot >= s + j.duration - p.reg_end).OnlyEnforceIf(pres)
        tot_ot.append(ot)
        if j.prev_start is not None and j.prev_resource is not None:
            same_s = m.NewBoolVar(f"ss{jid}")
            m.Add(s == j.prev_start).OnlyEnforceIf(same_s)
            m.Add(s != j.prev_start).OnlyEnforceIf(same_s.Not())
            same_r = v["mv"].get(j.prev_resource)
            kept = m.NewBoolVar(f"kept{jid}")
            if same_r is None:
                m.Add(kept == 0)
            else:
                m.AddBoolAnd([same_s, same_r]).OnlyEnforceIf(kept)
                m.AddBoolOr([same_s.Not(), same_r.Not()]).OnlyEnforceIf(kept.Not())
            m.Add(kept <= pres)
            disrupt.append(pres - kept)
    forced_cost = sum(w.value(next(j for j in p.jobs if j.id == i)) for i in forced_out)

    stages = [("unscheduled_value", sum(unsched) if unsched else 0), ("max_wait", maxw),
              ("weighted_wait", sum(tot_wait) if tot_wait else 0), ("overtime", sum(tot_ot) if tot_ot else 0),
              ("disruption", sum(disrupt) if disrupt else 0)]
    res = Result(backend="cpsat", unscheduled=list(forced_out))
    if not V:
        res.status, res.solve_ms = "OPTIMAL", int((time.time() - t0) * 1000)
        return res

    per_stage = max(0.2, p.time_limit / len(stages))
    solver, last_ok, status_name = None, None, "UNKNOWN"
    for name, expr in stages:
        if isinstance(expr, int):                # empty objective term (e.g. nothing to disrupt): nothing to optimise or lock
            res.stages[name] = 0
            continue
        m.Minimize(expr)
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = per_stage
        s.parameters.num_workers = p.workers
        s.parameters.random_seed = 7
        st = s.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            status_name = s.StatusName(st) if last_ok is None else status_name
            break
        val = int(round(s.ObjectiveValue()))
        res.stages[name] = val + (forced_cost if name == "unscheduled_value" else 0)
        m.Add(expr <= val)                       # lock this stage's optimum
        last_ok, solver, status_name = s, s, s.StatusName(st)
    if last_ok is None:
        res.status = status_name
        res.unscheduled = [j.id for j in p.jobs]
        res.solve_ms = int((time.time() - t0) * 1000)
        return res

    for jid, v in V.items():
        if not solver.BooleanValue(v["pres"]):
            res.unscheduled.append(jid)
            continue
        mid = next(i for i, b in v["mv"].items() if solver.BooleanValue(b))
        kid = next(i for i, b in v["tv"].items() if solver.BooleanValue(b))
        st = solver.Value(v["start"])
        res.assignments[jid] = Assignment(jid, mid, kid, st, st + v["job"].duration)
    res.status = status_name
    res.solve_ms = int((time.time() - t0) * 1000)
    return res
