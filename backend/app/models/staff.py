"""
models/staff.py
Hospital staff members (doctors, nurses, radiologists, dentists, lab techs).
Each staff member belongs to one department.
"""
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    # role mirrors the user role: doctor, nurse, radiologist, dentist, lab_tech
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    specialization: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    department: Mapped["Department | None"] = relationship(
        "Department", back_populates="staff"
    )
    user_account: Mapped["User | None"] = relationship(
        "User", back_populates="linked_staff", foreign_keys="User.linked_staff_id"
    )
    workflow_events: Mapped[list["WorkflowEvent"]] = relationship(
        "WorkflowEvent", back_populates="staff"
    )
    radiology_ordered: Mapped[list["RadiologyRecord"]] = relationship(
        "RadiologyRecord",
        back_populates="ordered_by_staff",
        foreign_keys="RadiologyRecord.ordered_by",
    )
    radiology_reviewed: Mapped[list["RadiologyRecord"]] = relationship(
        "RadiologyRecord",
        back_populates="reviewed_by_staff",
        foreign_keys="RadiologyRecord.reviewed_by",
    )
    dental_records: Mapped[list["DentalRecord"]] = relationship(
        "DentalRecord", back_populates="dentist"
    )
    blood_tests_ordered: Mapped[list["BloodTestRecord"]] = relationship(
        "BloodTestRecord", back_populates="ordered_by_staff"
    )

    def __repr__(self) -> str:
        return f"<Staff id={self.id} name={self.full_name!r} role={self.role!r}>"
