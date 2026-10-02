"""
models/radiology.py
Radiology records — one row per scan ordered for a patient.

ML trigger condition:
  status == "COMPLETED" AND findings IS NOT NULL AND impression IS NOT NULL

ML target (from label_rules.py): requires_radiologist_followup (binary)
"""
from datetime import datetime
from sqlalchemy import String, Boolean, Float, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Allowed values — referenced in services and data generator
SCAN_TYPES = ["X-Ray", "CT", "MRI", "Ultrasound"]
BODY_PARTS = ["Chest", "Abdomen", "Brain", "Spine", "Knee", "Hip", "Pelvis", "Neck"]
INDICATIONS = [
    "Trauma", "Infection", "Tumour Screening", "Chronic Disease", "Routine", "Pre-operative"
]
PRIORITIES = ["Routine", "Urgent", "STAT"]
STATUSES = ["ORDERED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]


class RadiologyRecord(Base):
    __tablename__ = "radiology_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    ordered_by: Mapped[int | None] = mapped_column(
        ForeignKey("staff.id"), nullable=True
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("staff.id"), nullable=True
    )

    scan_type: Mapped[str] = mapped_column(String(50), nullable=False)
    body_part: Mapped[str] = mapped_column(String(80), nullable=False)
    indication: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="Routine")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ORDERED")

    # Clinical data (populated when completed)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    impression: Mapped[str | None] = mapped_column(Text, nullable=True)
    radiation_dose_mgy: Mapped[float | None] = mapped_column(Float, nullable=True)
    contrast_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scan_duration_min: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Synthetic ML label (stored during data generation; used for model training)
    requires_radiologist_followup: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )

    ordered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient", back_populates="radiology_records"
    )
    ordered_by_staff: Mapped["Staff | None"] = relationship(
        "Staff", back_populates="radiology_ordered", foreign_keys=[ordered_by]
    )
    reviewed_by_staff: Mapped["Staff | None"] = relationship(
        "Staff", back_populates="radiology_reviewed", foreign_keys=[reviewed_by]
    )

    def __repr__(self) -> str:
        return (
            f"<RadiologyRecord id={self.id} patient={self.patient_id} "
            f"scan={self.scan_type!r} status={self.status!r}>"
        )
