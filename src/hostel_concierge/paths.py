import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    override = os.environ.get("HOSTEL_DATA_DIR")
    if override:
        return Path(override)
    return repo_root() / "data"


def config_path() -> Path:
    return repo_root() / "config" / "safety.yaml"
