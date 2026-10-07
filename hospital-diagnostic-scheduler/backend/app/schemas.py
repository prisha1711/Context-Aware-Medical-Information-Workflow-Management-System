from typing import Literal, Optional

from pydantic import BaseModel, Field


class OrderIn(BaseModel):
    patient_name: str
    age: int = Field(ge=0, le=120)
    test_code: str
    priority: int = Field(2, ge=0, le=2, description="0 STAT, 1 Urgent, 2 Routine - set by the ordering clinician")
    contrast: bool = False
    sedation: bool = False
    inpatient: bool = False
    window_start_min: int = 480
    window_end_min: int = 1050
    prereq_ready_min: int = 0


class EventIn(BaseModel):
    type: Literal["cancellation", "no_show", "delay", "early_completion", "machine_down", "machine_up", "staff_unavailable"]
    appointment_id: Optional[int] = None
    resource_id: Optional[int] = None
    technician_id: Optional[int] = None
    minutes: Optional[int] = None
    duration_min: Optional[int] = None


class StatIn(BaseModel):
    test_code: str


class SeedIn(BaseModel):
    seed: int = 7
    n_orders: int = Field(64, ge=5, le=200)
    disruptions: bool = True


class AdvanceIn(BaseModel):
    minutes: int = Field(15, ge=5, le=240)
