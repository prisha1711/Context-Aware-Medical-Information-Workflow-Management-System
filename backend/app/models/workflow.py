"""
models/workflow.py
WorkflowEvent — every step in a patient's hospital journey is recorded here.

Current patient status is always derived from the MOST RECENT event for that patient.
No separate status field is stored on the Patient record.

linked_record_id + linked_record_type allow an event to reference any domain record
or ML prediction, giving full traceability without storing mixed FKs.
"""
from datetime import datetime
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Allowed event types — used for validation in services
WORKFLOW_EVENT_TYPES = frozenset({
    "REGISTRATION",
    "TRIAGE",
    "CONSULTATION",
    "TEST_ORDER",
    "TEST_IN_PROGRESS",
    "RESULTS_ENTERED",
    "ML_PREDICTION_READY",
    "DOCTOR_REVIEW",
    "ML_PREDICTION_ACKNOWLEDGED",
    "TREATMENT_PLAN_UPDATED",
    "DISCHARGE",
    "TRANSFER",
})


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    staff_id: Mapped[int | None] = mapped_column(
        ForeignKey("staff.id"), nullable=True
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Generic reference to any linked domain record or ML prediction
    # e.g. linked_record_type="radiology", linked_record_id=17
    linked_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    linked_record_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    event_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="workflow_events")
    department: Mapped["Department | None"] = relationship(
        "Department", back_populates="workflow_events"
    )
    staff: Mapped["Staff | None"] = relationship("Staff", back_populates="workflow_events")
    ml_prediction: Mapped["MLPrediction | None"] = relationship(
        "MLPrediction", back_populates="workflow_event"
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowEvent id={self.id} patient={self.patient_id} "
            f"type={self.event_type!r} time={self.event_time}>"
        )
