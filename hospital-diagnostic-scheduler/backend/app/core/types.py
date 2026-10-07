"""Framework-free problem/solution types shared by the optimizer, simulator and API services."""
from dataclasses import dataclass, field
from typing import Optional

from .timeutil import HORIZON

STAT, URGENT, ROUTINE = 0, 1, 2
PRIORITY_NAMES = {0: "STAT", 1: "Urgent", 2: "Routine"}


@dataclass
class Weights:
    """PLACEHOLDER values. Real values must come from SMCW (docs/weights_elicitation.md).

    Tiers are lexicographically separated: tier_value gaps are larger than the maximum fairness credit,
    so a lower tier can never outrank a higher one.  Everything else is only used inside a tier.
    """
    tier_value: dict = field(default_factory=lambda: {0: 10000, 1: 1000, 2: 100})
    fairness_per_wait_day: int = 1
    fairness_per_displacement: int = 3
    fairness_cap: int = 99
    no_show_penalty: int = 5          # tie-break only: prefers reliable candidates for recovered slots
    wait_mult: dict = field(default_factory=lambda: {0: 4, 1: 2, 2: 1})

    def value(self, job: "Job") -> int:
        credit = min(self.fairness_cap, self.fairness_per_wait_day * job.wait_days
                     + self.fairness_per_displacement * job.displaced)
        return self.tier_value[job.priority] + credit - int(self.no_show_penalty * job.no_show_prob)

    def rank_key(self, job: "Job"):
        """Waitlist ranking: tier, then fairness credit, then lower no-show risk."""
        return (job.priority, -(job.wait_days + 2 * job.displaced), job.no_show_prob, job.id)


@dataclass
class Job:
    id: int
    modality: str
    priority: int
    duration: int                       # slots, includes turnover
    earliest: int = 0                   # slot: patient window / prerequisites / notice lead
    latest_end: int = HORIZON           # slot
    wait_days: int = 0
    displaced: int = 0
    no_show_prob: float = 0.0
    prev_start: Optional[int] = None    # current plan (for disruption objective)
    prev_resource: Optional[int] = None
    cert: Optional[str] = None          # required technician certification, defaults to modality


@dataclass
class Machine:
    id: int
    modality: str
    name: str = ""
    down: list = field(default_factory=list)   # [(start_slot, end_slot)]


@dataclass
class Tech:
    id: int
    certs: set
    shift: tuple                                # (start_slot, end_slot)
    name: str = ""


@dataclass
class Fixed:
    """Capacity that is already committed (running case, frozen appointment, existing booking in recovery mode)."""
    resource_id: int
    tech_id: Optional[int]
    start: int
    end: int
    job_id: Optional[int] = None


@dataclass
class Problem:
    jobs: list
    machines: list
    techs: list
    fixed: list = field(default_factory=list)
    weights: Weights = field(default_factory=Weights)
    time_limit: float = 5.0
    workers: int = 4
    reg_end: int = 108                          # slot where overtime starts
    horizon: int = HORIZON


@dataclass
class Assignment:
    job_id: int
    resource_id: int
    tech_id: Optional[int]
    start: int
    end: int


@dataclass
class Result:
    assignments: dict = field(default_factory=dict)   # job_id -> Assignment
    unscheduled: list = field(default_factory=list)
    status: str = "UNKNOWN"
    backend: str = ""
    stages: dict = field(default_factory=dict)        # lexicographic stage -> optimal value
    solve_ms: int = 0
