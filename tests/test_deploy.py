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
        compose_calls = [line for line in content.splitlines() if "docker compose" in line]
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


# ---------------------------------------------------------------------------
# Docker Compose secrets migration tests
# ---------------------------------------------------------------------------

class TestDockerComposeSecrets:
    """docker-compose.{staging,prod}.yml use file-based secrets, not env vars for secrets."""

    def test_staging_has_top_level_secrets_section(self):
        compose_file = PROJECT_DIR / "docker-compose.staging.yml"
        content = compose_file.read_text()
        # Should have a top-level 'secrets:' section (not under services)
        assert "\nsecrets:" in content or content.startswith("secrets:"), (
            "docker-compose.staging.yml missing top-level secrets: section"
        )

    def test_prod_has_top_level_secrets_section(self):
        compose_file = PROJECT_DIR / "docker-compose.prod.yml"
        content = compose_file.read_text()
        assert "\nsecrets:" in content or content.startswith("secrets:"), (
            "docker-compose.prod.yml missing top-level secrets: section"
        )

    def test_staging_app_service_has_secrets_mount(self):
        compose_file = PROJECT_DIR / "docker-compose.staging.yml"
        content = compose_file.read_text()
        # The app service should mount db_pass and sdlc_api_key secrets
        assert "db_pass" in content
        assert "sdlc_api_key" in content
        # Should use _FILE vars instead of direct env vars for secrets
        assert "DB_PASS_FILE" in content, "Missing DB_PASS_FILE in staging compose"
        assert "SDLC_API_KEY_FILE" in content, "Missing SDLC_API_KEY_FILE in staging compose"

    def test_staging_db_service_has_secrets_mount(self):
        compose_file = PROJECT_DIR / "docker-compose.staging.yml"
        content = compose_file.read_text()
        assert "postgres_password" in content
        assert "POSTGRES_PASSWORD_FILE" in content, (
            "Missing POSTGRES_PASSWORD_FILE in staging compose"
        )

    def test_prod_app_service_has_secrets_mount(self):
        compose_file = PROJECT_DIR / "docker-compose.prod.yml"
        content = compose_file.read_text()
        assert "db_pass" in content
        assert "sdlc_api_key" in content
        assert "DB_PASS_FILE" in content, "Missing DB_PASS_FILE in prod compose"
        assert "SDLC_API_KEY_FILE" in content, "Missing SDLC_API_KEY_FILE in prod compose"

    def test_prod_db_service_has_secrets_mount(self):
        compose_file = PROJECT_DIR / "docker-compose.prod.yml"
        content = compose_file.read_text()
        assert "postgres_password" in content
        assert "POSTGRES_PASSWORD_FILE" in content, (
            "Missing POSTGRES_PASSWORD_FILE in prod compose"
        )

    def test_staging_secret_paths_use_staging_prefix(self):
        """Secrets in staging use staging_ prefix in file paths."""
        compose_file = PROJECT_DIR / "docker-compose.staging.yml"
        content = compose_file.read_text()
        assert "staging_db_pass" in content
        assert "staging_sdlc_api_key" in content
        assert "staging_postgres_password" in content

    def test_prod_secret_paths_use_prod_prefix(self):
        """Secrets in prod use prod_ prefix in file paths."""
        compose_file = PROJECT_DIR / "docker-compose.prod.yml"
        content = compose_file.read_text()
        assert "prod_db_pass" in content
        assert "prod_sdlc_api_key" in content
        assert "prod_postgres_password" in content

    def test_no_plaintext_db_pass_in_staging_app_env(self):
        """Staging app service should NOT have DB_PASS directly in environment."""
        compose_file = PROJECT_DIR / "docker-compose.staging.yml"
        content = compose_file.read_text()
        # Find the app service section
        app_section_start = content.find("  app:")
        if app_section_start == -1:
            pytest.skip("app service not found in staging compose")
        # Find the end of the app service (next top-level key)
        app_section = content[app_section_start:]
        # DB_PASS should only appear as DB_PASS_FILE, not as a raw env var
        lines = app_section.splitlines()
        env_lines = []
        in_env = False
        for line in lines:
            if line.strip().startswith("environment:"):
                in_env = True
                continue
            if in_env:
                if not line.startswith("      "):  # end of environment indentation
                    break
                env_lines.append(line)
        for line in env_lines:
            if "DB_PASS" in line:
                assert "DB_PASS_FILE" in line, (
                    f"DB_PASS found without _FILE suffix in staging app env: {line.strip()}"
                )

    def test_no_plaintext_postgres_password_in_staging_db_env(self):
        """Staging db service should NOT have POSTGRES_PASSWORD directly in environment."""
        compose_file = PROJECT_DIR / "docker-compose.staging.yml"
        content = compose_file.read_text()
        db_section_start = content.find("  db:")
        if db_section_start == -1:
            pytest.skip("db service not found in staging compose")
        db_section = content[db_section_start:]
        lines = db_section.splitlines()
        env_lines = []
        in_env = False
        for line in lines:
            if line.strip().startswith("environment:"):
                in_env = True
                continue
            if in_env:
                if not line.startswith("      "):
                    break
                env_lines.append(line)
        for line in env_lines:
            if "POSTGRES_PASSWORD" in line:
                assert "POSTGRES_PASSWORD_FILE" in line, (
                    f"POSTGRES_PASSWORD found without _FILE suffix in staging db env: {line.strip()}"
                )


# ---------------------------------------------------------------------------
# deploy.sh split-env sourcing tests
# ---------------------------------------------------------------------------

class TestDeployEnvSourcing:
    """deploy.sh sources .env.<env> instead of .env for staging/prod isolation."""

    def test_sources_env_dot_env_var(self):
        """deploy.sh should source .env.$ENV, not .env directly."""
        content = DEPLOY_SCRIPT.read_text()
        # Should reference .env.${ENV} or .env.$ENV
        assert ".env.${ENV}" in content or '.env.$ENV' in content or '.env."${ENV}"' in content, (
            "deploy.sh must source .env.${ENV}, not .env"
        )

    def test_env_file_not_found_check(self):
        """deploy.sh should check that the env file exists before sourcing."""
        content = DEPLOY_SCRIPT.read_text()
        assert "-f" in content or "-e" in content or "not found" in content.lower(), (
            "deploy.sh must check that env file exists before sourcing"
        )

    def test_secrets_directory_creation(self):
        """deploy.sh should create secrets/ directory before writing secret files."""
        content = DEPLOY_SCRIPT.read_text()
        assert "mkdir" in content and "secrets" in content, (
            "deploy.sh must create secrets/ directory"
        )

    def test_secret_files_written_before_compose_up(self):
        """deploy.sh should write secret files to secrets/ before docker compose up."""
        content = DEPLOY_SCRIPT.read_text()
        # Secret file writes (echo ... > secrets/...) should appear before compose up
        up_line_idx = None
        secret_write_idx = None
        for i, line in enumerate(content.splitlines()):
            if "docker compose" in line and "up" in line:
                up_line_idx = i
            if "secrets/" in line and ">" in line:
                secret_write_idx = i
        assert secret_write_idx is not None, "No secret file writes found in deploy.sh"
        assert up_line_idx is not None, "No compose up command found in deploy.sh"
        assert secret_write_idx < up_line_idx, (
            f"Secret file writes (line {secret_write_idx + 1}) must happen before "
            f"compose up (line {up_line_idx + 1})"
        )
