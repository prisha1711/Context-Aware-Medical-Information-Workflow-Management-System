from app.core.timeutil import HORIZON, REG_END_SLOT
from app.core.types import Fixed, Job, Machine, Problem, Tech


def small_problem(jobs, fixed=None, down=None, techs=None):
    machines = [Machine(1, "MRI", "MRI-1", down or []), Machine(2, "MRI", "MRI-2"), Machine(3, "CT", "CT-1")]
    techs = techs or [Tech(1, {"MRI", "CT"}, (0, HORIZON)), Tech(2, {"MRI"}, (0, HORIZON)), Tech(3, {"CT"}, (0, HORIZON))]
    return Problem(jobs, machines, techs, fixed or [], time_limit=2.0, workers=1, reg_end=REG_END_SLOT)


def check_hard_constraints(p: Problem, res):
    """Independent verifier used by every solver test: returns a list of violations."""
    bad = []
    by_id = {j.id: j for j in p.jobs}
    mach = {m.id: m for m in p.machines}
    tech = {t.id: t for t in p.techs}
    for a in res.assignments.values():
        j = by_id[a.job_id]
        if mach[a.resource_id].modality != j.modality:
            bad.append(f"modality {a}")
        if a.start < j.earliest or a.end > j.latest_end:
            bad.append(f"window {a}")
        if a.end - a.start != j.duration:
            bad.append(f"duration {a}")
        t = tech[a.tech_id]
        if (j.cert or j.modality) not in t.certs or a.start < t.shift[0] or a.end > t.shift[1]:
            bad.append(f"tech {a}")
        for s, e in mach[a.resource_id].down:
            if a.start < e and s < a.end:
                bad.append(f"down {a}")
    ivs = [(a.resource_id, a.tech_id, a.start, a.end, a.job_id) for a in res.assignments.values()]
    ivs += [(f.resource_id, f.tech_id, f.start, f.end, f"fx{f.job_id}") for f in p.fixed]
    for i, x in enumerate(ivs):
        for y in ivs[i + 1:]:
            if x[2] < y[3] and y[2] < x[3]:
                if x[0] == y[0]:
                    bad.append(f"machine overlap {x} {y}")
                if x[1] is not None and x[1] == y[1]:
                    bad.append(f"tech overlap {x} {y}")
    return bad
