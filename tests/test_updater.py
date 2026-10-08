import hashlib

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import updater
from backend.config import Settings
from backend.main import create_app
from backend.updater import Updater, UpdateError

EXE = b"MZ" + b"new version" * 100


def fake_github(tag="build-7", body=EXE, digest=None, status=200):
    digest = hashlib.sha256(EXE).hexdigest() if digest is None else digest

    def handler(request):
        if request.url.path.endswith("/releases/latest"):
            return httpx.Response(status, json={"tag_name": tag, "body": "Faster ideas", "assets": [{
                "name": "SocialClimb.exe", "digest": f"sha256:{digest}",
                "browser_download_url": "https://example.test/SocialClimb.exe"}]})
        return httpx.Response(200, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_status_reports_newer_build_with_notes():
    status = Updater(current=5, can_update=True, client=fake_github()).status()
    assert status == {"current": 5, "can_update": True, "available": True, "latest": 7, "notes": "Faster ideas"}
    assert Updater(current=7, can_update=True, client=fake_github()).status()["available"] is False


def test_status_when_offline_is_not_an_error_for_the_page():
    status = Updater(current=5, can_update=True, client=fake_github(status=500)).status()
    assert status["available"] is False and "Couldn't check" in status["error"]


def test_running_from_source_never_offers_updates():
    assert Updater(current=0, can_update=False, client=fake_github()).status()["available"] is False


def test_install_swaps_exe_and_keeps_old_copy(tmp_path):
    exe = tmp_path / "SocialClimb.exe"
    exe.write_bytes(b"MZ old")
    info = updater.fetch_latest(fake_github())
    updater.install(info, exe, fake_github())
    assert exe.read_bytes() == EXE
    assert (tmp_path / "SocialClimb.exe.old").read_bytes() == b"MZ old"
    assert not (tmp_path / "SocialClimb.exe.new").exists()


@pytest.mark.parametrize("client", [fake_github(digest="0" * 64), fake_github(body=b"<html>not an exe")])
def test_damaged_download_leaves_current_exe_alone(tmp_path, client):
    exe = tmp_path / "SocialClimb.exe"
    exe.write_bytes(b"MZ old")
    with pytest.raises(UpdateError, match="damaged"):
        updater.install(updater.fetch_latest(client), exe, client)
    assert exe.read_bytes() == b"MZ old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["SocialClimb.exe"]


def test_update_endpoints_are_pc_only(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "db.sqlite"), app_token="t"),
                     updater=Updater(current=5, can_update=True, client=fake_github()))
    pc = TestClient(app, client=("127.0.0.1", 1))
    phone = TestClient(app, client=("192.168.1.9", 1), headers={"X-App-Token": "t"})
    assert pc.get("/api/update").json()["available"] is True
    assert phone.get("/api/update").status_code == 403
    assert phone.post("/api/update").status_code == 403
    assert pc.get("/api/config").json()["build"] == 5


def test_update_refused_from_source_checkout(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "db.sqlite")), updater=Updater(current=0, can_update=False))
    res = TestClient(app, client=("127.0.0.1", 1)).post("/api/update")
    assert res.status_code == 400 and "installed SocialClimb.exe" in res.json()["detail"]
