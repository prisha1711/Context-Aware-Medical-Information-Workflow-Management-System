"""
tests/conftest.py
Shared pytest fixtures for all test modules.

Uses an in-memory SQLite database — the real hospital.db is never touched by tests.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403 — ensures all tables are registered

TEST_DATABASE_URL = "sqlite:///:memory:"

_test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


def override_get_db():
    """Replace the real DB session with the in-memory test DB."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables once for the entire test session."""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture(scope="function")
def db():
    """Yield a test DB session, rollback after each test to keep tests isolated."""
    connection = _test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient with the real DB swapped for the in-memory test DB."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def demo_admin_user(db):
    """Create a demo admin user in the test DB and return (username, password)."""
    from app.models.user import User
    from app.services.auth_service import hash_password

    user = User(
        username="test_admin",
        email="test_admin@hospital.local",
        hashed_password=hash_password("Admin@123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, "Admin@123"


@pytest.fixture
def demo_doctor_user(db):
    """Create a demo doctor user in the test DB."""
    from app.models.user import User
    from app.services.auth_service import hash_password

    user = User(
        username="test_doctor",
        email="test_doctor@hospital.local",
        hashed_password=hash_password("Doctor@123"),
        role="doctor",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, "Doctor@123"


@pytest.fixture
def demo_patient_user(db):
    """Create a demo patient user linked to a patient record."""
    from app.models.patient import Patient
    from app.models.user import User
    from app.services.auth_service import hash_password
    import datetime

    p = Patient(
        rfid_tag_id="RFID-TESTTEST",
        full_name="Test Patient",
        gender="M",
        date_of_birth=datetime.date(1990, 1, 1),
        is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    user = User(
        username="test_patient",
        email="test_patient@hospital.local",
        hashed_password=hash_password("Patient@123"),
        role="patient",
        linked_patient_id=p.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, "Patient@123", p
