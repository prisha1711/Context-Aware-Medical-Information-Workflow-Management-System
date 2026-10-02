"""
models/__init__.py
Import all models here so that:
  1. SQLAlchemy's Base.metadata knows about every table when create_all() is called.
  2. Relationship back-references can resolve across modules.
"""
from app.models.department import Department        # noqa: F401
from app.models.patient import Patient              # noqa: F401
from app.models.staff import Staff                  # noqa: F401
from app.models.user import User                    # noqa: F401
from app.models.workflow import WorkflowEvent       # noqa: F401
from app.models.radiology import RadiologyRecord    # noqa: F401
from app.models.dental import DentalRecord          # noqa: F401
from app.models.blood_test import (                 # noqa: F401
    BloodTestRecord,
    BloodTestResult,
)
from app.models.ml_prediction import MLPrediction   # noqa: F401
from app.models.audit_log import AuditLog           # noqa: F401

__all__ = [
    "Department",
    "Patient",
    "Staff",
    "User",
    "WorkflowEvent",
    "RadiologyRecord",
    "DentalRecord",
    "BloodTestRecord",
    "BloodTestResult",
    "MLPrediction",
    "AuditLog",
]
