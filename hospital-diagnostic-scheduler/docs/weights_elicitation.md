# Getting the priorities and weights from SMCW (do not invent them)

`app/core/types.py::Weights` holds PLACEHOLDER numbers. Replace them with these steps.

1. **Fix the hierarchy (not weights).** Confirm with the department head, in writing, the order of tiers:
   hard constraints / STAT deadlines > urgent > routine, then max wait, total wait, overtime, disruption.
   This is the stage order in `cpsat.py`.
2. **Pairwise comparisons (AHP style)** with the head of radiology, senior technologist and scheduling staff, one session each:
   "Is a 10-minute cut in the longest wait worth more or less than a 10-minute cut in overtime?" for every pair of objectives within a tier.
   Compute weights from the comparison matrix and report the consistency ratio (accept < 0.1).
3. **Show outcomes, not numbers.** Run `python -m sim.benchmark` with 2-3 candidate weight sets and show the Pareto trade-off
   (utilization vs fairness vs overtime). Let them choose the schedule they prefer.
4. **Fairness parameters.** Ask how many displacements are acceptable for one patient (`fairness_per_displacement`, cap) and whether any
   clinical category must be protected (e.g. oncology follow-ups).
5. **Record and version** the decisions in this file with date and participants.

Open questions for SMCW: real slot lengths and turnover, contrast prerequisites (creatinine), sedation policy, how STAT is declared,
how many minutes of overtime are tolerable, how far in advance cancellations are usually known, data-sharing rules for de-identified history.
