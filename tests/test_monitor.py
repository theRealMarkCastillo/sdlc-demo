"""
Tests for SDLC monitor script (sdlc-log-scan.py).

Validates container name constants match docker-compose files,
preventing the false-positive container_down bug from recurring.
"""
import importlib.util
import os
import yaml


# ---------------------------------------------------------------------------
# Load the monitor module (filename has hyphens — use importlib)
# ---------------------------------------------------------------------------

def _load_monitor():
    """Load sdlc-log-scan.py as a module."""
    path = os.path.expanduser("~/.hermes/scripts/sdlc-log-scan.py")
    spec = importlib.util.spec_from_file_location("sdlc_monitor", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_compose_container_names(compose_path: str) -> dict:
    """Extract container_name from each service in a compose file."""
    with open(compose_path) as f:
        data = yaml.safe_load(f)
    names = {}
    for svc_name, svc in data.get("services", {}).items():
        name = svc.get("container_name")
        if name:
            names[svc_name] = name
    return names


# ---------------------------------------------------------------------------
# Constants validation
# ---------------------------------------------------------------------------

def test_prod_container_names_match_compose():
    """Monitor PROD_CONTAINER must match docker-compose.prod.yml."""
    monitor = _load_monitor()
    compose_path = os.path.expanduser("~/git/sdlc-demo/docker-compose.prod.yml")
    compose_names = _load_compose_container_names(compose_path)

    if "app" in compose_names:
        assert monitor.PROD_CONTAINER == compose_names["app"], (
            f"Monitor PROD_CONTAINER={monitor.PROD_CONTAINER!r} "
            f"but compose sets container_name={compose_names['app']!r}"
        )


def test_staging_container_names_match_compose():
    """Monitor STAGING_CONTAINER must match docker-compose.staging.yml."""
    monitor = _load_monitor()
    compose_path = os.path.expanduser("~/git/sdlc-demo/docker-compose.staging.yml")
    compose_names = _load_compose_container_names(compose_path)

    if "app" in compose_names:
        assert monitor.STAGING_CONTAINER == compose_names["app"]


# ---------------------------------------------------------------------------
# fingerprint() tests
# ---------------------------------------------------------------------------

def test_fingerprint_log_anomaly():
    """fingerprint() works on scan_logs() output (has error_type)."""
    monitor = _load_monitor()

    anomaly = {
        "container": "sdlc-demo-app-1",
        "error_type": "DatabaseError",
        "severity": "P0",
        "count": 3,
        "sample": "connection refused",
    }
    fp = monitor.fingerprint(anomaly)
    assert isinstance(fp, str)
    assert len(fp) == 12
    # Deterministic
    assert fp == monitor.fingerprint(dict(anomaly))


def test_fingerprint_stale_anomaly():
    """fingerprint() works on check_stale() output (has 'type', no 'error_type')."""
    monitor = _load_monitor()

    anomaly = {
        "type": "container_down",
        "container": "sdlc-demo-app-1",
        "severity": "P0",
        "summary": "sdlc-demo-app-1 is not running",
    }
    fp = monitor.fingerprint(anomaly)
    assert isinstance(fp, str)
    assert len(fp) == 12


def test_fingerprint_different_types_produce_different_fps():
    """container_down and log errors produce distinct fingerprints."""
    monitor = _load_monitor()

    stale = {"type": "container_down", "container": "sdlc-demo-app-1",
             "severity": "P0"}
    log_err = {"error_type": "DatabaseError", "container": "sdlc-demo-app-1",
               "severity": "P0"}

    assert monitor.fingerprint(stale) != monitor.fingerprint(log_err)


# ---------------------------------------------------------------------------
# check_stale() tests
# ---------------------------------------------------------------------------

def test_check_stale_running(monkeypatch):
    """check_stale() returns None when container is running."""
    monitor = _load_monitor()

    def fake_run(cmd, timeout=30, env=None):
        return "Up 25 minutes"

    monkeypatch.setattr(monitor, "run", fake_run)
    result = monitor.check_stale("my-app")
    assert result is None


def test_check_stale_not_found(monkeypatch):
    """check_stale() returns container_down when docker ps returns empty."""
    monitor = _load_monitor()

    def fake_run(cmd, timeout=30, env=None):
        return ""  # empty = no container

    monkeypatch.setattr(monitor, "run", fake_run)
    result = monitor.check_stale("missing-app")
    assert result is not None
    assert result["type"] == "container_down"
    assert result["severity"] == "P0"


def test_check_stale_restarting(monkeypatch):
    """check_stale() detects restart loops."""
    monitor = _load_monitor()

    def fake_run(cmd, timeout=30, env=None):
        return "Restarting (1) 10 seconds ago"

    monkeypatch.setattr(monitor, "run", fake_run)
    result = monitor.check_stale("loopy-app")
    assert result is not None
    assert result["type"] == "container_restarting"


def test_check_stale_exited(monkeypatch):
    """check_stale() detects exited containers."""
    monitor = _load_monitor()

    def fake_run(cmd, timeout=30, env=None):
        return "Exited (137) 2 hours ago"

    monkeypatch.setattr(monitor, "run", fake_run)
    result = monitor.check_stale("dead-app")
    assert result is not None
    assert result["type"] == "container_exited"
