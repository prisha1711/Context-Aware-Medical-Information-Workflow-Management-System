"""Slot-recovery helpers: gap detection and waitlist ranking (the CP-SAT/greedy solver does the placement)."""
from .types import Problem


def find_gaps(p: Problem, from_slot: int, to_slot_: int, min_len: int = 4):
    """Free intervals per machine between from_slot and to_slot_, ignoring technician availability."""
    gaps = []
    for m in p.machines:
        busy = sorted([(a, b) for a, b in m.down] +
                      [(f.start, f.end) for f in p.fixed if f.resource_id == m.id])
        t = from_slot
        for a, b in busy:
            if a - t >= min_len:
                gaps.append((m.id, t, min(a, to_slot_)))
            t = max(t, b)
        if to_slot_ - t >= min_len:
            gaps.append((m.id, t, to_slot_))
    return [g for g in gaps if g[2] - g[1] >= min_len]


def rank_waitlist(jobs, weights):
    return sorted(jobs, key=weights.rank_key)
