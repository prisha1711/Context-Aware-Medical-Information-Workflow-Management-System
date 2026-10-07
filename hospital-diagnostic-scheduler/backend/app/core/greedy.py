"""Pure-Python earliest-feasible scheduler.

Used for (a) the FCFS / priority baselines, and (b) as a fallback when OR-Tools is not installed.
It honours the same hard constraints as the CP-SAT model: machine modality, one case per machine,
one case per technician, technician certification and shift, machine downtime, patient window, horizon.
"""
import time

from .types import Assignment, Problem, Result


def _busy(p: Problem):
    mb = {m.id: list(m.down) for m in p.machines}
    tb = {k.id: [] for k in p.techs}
    for f in p.fixed:
        mb.setdefault(f.resource_id, []).append((f.start, f.end))
        if f.tech_id is not None:
            tb.setdefault(f.tech_id, []).append((f.start, f.end))
    return mb, tb


def _free(busy, t, e):
    return all(e <= a or t >= b for a, b in busy)


def _tech_for(p, job, tb, t, e):
    need = job.cert or job.modality
    for k in p.techs:
        if need in k.certs and k.shift[0] <= t and e <= k.shift[1] and _free(tb[k.id], t, e):
            return k.id
    return None


def _earliest(p, job, mb, tb, lb):
    """Earliest (start, machine, tech) over compatible machines, or None."""
    best = None
    need = job.cert or job.modality
    techs = [k for k in p.techs if need in k.certs]
    for m in p.machines:
        if m.modality != job.modality:
            continue
        cands = {lb}
        cands.update(b for _, b in mb[m.id] if b > lb)
        for k in techs:
            cands.update(b for _, b in tb[k.id] if b > lb)
            cands.add(max(lb, k.shift[0]))
        for t in sorted(cands):
            e = t + job.duration
            if e > job.latest_end:
                break
            if best is not None and t >= best[0]:
                break
            if _free(mb[m.id], t, e):
                kid = _tech_for(p, job, tb, t, e)
                if kid is not None:
                    best = (t, m.id, kid)
                    break
    return best


def solve_greedy(p: Problem, order: str = "priority", sticky: bool = False) -> Result:
    t0 = time.time()
    mb, tb = _busy(p)
    w = p.weights
    if order == "fcfs":
        jobs = sorted(p.jobs, key=lambda j: j.id)
    else:
        jobs = sorted(p.jobs, key=lambda j: (j.priority, -(j.wait_days + 2 * j.displaced),
                                             j.prev_start if j.prev_start is not None else 10 ** 4, j.id))
    res = Result(status="FEASIBLE", backend="greedy-sticky" if sticky else "greedy")
    for j in jobs:
        lb = max(0, j.earliest)
        pick = None
        if sticky and j.prev_start is not None and j.prev_resource is not None and j.prev_start >= lb:
            t, e = j.prev_start, j.prev_start + j.duration
            if e <= j.latest_end and _free(mb[j.prev_resource], t, e):
                kid = _tech_for(p, j, tb, t, e)
                if kid is not None:
                    pick = (t, j.prev_resource, kid)
        if pick is None:
            pick = _earliest(p, j, mb, tb, lb)
        if pick is None:
            res.unscheduled.append(j.id)
            continue
        t, mid, kid = pick
        e = t + j.duration
        mb[mid].append((t, e))
        tb[kid].append((t, e))
        res.assignments[j.id] = Assignment(j.id, mid, kid, t, e)
    res.solve_ms = int((time.time() - t0) * 1000)
    return res
