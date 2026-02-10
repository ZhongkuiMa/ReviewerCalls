"""Shared test fixtures."""

import yaml
import pytest


@pytest.fixture
def tmp_yaml(tmp_path):
    """Create a temporary YAML file helper.

    Returns a function that writes data to a temp YAML file and returns the path.
    """

    def _write(data, filename="test.yaml"):
        path = tmp_path / filename
        with open(path, "w") as f:
            yaml.dump(data, f)
        return str(path)

    return _write


@pytest.fixture
def sample_conf():
    """Sample conference dictionary."""
    return {
        "short": "IJCAI",
        "name": "International Joint Conference on Artificial Intelligence",
        "domain": "ijcai.org",
        "area": "AI",
        "rank": {"ccf": "A", "core": "A*"},
        "conf_date": 8,
    }


@pytest.fixture
def sample_call():
    """Sample call dictionary."""
    return {
        "conference": "IJCAI",
        "year": 2026,
        "url": "https://2026.ijcai.org/call-for-reviewers/",
        "role": "Reviewer",
        "date": "2025-06-01",
        "confirmed": True,
    }
