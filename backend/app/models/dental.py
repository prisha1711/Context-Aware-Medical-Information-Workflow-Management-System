"""
models/dental.py
Dental records — one row per dental visit/procedure.

ML trigger condition:
  status == "COMPLETED"
  AND procedure_type, diagnosis, pain_score, treatment_notes, material_used are all non-null

ML target (from label_rules.py): treatment_escalation_risk (binary)
"""
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Float, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

PROCEDURE_TYPES = [
    "Extraction", "Filling", "Root Canal", "Crown", "Cleaning", "Implant", "Consultation"
]
TOOTH_TYPES = ["Incisor", "Canine", "Premolar", "Molar", "Wisdom"]
TOOTH_QUADRANTS = ["Upper-Left", "Upper-Right", "Lower-Left", "Lower-Right"]
DIAGNOSES = ["Caries", "Periodontitis", "Abscess", "Healthy", "Fracture", "Sensitivity"]
MATERIALS = ["Composite", "Amalgam", "Ceramic", "GIC", "None"]
STATUSES = ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "NO_SHOW"]


class DentalRecord(Base):
    __tablename__ = "dental_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    dentist_id: Mapped[int | None] = mapped_column(
        ForeignKey("staff.id"), nullable=True
    )

    procedure_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tooth_notation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tooth_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tooth_quadrant: Mapped[str | None] = mapped_column(String(30), nullable=True)

    pain_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0–10
    diagnosis: Mapped[str | None] = mapped_column(String(100), nullable=True)
    treatment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)          # INR

    # Number of dental visits this patient had at the time of this record (derived at generation)
    visit_count_at_time: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SCHEDULED")

    # Synthetic ML label
    treatment_escalation_risk: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    visit_date: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    next_appointment: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="dental_records")
    dentist: Mapped["Staff | None"] = relationship(
        "Staff", back_populates="dental_records"
    )

    def __repr__(self) -> str:
        return (
            f"<DentalRecord id={self.id} patient={self.patient_id} "
            f"procedure={self.procedure_type!r} status={self.status!r}>"
        )
