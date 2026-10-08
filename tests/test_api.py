import json
import time

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app

PHONE = ("192.168.1.50", 5000)
PC = ("127.0.0.1", 5000)


def client(tmp_path, host=PC, **overrides):
    app = create_app(Settings(db_path=str(tmp_path / "db.sqlite"), **overrides))
    return TestClient(app, client=host)


def wait(c, job_id):
    for _ in range(100):
        job = c.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_analyze_job_end_to_end(tmp_path):
    c = client(tmp_path)
    assert c.get("/").status_code == 200
    job = wait(c, c.post("/api/analyze", json={"topic": "archaeology", "timezone": "UTC"}).json()["job_id"])
    assert job["status"] == "done", job["error"]
    assert c.get("/api/reports").json()[0]["topic"] == "archaeology"


def test_missing_keys_surface_as_job_error(tmp_path):
    c = client(tmp_path, data_provider="apify")
    job = wait(c, c.post("/api/analyze", json={"topic": "archaeology"}).json()["job_id"])
    assert job["status"] == "error" and "Apify key" in job["error"]


def test_phone_needs_token_but_pc_does_not(tmp_path):
    assert client(tmp_path, host=PC, app_token="s3cret").get("/api/config").json()["is_host"] is True
    phone = client(tmp_path, host=PHONE, app_token="s3cret")
    assert phone.get("/api/config").status_code == 401
    ok = phone.get("/api/config", headers={"X-App-Token": "s3cret"})
    assert ok.status_code == 200 and ok.json()["is_host"] is False


def test_settings_are_pc_only_and_never_leak_keys(tmp_path):
    phone = client(tmp_path, host=PHONE, app_token="s3cret")
    headers = {"X-App-Token": "s3cret"}
    assert phone.get("/api/settings", headers=headers).status_code == 403
    assert phone.put("/api/settings", headers=headers, json={"apify_token": "x"}).status_code == 403
    assert phone.get("/api/phone/qr.svg", headers=headers).status_code == 403

    pc = client(tmp_path, app_token="s3cret")
    assert pc.get("/api/config").json()["data_provider"] == "mock"
    saved = pc.put("/api/settings", json={"apify_token": "apify-secret", "llm_api_key": "", "max_hashtags": "5"}).json()
    assert saved["apify_token_set"] and not saved["llm_api_key_set"] and saved["max_hashtags"] == 5
    assert "apify-secret" not in json.dumps(pc.get("/api/settings").json())
    # A real key switches "auto" mode from demo data to Apify.
    assert pc.get("/api/config").json()["data_provider"] == "apify"
    stored = json.loads((tmp_path / "settings.json").read_text())
    assert stored["apify_token"] == "apify-secret" and stored["app_token"] == "s3cret"


def test_bad_setting_is_rejected(tmp_path):
    assert client(tmp_path).put("/api/settings", json={"max_hashtags": "lots"}).status_code == 400


def test_qr_code_links_phone_with_token(tmp_path):
    c = client(tmp_path, app_token="s3cret")
    assert c.get("/api/phone").json()["url"].endswith("/?token=s3cret")
    res = c.get("/api/phone/qr.svg")
    assert res.status_code == 200 and res.headers["content-type"].startswith("image/svg+xml")


def test_saved_settings_load_on_restart_and_token_is_created(tmp_path):
    first = Settings(db_path=str(tmp_path / "db.sqlite")).with_saved()
    assert first.app_token  # generated and persisted
    first.updated({"llm_api_key": "k"}).save()
    again = Settings(db_path=str(tmp_path / "db.sqlite")).with_saved()
    assert again.app_token == first.app_token and again.active_llm_provider == "openai"
