"""
models/patient.py
The central hub table. All medical records and workflow events reference this.

RFID tag format: RFID-XXXXXXXX (8-digit uppercase hex), e.g. RFID-4F3A91BC
"""
from datetime import date, datetime
from sqlalchemy import String, Boolean, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    rfid_tag_id: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)        # "M" or "F"
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    blood_group: Mapped[str | None] = mapped_column(String(5), nullable=True)
    contact_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user_account: Mapped["User | None"] = relationship(
        "User", back_populates="linked_patient", foreign_keys="User.linked_patient_id"
    )
    workflow_events: Mapped[list["WorkflowEvent"]] = relationship(
        "WorkflowEvent", back_populates="patient"
    )
    radiology_records: Mapped[list["RadiologyRecord"]] = relationship(
        "RadiologyRecord", back_populates="patient"
    )
    dental_records: Mapped[list["DentalRecord"]] = relationship(
        "DentalRecord", back_populates="patient"
    )
    blood_test_records: Mapped[list["BloodTestRecord"]] = relationship(
        "BloodTestRecord", back_populates="patient"
    )
    ml_predictions: Mapped[list["MLPrediction"]] = relationship(
        "MLPrediction", back_populates="patient"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="patient"
    )

    def __repr__(self) -> str:
        return f"<Patient id={self.id} name={self.full_name!r} rfid={self.rfid_tag_id!r}>"
