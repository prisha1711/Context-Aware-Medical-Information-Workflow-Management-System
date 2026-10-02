"""
models/user.py
Authentication table for all 7 roles:
  admin, doctor, nurse, lab_tech, radiologist, dentist, patient

Staff roles: linked_staff_id points to the staff table.
Patient role: linked_patient_id points to the patients table.
              linked_staff_id is NULL for patient-role users.
"""
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

VALID_ROLES = frozenset(
    {"admin", "doctor", "nurse", "lab_tech", "radiologist", "dentist", "patient"}
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)

    # One of: admin | doctor | nurse | lab_tech | radiologist | dentist | patient
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # Exactly one of these will be non-NULL depending on the role
    linked_staff_id: Mapped[int | None] = mapped_column(
        ForeignKey("staff.id"), nullable=True
    )
    linked_patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("patients.id"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    linked_staff: Mapped["Staff | None"] = relationship(
        "Staff", back_populates="user_account", foreign_keys=[linked_staff_id]
    )
    linked_patient: Mapped["Patient | None"] = relationship(
        "Patient", back_populates="user_account", foreign_keys=[linked_patient_id]
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"
