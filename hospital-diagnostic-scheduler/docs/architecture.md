# Architecture

```
history / live data ──> ML predictions ──> CP-SAT optimizer ──> live schedule ──> event monitor ──> waitlist recovery
 (appointments table)   duration p80        feasible slots       appointments     cancel / no-show      CP-SAT in "recover" mode
                        no-show risk        + constraints                         delay / STAT / down          │
                                                  ▲                                     │                      │
                                                  └──────────── re-optimize ◄───────────┘ ◄────────────────────┘
```

## Principle: ML predicts, optimization decides
* `app/ml` only produces numbers (expected duration, 80th-percentile duration, no-show probability).
* `app/core` (pure Python, no framework) turns those numbers into a schedule under hard constraints.
* The solver schedules against the **p80 duration**, not the mean. Back-to-back packing on point estimates is exactly the
  fragility dynamic scheduling is meant to remove.

## Solver modes (`app/services/scheduling.py`)
| mode | when | free to move | fixed |
|---|---|---|---|
| initial | start of day / seed | everything | running cases |
| insert | new ROUTINE order | the newcomer only | all bookings (routine orders never displace booked patients) |
| reopt | STAT/urgent order, machine down, technician leaves, delay >= 10 min | unstarted bookings not starting in the next 15 min | running + frozen |
| recover | cancellation, no-show, early finish, periodic sweep | waitlisted orders | every booking |

Recovery is solved as a small optimization (which set of waitlisted patients best fills the gaps), not a first-come loop.

## Hard constraints (`app/core/cpsat.py`)
H1 modality match · H2 one case per machine (incl. running, frozen, downtime) · H3 one case per technician ·
H4 technician certification and shift · H5 patient window, prerequisite-ready time, horizon.

## Lexicographic objective (each stage's optimum is locked before the next)
1. unscheduled value (tier value + fairness credit; tiers cannot be traded off)
2. maximum patient wait  3. weighted total wait  4. overtime  5. disruption (moves away from the previous plan)

Weights are **placeholders** until SMCW supplies them: `docs/weights_elicitation.md`.

## Re-optimization cadence
Too often = thrashing, too rarely = stale. Rules: delays under 10 min are absorbed; appointments starting within 15 min are frozen;
routine inserts never trigger a full re-optimization; the recovery sweep runs every 15 simulated minutes.

## Explainability
CP-SAT does not explain itself. `app/core/explain.py` reconstructs reasons from the final plan (blocking cases, windows, tier,
stickiness) and stores them per run in `optimization_runs.explain`. Rule-based summaries, not solver internals.

## Data model (13 tables)
users, patients, tests, resources (room is a column), technicians, staff_availability, test_orders, appointments (actual_* columns are the
training history), waitlist, operational_events, predictions, optimization_runs, audit_logs. Notifications are deferred.

## Deliberately not used
Kubernetes, Kafka, LLM agents, digital twins, blockchain. Celery is not needed: a solve takes seconds and runs in FastAPI's thread pool.
Redis is optional and only fans WebSocket messages out across several API workers.
