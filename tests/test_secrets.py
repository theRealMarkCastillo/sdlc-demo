"""Tests for _read_secret() — file-based Docker secret reading with env var fallback."""
import os
import tempfile
import pytest


# ---------------------------------------------------------------------------
# Import the helper once app.py is updated. The tests are written first
# (TDD RED phase) and will fail until the implementation lands.
# We import the function dynamically so this file doesn't crash on import
# before app.py is patched.
# ---------------------------------------------------------------------------

def _import_read_secret():
    """Import _read_secret from app after setting up required env vars."""
    # Ensure required env vars exist so app.py can be imported
    os.environ.setdefault("DB_USER", "sdlc_user_test")
    os.environ.setdefault("DB_PASS", "sdlc_pass_test")
    os.environ.setdefault("SDLC_API_KEY", "test-api-key-for-sdlc-demo")
    os.environ.setdefault("SDLC_API_KEY_USER_ID", "1")
    import importlib
    import app
    importlib.reload(app)
    return app._read_secret


class TestReadSecret:
    """_read_secret(file_env_var) reads from a Docker secret file or falls back to env."""

    def test_file_exists_with_content(self):
        """When the secret file exists and has content, its value is returned."""
        _read_secret = _import_read_secret()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("super-secret-value")
            f.flush()
            f_path = f.name

        try:
            os.environ["MY_SECRET"] = "env-fallback-should-not-be-used"
            os.environ["MY_SECRET_FILE"] = f_path
            result = _read_secret("MY_SECRET", "MY_SECRET_FILE")
            assert result == "super-secret-value"
        finally:
            os.unlink(f_path)
            os.environ.pop("MY_SECRET", None)
            os.environ.pop("MY_SECRET_FILE", None)

    def test_file_exists_but_empty_falls_back_to_env(self):
        """When the secret file exists but is empty, falls back to env var."""
        _read_secret = _import_read_secret()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")  # empty
            f.flush()
            f_path = f.name

        try:
            os.environ["MY_SECRET"] = "fallback-value"
            os.environ["MY_SECRET_FILE"] = f_path
            result = _read_secret("MY_SECRET", "MY_SECRET_FILE")
            assert result == "fallback-value"
        finally:
            os.unlink(f_path)
            os.environ.pop("MY_SECRET", None)
            os.environ.pop("MY_SECRET_FILE", None)

    def test_file_does_not_exist_falls_back_to_env(self):
        """When the secret file path is set but the file doesn't exist, falls back to env."""
        _read_secret = _import_read_secret()
        os.environ["MY_SECRET"] = "fallback-value"
        os.environ["MY_SECRET_FILE"] = "/nonexistent/path/secret.txt"
        try:
            result = _read_secret("MY_SECRET", "MY_SECRET_FILE")
            assert result == "fallback-value"
        finally:
            os.environ.pop("MY_SECRET", None)
            os.environ.pop("MY_SECRET_FILE", None)

    def test_neither_file_nor_env_raises_runtime_error(self):
        """When neither the secret file nor the env var provides a value, RuntimeError is raised."""
        _read_secret = _import_read_secret()
        # Ensure neither env var is set
        os.environ.pop("MISSING_SECRET", None)
        os.environ.pop("MISSING_SECRET_FILE", None)
        with pytest.raises(RuntimeError, match="Missing required secret"):
            _read_secret("MISSING_SECRET", "MISSING_SECRET_FILE")

    def test_no_file_env_var_reads_from_env_directly(self):
        """When no _FILE env var is provided, reads directly from the plain env var."""
        _read_secret = _import_read_secret()
        os.environ["DIRECT_SECRET"] = "direct-value"
        os.environ.pop("DIRECT_SECRET_FILE", None)
        try:
            result = _read_secret("DIRECT_SECRET", "DIRECT_SECRET_FILE")
            assert result == "direct-value"
        finally:
            os.environ.pop("DIRECT_SECRET", None)

    def test_file_env_var_empty_string_falls_back_to_env(self):
        """When the _FILE env var is an empty string, falls back to plain env var."""
        _read_secret = _import_read_secret()
        os.environ["MY_SECRET"] = "fallback-value"
        os.environ["MY_SECRET_FILE"] = ""
        try:
            result = _read_secret("MY_SECRET", "MY_SECRET_FILE")
            assert result == "fallback-value"
        finally:
            os.environ.pop("MY_SECRET", None)
            os.environ.pop("MY_SECRET_FILE", None)
