import yaml

from hostel_concierge.paths import config_path


def safety_config() -> dict:
    with config_path().open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def approval_required_tools() -> set[str]:
    return set(safety_config()["approval_required_tools"])


def limits_for(agent: str, overrides: dict | None = None) -> dict:
    configured = dict(safety_config()["limits"][agent])
    if overrides and agent in overrides:
        configured.update(overrides[agent])
    return configured
