"""
models/department.py
Departments in the hospital (Radiology, Dental, Blood Lab, etc.)
"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    staff: Mapped[list["Staff"]] = relationship("Staff", back_populates="department")
    workflow_events: Mapped[list["WorkflowEvent"]] = relationship(
        "WorkflowEvent", back_populates="department"
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id} name={self.name!r}>"
