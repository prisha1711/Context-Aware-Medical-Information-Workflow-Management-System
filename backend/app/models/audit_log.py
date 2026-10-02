"""
models/audit_log.py
Records every authenticated action — who accessed what data, when.
Important for healthcare compliance awareness in a real system.
"""
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("patients.id"), nullable=True, index=True
    )

    action: Mapped[str] = mapped_column(String(20), nullable=False)   # GET | POST | PATCH | DELETE
    resource: Mapped[str] = mapped_column(String(200), nullable=False) # e.g. "/api/v1/patients/42"
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv4/IPv6
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")
    patient: Mapped["Patient | None"] = relationship("Patient", back_populates="audit_logs")

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} user={self.user_id} "
            f"action={self.action!r} resource={self.resource!r}>"
        )
