"""Rule-based explanations. CP-SAT does not explain itself, so we reconstruct *why* from the final plan.

Honest scope: these are engineered summaries of binding constraints (blockers, windows, tiers, stickiness),
not solver internals.
"""
from .timeutil import fmt, to_min
from .types import PRIORITY_NAMES, Problem, Result


def explain_job(p: Problem, r: Result, job_id: int, names: dict | None = None) -> dict:
    names = names or {}
    job = next((j for j in p.jobs if j.id == job_id), None)
    if job is None:
        return {"summary": "Job not part of this optimization run.", "details": []}
    tier = PRIORITY_NAMES[job.priority]
    mname = lambda i: names.get(i, f"machine {i}")
    d = []
    if job_id in r.assignments:
        a = r.assignments[job_id]
        d.append(f"{tier} case placed on {mname(a.resource_id)} at {fmt(to_min(a.start))}.")
        if a.start == job.earliest:
            d.append("Starts at the earliest time allowed by the patient window, prerequisites and notice lead.")
        else:
            blockers = []
            for m in p.machines:
                if m.modality != job.modality:
                    continue
                for o in r.assignments.values():
                    if o.job_id != job_id and o.resource_id == m.id and job.earliest < o.end and o.start < a.start:
                        oj = next((x for x in p.jobs if x.id == o.job_id), None)
                        blockers.append((oj.priority if oj else 9, f"{mname(m.id)} busy with #{o.job_id} until {fmt(to_min(o.end))}"))
                for f in p.fixed:
                    if f.resource_id == m.id and job.earliest < f.end and f.start < a.start:
                        blockers.append((-1, f"{mname(m.id)} committed until {fmt(to_min(f.end))}"))
                for s, e in m.down:
                    if job.earliest < e and s < a.start:
                        blockers.append((-1, f"{mname(m.id)} unavailable until {fmt(to_min(e))}"))
            if blockers:
                d.append("Earlier slots were blocked: " + "; ".join(sorted({b[1] for b in blockers})[:3]) + ".")
            else:
                d.append("Earlier slots were blocked by technician availability or shift limits.")
        if job.prev_start is not None:
            if job.prev_start == a.start and job.prev_resource == a.resource_id:
                d.append("Kept its previous slot to avoid unnecessary disruption.")
            else:
                d.append(f"Moved from {fmt(to_min(job.prev_start))}: its previous slot conflicted with a higher-priority or committed case.")
        d.append(f"Planned block {(a.end - a.start) * 5} min including turnover.")
        return {"summary": d[0], "details": d[1:]}
    reasons = []
    if not any(m.modality == job.modality for m in p.machines):
        reasons.append("no machine of this modality is available")
    if job.latest_end - job.earliest < job.duration:
        reasons.append("the patient window is shorter than the planned block")
    if not reasons:
        reasons.append("every feasible slot inside the patient window was taken by cases of equal or higher tier")
    return {"summary": f"{tier} case not scheduled in this run.", "details": ["Reason: " + "; ".join(reasons) + "."]}
