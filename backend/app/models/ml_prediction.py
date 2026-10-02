"""
models/ml_prediction.py
Stores every ML prediction made by the system.

Key design points:
- disclaimer is ALWAYS stored (hardcoded constant from config.py)
- doctor_review_status tracks whether the doctor has acknowledged the prediction
- workflow_event_id links back to the ML_PREDICTION_READY workflow event
- input_features and prediction_output are stored as JSON strings for auditability
"""
from datetime import datetime
from sqlalchemy import String, Float, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

DOMAINS = frozenset({"radiology", "dental", "blood_test"})
REVIEW_STATUSES = frozenset({"PENDING", "ACKNOWLEDGED", "DISPUTED"})


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False, index=True
    )
    # FK to the ML_PREDICTION_READY workflow event that was created for this prediction
    workflow_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_events.id"), nullable=True
    )

    domain: Mapped[str] = mapped_column(String(20), nullable=False)    # radiology | dental | blood_test
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # JSON string: {"feature_name": value, ...}
    input_features: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON string: {"label": "...", "probability_positive": 0.77, "probability_negative": 0.23}
    prediction_output: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Mandatory disclaimer — always populated from settings.ML_DISCLAIMER
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)

    # Doctor review
    doctor_review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    doctor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    predicted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="ml_predictions")
    workflow_event: Mapped["WorkflowEvent | None"] = relationship(
        "WorkflowEvent", back_populates="ml_prediction"
    )

    def __repr__(self) -> str:
        return (
            f"<MLPrediction id={self.id} patient={self.patient_id} "
            f"domain={self.domain!r} review={self.doctor_review_status!r}>"
        )
