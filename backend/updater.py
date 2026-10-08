"""In-app updates for the packaged Windows app, from the repo's GitHub Releases.

Keys, reports and the phone token live in the data directory (see config.py),
not next to the .exe, so swapping the .exe never touches them.

Update steps: download the new .exe beside the running one, verify its
SHA-256 against GitHub's digest, rename the running .exe to .old (Windows
allows renaming a running program, just not overwriting it), move the new
one into place, start it, and exit. The new process deletes the .old file.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from .config import FROZEN

REPO = "ChadPickett/Social-Climb"
ASSET_NAME = "SocialClimb.exe"
# Overridable so CI can rehearse a full update against a local fake release.
RELEASE_API = os.environ.get(
    "SOCIALCLIMB_UPDATE_API", f"https://api.github.com/repos/{REPO}/releases/latest"
)

try:  # written by the release build; absent when running from source
    from ._build import BUILD
except ImportError:
    BUILD = 0

CAN_SELF_UPDATE = FROZEN and os.name == "nt"


class UpdateError(RuntimeError):
    pass


def parse_build(tag: str | None) -> int:
    match = re.fullmatch(r"build-(\d+)", tag or "")
    return int(match.group(1)) if match else 0


def fetch_latest(client: httpx.Client | None = None) -> dict:
    client = client or httpx.Client(timeout=15, follow_redirects=True)
    try:
        resp = client.get(RELEASE_API, headers={"Accept": "application/vnd.github+json"})
        resp.raise_for_status()
        release = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise UpdateError(f"Couldn't check for updates: {exc}") from exc
    asset = next((a for a in release.get("assets", []) if a.get("name") == ASSET_NAME), None)
    if not asset:
        raise UpdateError("The latest release has no SocialClimb.exe yet. Try again in a few minutes.")
    return {
        "build": parse_build(release.get("tag_name")),
        "notes": (release.get("body") or "").strip(),
        "url": asset["browser_download_url"],
        "sha256": (asset.get("digest") or "").removeprefix("sha256:"),
    }


def download(info: dict, dest: Path, client: httpx.Client | None = None) -> None:
    """Download the release asset to `dest`, verifying it before keeping it."""
    client = client or httpx.Client(timeout=120, follow_redirects=True)
    digest = hashlib.sha256()
    try:
        with client.stream("GET", info["url"]) as resp, open(dest, "wb") as out:
            resp.raise_for_status()
            for chunk in resp.iter_bytes(1 << 16):
                digest.update(chunk)
                out.write(chunk)
    except (httpx.HTTPError, OSError) as exc:
        dest.unlink(missing_ok=True)
        raise UpdateError(f"Download failed: {exc}") from exc
    with open(dest, "rb") as f:
        is_exe = f.read(2) == b"MZ"
    if not is_exe or (info["sha256"] and digest.hexdigest() != info["sha256"]):
        dest.unlink(missing_ok=True)
        raise UpdateError("The downloaded update was damaged. Please try again.")


def swap(exe: Path, new: Path) -> None:
    """Put `new` where `exe` is, keeping the running file as .old (rolled back on failure)."""
    old = exe.with_name(exe.name + ".old")
    old.unlink(missing_ok=True)
    exe.rename(old)
    try:
        new.rename(exe)
    except OSError:
        old.rename(exe)
        raise


def install(info: dict, exe: Path, client: httpx.Client | None = None) -> None:
    new = exe.with_name(exe.name + ".new")
    download(info, new, client)
    try:
        swap(exe, new)
    except OSError as exc:
        new.unlink(missing_ok=True)
        raise UpdateError(
            f"Couldn't replace the app file ({exc}). Move SocialClimb.exe to a folder you own, "
            "like Documents, and try again."
        ) from exc


def restart(exe: Path, port: int) -> None:
    """Start the new version in its own window, then exit this process."""
    # Tells PyInstaller the child is an independent app, not part of this one.
    env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    subprocess.Popen(
        [str(exe), "--port", str(port), "--after-update"],
        env=env, cwd=exe.parent, creationflags=flags, close_fds=True,
    )
    threading.Timer(1.0, os._exit, [0]).start()


def cleanup_old_exe() -> None:
    """Delete the previous version once its process has exited."""
    old = Path(sys.executable).with_name(Path(sys.executable).name + ".old")

    def work():
        for _ in range(15):
            try:
                old.unlink(missing_ok=True)
                return
            except OSError:
                time.sleep(2)

    threading.Thread(target=work, daemon=True).start()


class Updater:
    """Caches the latest-release lookup so page loads don't hammer GitHub."""

    CACHE_SECONDS = 600

    def __init__(self, current: int = BUILD, can_update: bool = CAN_SELF_UPDATE, client=None):
        self.current = current
        self.can_update = can_update
        self.client = client
        self._cached: tuple[float, dict] | None = None
        self._lock = threading.Lock()

    def latest(self, refresh: bool = False) -> dict:
        with self._lock:
            if refresh or not self._cached or time.monotonic() - self._cached[0] > self.CACHE_SECONDS:
                self._cached = (time.monotonic(), fetch_latest(self.client))
            return self._cached[1]

    def status(self, refresh: bool = False) -> dict:
        result = {"current": self.current, "can_update": self.can_update, "available": False}
        if not self.can_update:
            return result
        try:
            info = self.latest(refresh)
        except UpdateError as exc:
            return {**result, "error": str(exc)}
        return {
            **result,
            "latest": info["build"],
            "available": info["build"] > self.current,
            "notes": info["notes"],
        }

    def apply(self, port: int) -> int:
        if not self.can_update:
            raise UpdateError("Updates only work in the installed SocialClimb.exe.")
        info = self.latest(refresh=True)
        if info["build"] <= self.current:
            raise UpdateError("You already have the latest version.")
        exe = Path(sys.executable)
        install(info, exe, self.client)
        restart(exe, port)
        return info["build"]
