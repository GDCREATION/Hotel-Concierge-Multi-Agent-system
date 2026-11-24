import shutil

import pytest

from hostel_concierge.paths import repo_root
from hostel_concierge.runtime_state import reset_runtime


@pytest.fixture(autouse=True)
def isolated_hostel(tmp_path, monkeypatch):
    destination = tmp_path / "data"
    shutil.copytree(repo_root() / "data", destination)
    monkeypatch.setenv("HOSTEL_DATA_DIR", str(destination))
    monkeypatch.setenv("HOSTEL_MODEL", "scripted")
    monkeypatch.setenv("HOSTEL_NOW", "2026-11-24T08:30:00")
    monkeypatch.delenv("HOSTEL_GUEST_ID", raising=False)
    monkeypatch.delenv("HOSTEL_ROOM", raising=False)
    reset_runtime()
    yield destination
    reset_runtime()
