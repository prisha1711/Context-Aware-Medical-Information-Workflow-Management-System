"""
models/blood_test.py
Two tables:
  BloodTestRecord  — one row per test order
  BloodTestResult  — one row per analyte measured in that order

ML trigger condition:
  All expected analytes for the ordered test panel have been entered
  (count of BloodTestResult rows == expected analyte count for the panel)

ML target (from label_rules.py): haematological_abnormality_pattern (binary)
"""
from datetime import datetime
from sqlalchemy import String, Boolean, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

TEST_PANELS = ["CBC", "LFT", "KFT", "Lipid", "Thyroid"]
PRIORITIES = ["Routine", "Urgent"]
STATUSES_RECORD = ["ORDERED", "SAMPLE_COLLECTED", "IN_PROGRESS", "RESULTED", "CANCELLED"]
FLAG_TYPES = ["LOW", "HIGH", "CRITICAL_LOW", "CRITICAL_HIGH"]

# Expected analyte count per panel — used for trigger condition check
PANEL_ANALYTE_COUNTS: dict[str, int] = {
    "CBC": 9,
    "LFT": 7,
    "KFT": 5,
    "Lipid": 5,
    "Thyroid": 3,
}


class BloodTestRecord(Base):
    __tablename__ = "blood_test_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    ordered_by: Mapped[int | None] = mapped_column(
        ForeignKey("staff.id"), nullable=True
    )

    test_panel: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="Routine")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ORDERED")

    # Synthetic ML label (stored per record for CBC panel only; None for other panels)
    haematological_abnormality_pattern: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )

    ordered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resulted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient", back_populates="blood_test_records"
    )
    ordered_by_staff: Mapped["Staff | None"] = relationship(
        "Staff", back_populates="blood_tests_ordered"
    )
    results: Mapped[list["BloodTestResult"]] = relationship(
        "BloodTestResult", back_populates="blood_test_record", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<BloodTestRecord id={self.id} patient={self.patient_id} "
            f"panel={self.test_panel!r} status={self.status!r}>"
        )


class BloodTestResult(Base):
    """One row per analyte measured in a BloodTestRecord."""
    __tablename__ = "blood_test_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    blood_test_id: Mapped[int] = mapped_column(
        ForeignKey("blood_test_records.id"), nullable=False, index=True
    )

    analyte_name: Mapped[str] = mapped_column(String(80), nullable=False)
    result_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    flag_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    blood_test_record: Mapped["BloodTestRecord"] = relationship(
        "BloodTestRecord", back_populates="results"
    )

    def __repr__(self) -> str:
        return (
            f"<BloodTestResult id={self.id} test={self.blood_test_id} "
            f"analyte={self.analyte_name!r} value={self.result_value}>"
        )
