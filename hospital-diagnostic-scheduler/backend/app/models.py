"""13 tables (merged from the original 17: test_history -> appointments actuals, queue/schedule events -> operational_events,
rooms -> resources.room, notifications deferred)."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20))            # admin|scheduler|doctor|technician|viewer
    full_name: Mapped[str] = mapped_column(String(120), default="")


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    mrn: Mapped[str] = mapped_column(String(32), unique=True, index=True)   # pseudonymous in demo
    name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int] = mapped_column(Integer)
    prior_no_shows: Mapped[int] = mapped_column(Integer, default=0)
    distance_km: Mapped[float] = mapped_column(Float, default=5.0)


class Test(Base):
    __test__ = False   # keep pytest from collecting this model
    __tablename__ = "tests"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    modality: Mapped[str] = mapped_column(String(10))        # MRI|CT
    base_minutes: Mapped[int] = mapped_column(Integer)


class Resource(Base):
    """A scanner. One machine per room in the MVP, so the room is a column rather than a table."""
    __tablename__ = "resources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    modality: Mapped[str] = mapped_column(String(10))
    room: Mapped[str] = mapped_column(String(40), default="")
    unavailable: Mapped[list] = mapped_column(JSON, default=list)   # [[start_min, end_min], ...] for the active day


class Technician(Base):
    __tablename__ = "technicians"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    certifications: Mapped[list] = mapped_column(JSON, default=list)  # ["MRI","CT"]


class StaffAvailability(Base):
    __tablename__ = "staff_availability"
    id: Mapped[int] = mapped_column(primary_key=True)
    technician_id: Mapped[int] = mapped_column(ForeignKey("technicians.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    start_min: Mapped[int] = mapped_column(Integer)
    end_min: Mapped[int] = mapped_column(Integer)


class TestOrder(Base):
    __test__ = False
    """Created by an authorised clinician. The system never decides whether the test is needed - only when/where."""
    __tablename__ = "test_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"))
    ordered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=2)       # 0 STAT, 1 Urgent, 2 Routine - set by clinician
    contrast: Mapped[bool] = mapped_column(Boolean, default=False)
    sedation: Mapped[bool] = mapped_column(Boolean, default=False)
    inpatient: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|scheduled|waitlisted|completed|cancelled|no_show
    day: Mapped[date] = mapped_column(Date, index=True)
    window_start_min: Mapped[int] = mapped_column(Integer, default=480)
    window_end_min: Mapped[int] = mapped_column(Integer, default=1050)
    prereq_ready_min: Mapped[int] = mapped_column(Integer, default=0)   # e.g. creatinine result expected at this minute
    lead_days: Mapped[int] = mapped_column(Integer, default=0)
    sms_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    wait_days: Mapped[int] = mapped_column(Integer, default=0)
    displaced_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    sim_true_duration: Mapped[float | None] = mapped_column(Float, nullable=True)   # DEMO ONLY: hidden ground truth
    sim_no_show: Mapped[bool | None] = mapped_column(Boolean, nullable=True)        # DEMO ONLY
    patient = relationship("Patient")
    test = relationship("Test")


class Appointment(Base):
    """Lifecycle row; actual_* columns double as the training history (replaces test_history)."""
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("test_orders.id"), index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    technician_id: Mapped[int | None] = mapped_column(ForeignKey("technicians.id"), nullable=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    start_min: Mapped[int] = mapped_column(Integer)
    planned_end_min: Mapped[int] = mapped_column(Integer)         # includes turnover
    planned_minutes: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)  # scheduled|in_progress|completed|cancelled|no_show|displaced
    source: Mapped[str] = mapped_column(String(20), default="initial")               # initial|insert|reopt|recovery|stat
    first_start_min: Mapped[int] = mapped_column(Integer, default=0)
    moves: Mapped[int] = mapped_column(Integer, default=0)
    recovered: Mapped[bool] = mapped_column(Boolean, default=False)
    actual_start_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_end_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order = relationship("TestOrder")
    resource = relationship("Resource")


class WaitlistEntry(Base):
    __tablename__ = "waitlist"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("test_orders.id"), unique=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    windows: Mapped[list] = mapped_column(JSON, default=list)        # patient availability [[start,end],...]
    short_notice_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(12), default="waiting")   # waiting|recovered|removed
    order = relationship("TestOrder")


class OperationalEvent(Base):
    __tablename__ = "operational_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True)  # cancellation|no_show|delay|early_completion|stat_order|machine_down|machine_up|staff_unavailable
    day: Mapped[date] = mapped_column(Date, index=True)
    at_min: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    appointment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("test_orders.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))               # duration|no_show
    value: Mapped[float] = mapped_column(Float)
    p80: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    mode: Mapped[str] = mapped_column(String(16))               # initial|insert|reopt|recover
    trigger: Mapped[str] = mapped_column(String(40), default="")
    trigger_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    backend: Mapped[str] = mapped_column(String(24), default="")
    status: Mapped[str] = mapped_column(String(16), default="")
    stages: Mapped[dict] = mapped_column(JSON, default=dict)   # lexicographic stage optima
    explain: Mapped[dict] = mapped_column(JSON, default=dict)  # order_id -> {summary, details}
    solve_ms: Mapped[int] = mapped_column(Integer, default=0)
    n_scheduled: Mapped[int] = mapped_column(Integer, default=0)
    n_unscheduled: Mapped[int] = mapped_column(Integer, default=0)
    n_moved: Mapped[int] = mapped_column(Integer, default=0)
    n_recovered: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime, default=_now)
