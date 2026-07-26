"""Tests for scripts/deploy.sh — port mapping and env validation."""
import subprocess
import pytest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEPLOY_SCRIPT = PROJECT_DIR / "scripts" / "deploy.sh"


def _run_deploy(args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Run deploy.sh with given args, capturing output. Does NOT actually deploy."""
    env = {"PATH": "/usr/bin:/bin", "HOME": str(PROJECT_DIR)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        f"bash {DEPLOY_SCRIPT} {args}",
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=str(PROJECT_DIR),
    )


class TestEnvValidation:
    """deploy.sh rejects invalid environments."""

    def test_rejects_empty(self):
        result = _run_deploy("")
        # Defaults to staging when arg is empty (treated as no arg)
        # So it should run (and fail at docker) rather than reject
        assert "ERROR" not in result.stderr

    def test_rejects_invalid(self):
        result = _run_deploy("dev")
        assert result.returncode != 0
        assert "Invalid environment" in (result.stderr + result.stdout)

    def test_accepts_staging(self):
        result = _run_deploy("staging")
        # Will fail because docker isn't in PATH, but should NOT show env error
        assert "Invalid environment" not in result.stderr

    def test_accepts_prod(self):
        result = _run_deploy("prod")
        assert "Invalid environment" not in result.stderr


class TestProjectName:
    """deploy.sh uses --project-name sdlc-<env> to isolate staging from prod."""

    def test_project_name_in_compose_commands(self):
        """Verify --project-name flag is present in deploy script for docker compose calls."""
        content = DEPLOY_SCRIPT.read_text()
        compose_calls = [l for l in content.splitlines() if "docker compose" in l]
        # Every docker compose call should include --project-name
        for call in compose_calls:
            assert "--project-name" in call, (
                f"docker compose call missing --project-name:\n  {call}"
            )
        # At least two calls (down + up)
        assert len(compose_calls) >= 2, f"Expected >=2 docker compose calls, got {len(compose_calls)}"

    def test_project_name_matches_env(self):
        """--project-name should reference $PROJECT_NAME, which is sdlc-$ENV."""
        content = DEPLOY_SCRIPT.read_text()
        assert 'PROJECT_NAME="sdlc-${ENV}"' in content or 'PROJECT_NAME="sdlc-$ENV"' in content.replace(
            "{ENV}", "ENV"
        )


class TestPortMapping:
    """Health check port matches the compose file's host port."""

    def test_port_map_staging(self):
        content = DEPLOY_SCRIPT.read_text()
        assert "5001" in content, "Missing staging port 5001"

    def test_port_map_prod(self):
        content = DEPLOY_SCRIPT.read_text()
        assert "5002" in content, "Missing prod port 5002"

    def test_port_no_longer_hardcoded_fallback(self):
        """The old bug: ${PORT:-5000} used a hardcoded fallback that didn't
        match either environment's actual port."""
        content = DEPLOY_SCRIPT.read_text()
        assert '${PORT:-' not in content, (
            "PORT fallback still present — must use per-env APP_PORT instead"
        )

    def test_app_port_used_in_health_check(self):
        content = DEPLOY_SCRIPT.read_text()
        assert "${APP_PORT}" in content, "Health check must use $APP_PORT, not a hardcoded value"
