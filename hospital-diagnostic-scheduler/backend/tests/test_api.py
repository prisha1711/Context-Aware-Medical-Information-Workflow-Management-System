import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.services.demo import seed_demo


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo(db, seed=5, n_orders=40, disruptions=False)
    with TestClient(app) as c:
        yield c


def login(client, user, pw):
    r = client.post("/auth/login", data={"username": user, "password": pw})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_auth_required(client):
    assert client.get("/schedule").status_code == 401


def test_bad_login(client):
    assert client.post("/auth/login", data={"username": "admin", "password": "nope"}).status_code == 401


def test_schedule_and_kpis(client):
    h = login(client, "viewer", "view123")
    s = client.get("/schedule", headers=h).json()
    assert len(s["appointments"]) > 10
    assert "served" in client.get("/kpis", headers=h).json()


def test_rbac_viewer_cannot_post_events(client):
    h = login(client, "viewer", "view123")
    assert client.post("/events", json={"type": "cancellation", "appointment_id": 1}, headers=h).status_code == 403


def test_cancellation_triggers_recovery_run(client):
    h = login(client, "scheduler", "sched123")
    appts = client.get("/schedule", headers=h).json()["appointments"]
    target = next(a for a in appts if a["status"] == "scheduled")
    waiting_before = len(client.get("/waitlist", headers=h).json())
    out = client.post("/events", json={"type": "cancellation", "appointment_id": target["id"]}, headers=h)
    assert out.status_code == 200
    assert len(client.get("/waitlist", headers=h).json()) <= waiting_before


def test_stat_order_is_scheduled_with_explanation(client):
    h = login(client, "doctor", "doc123")
    r = client.post("/orders", json={"patient_name": "Test STAT", "age": 40, "test_code": "CT_HEAD", "priority": 0}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "scheduled"
    assert r.json()["explanation"]["summary"]


def test_explain_endpoint(client):
    h = login(client, "viewer", "view123")
    a = next(a for a in client.get("/schedule", headers=h).json()["appointments"] if a["status"] == "scheduled")
    assert client.get(f"/appointments/{a['id']}/explain", headers=h).json()["explanation"]["summary"]


def test_advance_clock(client):
    h = login(client, "scheduler", "sched123")
    t0 = client.get("/demo/clock", headers=h).json()["now"]
    assert client.post("/demo/advance", json={"minutes": 30}, headers=h).json()["now"] == t0 + 30
