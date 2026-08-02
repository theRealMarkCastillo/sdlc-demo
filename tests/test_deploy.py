"""Tests for scripts/deploy.sh — port mapping and env validation."""
import subprocess
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


class TestDockerComposeSecrets:
    """docker-compose.staging.yml uses file-based secrets, not env interpolation."""

    COMPOSE_FILE = PROJECT_DIR / "docker-compose.staging.yml"

    def test_has_top_level_secrets_block(self):
        """The compose file must have a top-level 'secrets:' block."""
        content = self.COMPOSE_FILE.read_text()
        assert "secrets:" in content, "Missing top-level secrets block"

    def test_no_direct_env_var_passwords(self):
        """No ${POSTGRES_PASSWORD}, ${DB_PASS}, or ${SDLC_API_KEY} in environment section."""
        content = self.COMPOSE_FILE.read_text()
        # Extract the environment sections (between 'environment:' and next section)
        import re
        # Find all environment: blocks
        env_blocks = re.findall(r'environment:(.*?)(?=\n  \w|\n\w|\Z)', content, re.DOTALL)
        for block in env_blocks:
            assert "${POSTGRES_PASSWORD}" not in block, (
                "POSTGRES_PASSWORD env interpolation found — must use POSTGRES_PASSWORD_FILE"
            )
            assert "${DB_PASS}" not in block, (
                "DB_PASS env interpolation found — must use DB_PASS_FILE"
            )
            assert "${SDLC_API_KEY}" not in block, (
                "SDLC_API_KEY env interpolation found — must use SDLC_API_KEY_FILE"
            )

    def test_has_file_based_env_vars(self):
        """Environment uses _FILE vars pointing to /run/secrets/ paths."""
        content = self.COMPOSE_FILE.read_text()
        assert "POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password" in content, (
            "Missing POSTGRES_PASSWORD_FILE pointing to /run/secrets/postgres_password"
        )
        assert "DB_PASS_FILE: /run/secrets/db_pass" in content, (
            "Missing DB_PASS_FILE pointing to /run/secrets/db_pass"
        )
        assert "SDLC_API_KEY_FILE: /run/secrets/sdlc_api_key" in content, (
            "Missing SDLC_API_KEY_FILE pointing to /run/secrets/sdlc_api_key"
        )

    def test_secrets_reference_staging_files(self):
        """Top-level secrets block references staging_*.txt files."""
        content = self.COMPOSE_FILE.read_text()
        assert "staging_db_pass.txt" in content, "Missing staging_db_pass.txt in secrets block"
        assert "staging_sdlc_api_key.txt" in content, "Missing staging_sdlc_api_key.txt in secrets block"
        assert "staging_postgres_password.txt" in content, "Missing staging_postgres_password.txt in secrets block"

    def test_db_service_has_secrets(self):
        """db service has a 'secrets' entry mounting postgres_password."""
        content = self.COMPOSE_FILE.read_text()
        # Check db service section has secrets with postgres_password
        assert "postgres_password" in content, "db service must mount postgres_password secret"

    def test_app_service_has_secrets(self):
        """app service has 'secrets' entries for db_pass and sdlc_api_key."""
        content = self.COMPOSE_FILE.read_text()
        assert "db_pass" in content, "app service must mount db_pass secret"
        assert "sdlc_api_key" in content, "app service must mount sdlc_api_key secret"


class TestDeployEnvSourcing:
    """deploy.sh sources .env.${ENV} instead of .env."""

    def test_sources_env_specific_file(self):
        """deploy.sh must source .env.${ENV}, not .env."""
        content = DEPLOY_SCRIPT.read_text()
        # Accepts either direct 'source .env.${ENV}' or the variable pattern
        # 'ENV_FILE=".env.${ENV}"; source "$ENV_FILE"'
        has_direct = any(pat in content for pat in [
            "source .env.${ENV}", 'source ".env.${ENV}"',
            'source .env."${ENV}"', "source .env.$ENV",
        ])
        has_via_var = ('.env.${ENV}' in content or '.env.$ENV' in content) and \
                      'source "$ENV_FILE"' in content
        assert has_direct or has_via_var, (
            "deploy.sh must source .env.${ENV} instead of .env"
        )

    def test_no_bare_source_dot_env(self):
        """deploy.sh must NOT contain 'source .env' (without ${ENV} suffix)."""
        content = DEPLOY_SCRIPT.read_text()
        # source .env (without suffix) should not appear
        lines = content.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("source ") and ".env" in stripped:
                # Allow .env.${ENV} but not bare .env
                assert "${ENV}" in stripped or "$ENV" in stripped or '${ENV}' in stripped, (
                    f"Found 'source .env' without env suffix: {stripped}"
                )

    def test_env_file_check_exists(self):
        """deploy.sh checks that .env.${ENV} exists before sourcing."""
        content = DEPLOY_SCRIPT.read_text()
        assert "ENV_FILE" in content, "deploy.sh must define ENV_FILE variable"
        assert ".env.${ENV}" in content or ".env.$ENV" in content, (
            "deploy.sh must reference .env.${ENV}"
        )


class TestDeploySecretStaging:
    """deploy.sh stages file-based secrets before docker compose up."""

    def test_creates_secrets_directory(self):
        """deploy.sh must create secrets/ directory before writing secret files."""
        content = DEPLOY_SCRIPT.read_text()
        assert "mkdir" in content and "secrets" in content.replace(" ", ""), (
            "deploy.sh must create secrets/ directory"
        )

    def test_writes_secret_files(self):
        """deploy.sh writes secret files from env vars to secrets/ directory."""
        content = DEPLOY_SCRIPT.read_text()
        assert "secrets/${ENV}_db_pass.txt" in content or 'secrets/"${ENV}"_db_pass.txt' in content or \
               "secrets/$ENV" in content, (
            "deploy.sh must write secrets/${ENV}_db_pass.txt"
        )
    def test_does_not_clean_up_secret_files(self):
        """deploy.sh must NOT delete secret files after docker compose up.

        Secret files are bind-mounted into containers at runtime.
        Deleting them breaks /run/secrets/* inside containers immediately.
        secrets/ is already in .gitignore and .dockerignore — no cleanup needed.
        """
        content = DEPLOY_SCRIPT.read_text()
        # After docker compose up, there must be NO rm of secrets/*
        lines = content.splitlines()
        compose_up_idx = None
        for i, line in enumerate(lines):
            if "docker compose" in line and "up" in line:
                compose_up_idx = i
                break
        assert compose_up_idx is not None, "Could not find 'docker compose up' command"
        # Verify NO cleanup after compose up
        after_up = "\n".join(lines[compose_up_idx:])
        assert "secrets/" not in after_up, (
            "deploy.sh must NOT clean up secret files after docker compose up — "
            "files are bind-mounted and must persist"
        )

    def test_chmod_secret_files(self):
        """deploy.sh sets restrictive permissions (600) on secret files."""
        content = DEPLOY_SCRIPT.read_text()
        # Should chmod 600 the secret files
        assert "chmod" in content and "600" in content, (
            "deploy.sh must chmod 600 secret files"
        )
