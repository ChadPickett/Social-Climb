import time

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app


def client(tmp_path, **overrides):
    return TestClient(create_app(Settings(db_path=str(tmp_path / "db.sqlite"), **overrides)))


def test_analyze_job_end_to_end(tmp_path):
    c = client(tmp_path)
    assert c.get("/").status_code == 200
    job_id = c.post("/api/analyze", json={"topic": "archaeology", "timezone": "UTC"}).json()["job_id"]
    for _ in range(100):
        job = c.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "done", job["error"]
    assert c.get("/api/reports").json()[0]["topic"] == "archaeology"


def test_missing_keys_surface_as_job_error(tmp_path):
    c = client(tmp_path, data_provider="apify")
    job_id = c.post("/api/analyze", json={"topic": "archaeology"}).json()["job_id"]
    for _ in range(100):
        job = c.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "error" and "APIFY_TOKEN" in job["error"]


def test_app_token_required_when_set(tmp_path):
    c = client(tmp_path, app_token="s3cret")
    assert c.get("/api/config").status_code == 401
    assert c.get("/api/config", headers={"X-App-Token": "s3cret"}).status_code == 200
