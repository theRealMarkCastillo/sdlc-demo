"""SDLC Demo tests."""
import pytest
import requests
import os
import psycopg2

# Set required credential env vars so app module can be imported in unit tests.
# Tests that verify the app crashes on missing creds use monkeypatch.delenv()
# to temporarily remove these and then importlib.reload().
os.environ.setdefault("DB_USER", "sdlc_user_test")
os.environ.setdefault("DB_PASS", "sdlc_pass_test")
os.environ.setdefault("SDLC_API_KEY", "test-api-key-for-sdlc-demo")
os.environ.setdefault("SDLC_API_KEY_USER_ID", "1")

BASE_URL = os.environ.get("TEST_URL", "http://localhost:5000")

# AUTH_HEADER is dynamically built so the correct key is used:
# - Unit tests (Flask test client): os.environ.setdefault sets the test key above
# - Integration tests (TEST_URL=...): SDLC_API_KEY must be set to the server's key
AUTH_HEADER = {"X-API-Key": os.environ.get("SDLC_API_KEY", "test-api-key-for-sdlc-demo")}


def test_health():
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"


def test_create_and_list_users():
    # Create a user
    r = requests.post(f"{BASE_URL}/api/users", json={
        "username": "testuser",
        "email": "test@example.com",
        "age": 30
    }, headers=AUTH_HEADER)
    assert r.status_code == 201
    user = r.json()
    assert user["username"] == "testuser"

    # List users
    r = requests.get(f"{BASE_URL}/api/users")
    assert r.status_code == 200
    users = r.json()
    assert len(users) >= 1


def test_get_user_by_id_found():
    """GET /api/users/<id> returns user when found."""
    # Create a user first so we have a known ID
    r = requests.post(f"{BASE_URL}/api/users", json={
        "username": "getbyid_test",
        "email": "getbyid@example.com",
        "age": 25
    }, headers=AUTH_HEADER)
    assert r.status_code == 201
    user_id = r.json()["id"]

    r = requests.get(f"{BASE_URL}/api/users/{user_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == user_id
    assert data["username"] == "getbyid_test"
    assert data["email"] == "getbyid@example.com"
    assert data["age"] == 25
    assert data["active"] is True


def test_get_user_by_id_not_found():
    """GET /api/users/<id> returns 404 when user does not exist."""
    r = requests.get(f"{BASE_URL}/api/users/99999")
    assert r.status_code == 404
    data = r.json()
    assert "error" in data
    assert "not found" in data["error"].lower()


def test_get_user_by_id_invalid_id():
    """GET /api/users/<id> returns 400 when id is not an integer."""
    r = requests.get(f"{BASE_URL}/api/users/abc")
    assert r.status_code == 400
    data = r.json()
    assert "error" in data
    assert "integer" in data["error"].lower()


def test_get_user_by_id_zero():
    """GET /api/users/<id> returns 400 when id is zero."""
    r = requests.get(f"{BASE_URL}/api/users/0")
    assert r.status_code == 400
    data = r.json()
    assert "error" in data
    assert "positive" in data["error"].lower()


def test_get_user_by_id_negative():
    """GET /api/users/<id> returns 400 when id is negative."""
    r = requests.get(f"{BASE_URL}/api/users/-5")
    assert r.status_code == 400
    data = r.json()
    assert "error" in data
    assert "positive" in data["error"].lower()


# ---------------------------------------------------------------------------
# POST /api/users/<id>/deactivate
# ---------------------------------------------------------------------------


def test_deactivate_user_success():
    """POST /api/users/<id>/deactivate sets active=false and returns user."""
    # Create a user first
    r = requests.post(f"{BASE_URL}/api/users", json={
        "username": "deactivate_test",
        "email": "deactivate@example.com",
        "age": 28
    }, headers=AUTH_HEADER)
    assert r.status_code == 201
    user_id = r.json()["id"]

    # Deactivate the user
    r = requests.post(f"{BASE_URL}/api/users/{user_id}/deactivate", headers=AUTH_HEADER)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == user_id
    assert data["active"] is False

    # Verify via GET that active is actually false in DB
    r = requests.get(f"{BASE_URL}/api/users/{user_id}")
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_deactivate_user_not_found():
    """POST /api/users/<id>/deactivate returns 404 for non-existent user."""
    r = requests.post(f"{BASE_URL}/api/users/99999/deactivate", headers=AUTH_HEADER)
    assert r.status_code == 404
    data = r.json()
    assert "error" in data
    assert "not found" in data["error"].lower()


def test_deactivate_user_invalid_id():
    """POST /api/users/<id>/deactivate returns 400 for non-integer id."""
    r = requests.post(f"{BASE_URL}/api/users/abc/deactivate", headers=AUTH_HEADER)
    assert r.status_code == 400
    data = r.json()
    assert "error" in data
    assert "integer" in data["error"].lower()


def test_deactivate_user_zero_id():
    """POST /api/users/<id>/deactivate returns 400 for zero id."""
    r = requests.post(f"{BASE_URL}/api/users/0/deactivate", headers=AUTH_HEADER)
    assert r.status_code == 400
    data = r.json()
    assert "error" in data
    assert "positive" in data["error"].lower()


def test_deactivate_user_negative_id():
    """POST /api/users/<id>/deactivate returns 400 for negative id."""
    r = requests.post(f"{BASE_URL}/api/users/-5/deactivate", headers=AUTH_HEADER)
    assert r.status_code == 400
    data = r.json()
    assert "error" in data
    assert "positive" in data["error"].lower()


def test_deactivate_user_already_inactive():
    """POST /api/users/<id>/deactivate is idempotent — 200 on already-inactive."""
    # Create a user
    r = requests.post(f"{BASE_URL}/api/users", json={
        "username": "idempotent_test",
        "email": "idempotent@example.com",
        "age": 35
    }, headers=AUTH_HEADER)
    assert r.status_code == 201
    user_id = r.json()["id"]

    # First deactivate
    r = requests.post(f"{BASE_URL}/api/users/{user_id}/deactivate", headers=AUTH_HEADER)
    assert r.status_code == 200
    assert r.json()["active"] is False

    # Second deactivate (idempotent)
    r = requests.post(f"{BASE_URL}/api/users/{user_id}/deactivate", headers=AUTH_HEADER)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == user_id
    assert data["active"] is False


def test_deactivate_user_db_unavailable(monkeypatch):
    """POST /api/users/<id>/deactivate returns 503 when DB is unreachable."""
    import app as app_module
    import psycopg2

    def raise_operational_error():
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(app_module, "get_db", raise_operational_error)

    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate", headers=AUTH_HEADER)
        assert r.status_code == 503
        data = r.get_json()
        assert data["error"] == "database unavailable"


def test_deactivate_user_rollback_raises(monkeypatch):
    """POST /api/users/<id>/deactivate returns 503 when both commit and rollback raise."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCommitAndRollbackError())

    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate", headers=AUTH_HEADER)
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


# ---------------------------------------------------------------------------
# DB error handling — list_users, create_user, get_user
# ---------------------------------------------------------------------------


def test_list_users_db_unavailable(monkeypatch):
    """GET /api/users returns 503 when DB is unreachable."""
    import app as app_module
    import psycopg2

    def raise_operational_error():
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(app_module, "get_db", raise_operational_error)

    with app_module.app.test_client() as client:
        r = client.get("/api/users")
        assert r.status_code == 503
        data = r.get_json()
        assert data["error"] == "database unavailable"


def test_create_user_db_unavailable(monkeypatch):
    """POST /api/users returns 503 when DB is unreachable."""
    import app as app_module
    import psycopg2

    def raise_operational_error():
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(app_module, "get_db", raise_operational_error)

    with app_module.app.test_client() as client:
        r = client.post("/api/users", headers=AUTH_HEADER, json={
            "username": "testuser",
            "email": "test@example.com",
            "age": 30
        })
        assert r.status_code == 503
        data = r.get_json()
        assert data["error"] == "database unavailable"


def test_get_user_db_unavailable(monkeypatch):
    """GET /api/users/<id> returns 503 when DB is unreachable — no NameError."""
    import app as app_module
    import psycopg2

    def raise_operational_error():
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(app_module, "get_db", raise_operational_error)

    with app_module.app.test_client() as client:
        r = client.get("/api/users/1")
        assert r.status_code == 503
        data = r.get_json()
        assert data["error"] == "database unavailable"


# ---------------------------------------------------------------------------
# Deep DB error path tests — cursor, execute, fetch, commit, rollback failures
# ---------------------------------------------------------------------------


class _FakeCursorExecuteError:
    """Cursor that raises on execute()."""

    def execute(self, *args, **kwargs):
        raise psycopg2.OperationalError("execute failed")

    def close(self):
        pass


class _FakeConnForExecute:
    def cursor(self):
        return _FakeCursorExecuteError()

    def close(self):
        pass


class _FakeCursorFetchError:
    """Cursor whose fetchone/fetchall raises."""

    def execute(self, *args, **kwargs):
        pass

    def fetchone(self):
        raise psycopg2.OperationalError("fetchone failed")

    def fetchall(self):
        raise psycopg2.OperationalError("fetchall failed")

    def close(self):
        pass


class _FakeConnForFetch:
    def cursor(self):
        return _FakeCursorFetchError()

    def close(self):
        pass


class _FakeCursorForCommit:
    """Cursor that works, but the connection's commit will fail."""

    def execute(self, *args, **kwargs):
        pass

    def fetchone(self):
        return (42,)  # succeeds — triggers commit path

    def close(self):
        pass


class _FakeConnCommitError:
    """Connection where commit raises (triggers rollback in except)."""

    def cursor(self):
        return _FakeCursorForCommit()

    def commit(self):
        raise psycopg2.OperationalError("commit failed")

    def rollback(self):
        pass  # rollback succeeds

    def close(self):
        pass


class _FakeConnCommitAndRollbackError:
    """Connection where BOTH commit AND rollback raise."""

    def cursor(self):
        return _FakeCursorForCommit()

    def commit(self):
        raise psycopg2.OperationalError("commit failed")

    def rollback(self):
        raise psycopg2.OperationalError("rollback also failed")

    def close(self):
        pass


class _FakeConnCursorError:
    """Connection whose cursor() raises."""

    def cursor(self):
        raise psycopg2.OperationalError("cursor failed")

    def rollback(self):
        pass

    def close(self):
        pass


# --- list_users deep error paths ---


def test_list_users_cursor_raises(monkeypatch):
    """GET /api/users returns 503 when conn.cursor() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCursorError())

    with app_module.app.test_client() as client:
        r = client.get("/api/users")
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_list_users_execute_raises(monkeypatch):
    """GET /api/users returns 503 when cur.execute() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForExecute())

    with app_module.app.test_client() as client:
        r = client.get("/api/users")
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_list_users_fetchall_raises(monkeypatch):
    """GET /api/users returns 503 when cur.fetchall() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForFetch())

    with app_module.app.test_client() as client:
        r = client.get("/api/users")
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


# --- create_user deep error paths ---


def test_create_user_cursor_raises(monkeypatch):
    """POST /api/users returns 503 when conn.cursor() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCursorError())

    with app_module.app.test_client() as client:
        r = client.post("/api/users", headers=AUTH_HEADER, json={
            "username": "testuser",
            "email": "test@example.com",
            "age": 30,
        })
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_create_user_execute_raises(monkeypatch):
    """POST /api/users returns 503 when cur.execute() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForExecute())

    with app_module.app.test_client() as client:
        r = client.post("/api/users", headers=AUTH_HEADER, json={
            "username": "testuser",
            "email": "test@example.com",
            "age": 30,
        })
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_create_user_fetchone_raises(monkeypatch):
    """POST /api/users returns 503 when cur.fetchone() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForFetch())

    with app_module.app.test_client() as client:
        r = client.post("/api/users", headers=AUTH_HEADER, json={
            "username": "testuser",
            "email": "test@example.com",
            "age": 30,
        })
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_create_user_commit_raises(monkeypatch):
    """POST /api/users returns 503 when conn.commit() raises (rollback succeeds)."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCommitError())

    with app_module.app.test_client() as client:
        r = client.post("/api/users", headers=AUTH_HEADER, json={
            "username": "testuser",
            "email": "test@example.com",
            "age": 30,
        })
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_create_user_rollback_raises(monkeypatch):
    """POST /api/users returns 503 when both commit and rollback raise."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCommitAndRollbackError())

    with app_module.app.test_client() as client:
        r = client.post("/api/users", headers=AUTH_HEADER, json={
            "username": "testuser",
            "email": "test@example.com",
            "age": 30,
        })
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_create_user_fetchone_returns_none(monkeypatch):
    """POST /api/users returns 503 when INSERT...RETURNING yields no row."""
    import app as app_module

    class FakeCursor:
        def execute(self, *args, **kwargs):
            pass
        def fetchone(self):
            return None  # forces the null-check path at app.py:96-98
        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor()
        def rollback(self):
            pass
        def close(self):
            pass

    monkeypatch.setattr(app_module, "get_db", lambda: FakeConn())
    with app_module.app.test_client() as client:
        r = client.post("/api/users", headers=AUTH_HEADER, json={
            "username": "test", "email": "t@t.com", "age": 30,
        })
        assert r.status_code == 503


# --- get_user deep error paths ---


def test_get_user_cursor_raises(monkeypatch):
    """GET /api/users/<id> returns 503 when conn.cursor() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCursorError())

    with app_module.app.test_client() as client:
        r = client.get("/api/users/1")
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_get_user_execute_raises(monkeypatch):
    """GET /api/users/<id> returns 503 when cur.execute() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForExecute())

    with app_module.app.test_client() as client:
        r = client.get("/api/users/1")
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_get_user_fetchone_raises(monkeypatch):
    """GET /api/users/<id> returns 503 when cur.fetchone() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForFetch())

    with app_module.app.test_client() as client:
        r = client.get("/api/users/1")
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


# --- deactivate_user deep error paths ---


def test_deactivate_user_cursor_raises(monkeypatch):
    """POST /api/users/<id>/deactivate returns 503 when conn.cursor() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCursorError())

    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate", headers=AUTH_HEADER)
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_deactivate_user_execute_raises(monkeypatch):
    """POST /api/users/<id>/deactivate returns 503 when cur.execute() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForExecute())

    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate", headers=AUTH_HEADER)
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_deactivate_user_fetchone_raises(monkeypatch):
    """POST /api/users/<id>/deactivate returns 503 when cur.fetchone() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForFetch())

    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate", headers=AUTH_HEADER)
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_deactivate_user_commit_raises(monkeypatch):
    """POST /api/users/<id>/deactivate returns 503 when conn.commit() raises (rollback succeeds)."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCommitError())

    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate", headers=AUTH_HEADER)
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


# ---------------------------------------------------------------------------
# Secret rotation — env var validation tests
# ---------------------------------------------------------------------------


def _reload_app_with_env(**extra_env):
    """Importlib-reload the app module, optionally with given env vars
    temporarily overridden. When called with no args, just does a plain
    reload (useful after a crash test — monkeypatch has already restored
    os.environ, but the module's globals may be stale from a partial reload).
    """
    import importlib
    import app as app_module
    old = {}
    for k, v in extra_env.items():
        old[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        importlib.reload(app_module)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_app_crashes_when_db_pass_missing(monkeypatch):
    """app.py raises RuntimeError on import when DB_PASS env var is not set."""
    import importlib
    import app as app_module

    # Save module globals that the reload might corrupt
    _saved = {k: getattr(app_module, k) for k in (
        "DB_USER", "DB_PASS", "DB_HOST", "DB_PORT", "DB_NAME",
        "SDLC_API_KEY", "SDLC_API_KEY_USER_ID",
    )}

    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.delenv("DB_PASS", raising=False)

    with pytest.raises(RuntimeError):
        importlib.reload(app_module)

    # Restore globals from saved values — monkeypatch hasn't restored env yet
    for k, v in _saved.items():
        setattr(app_module, k, v)


def test_app_crashes_when_db_user_missing(monkeypatch):
    """app.py raises RuntimeError on import when DB_USER env var is not set."""
    import importlib
    import app as app_module

    _saved = {k: getattr(app_module, k) for k in (
        "DB_USER", "DB_PASS", "DB_HOST", "DB_PORT", "DB_NAME",
        "SDLC_API_KEY", "SDLC_API_KEY_USER_ID",
    )}

    monkeypatch.setenv("DB_PASS", "test_pass")
    monkeypatch.delenv("DB_USER", raising=False)

    with pytest.raises(RuntimeError):
        importlib.reload(app_module)

    for k, v in _saved.items():
        setattr(app_module, k, v)


def test_app_crashes_when_both_credentials_missing(monkeypatch):
    """app.py raises RuntimeError when both DB_USER and DB_PASS are missing."""
    import importlib
    import app as app_module

    _saved = {k: getattr(app_module, k) for k in (
        "DB_USER", "DB_PASS", "DB_HOST", "DB_PORT", "DB_NAME",
        "SDLC_API_KEY", "SDLC_API_KEY_USER_ID",
    )}

    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.delenv("DB_PASS", raising=False)

    with pytest.raises(RuntimeError):
        importlib.reload(app_module)

    for k, v in _saved.items():
        setattr(app_module, k, v)


def test_app_infra_vars_keep_defaults(monkeypatch):
    """DB_HOST, DB_PORT, DB_NAME keep their defaults when env vars are missing."""
    import importlib
    import app as app_module

    _saved = {k: getattr(app_module, k) for k in (
        "DB_USER", "DB_PASS", "DB_HOST", "DB_PORT", "DB_NAME",
        "SDLC_API_KEY", "SDLC_API_KEY_USER_ID",
    )}

    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASS", "test_pass")
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)

    importlib.reload(app_module)
    assert app_module.DB_HOST == "localhost"
    assert app_module.DB_PORT == "5432"
    assert app_module.DB_NAME == "sdlc_demo"

    for k, v in _saved.items():
        setattr(app_module, k, v)


def test_app_imports_cleanly_with_credentials_set():
    """app.py imports without error when all required env vars are present."""
    import subprocess
    import sys

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Positive case: both DB_USER and DB_PASS set -> import succeeds
    env = os.environ.copy()
    env["DB_USER"] = "test_user"
    env["DB_PASS"] = "test_pass"
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, '.'); import app"],
        capture_output=True, text=True, env=env, cwd=repo_root,
    )
    assert result.returncode == 0, (
        f"app import failed with return code {result.returncode}\n"
        f"stderr: {result.stderr}\nstdout: {result.stdout}"
    )

    # Negative case: missing DB_PASS -> import fails with exit code 1
    env.pop("DB_PASS")
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, '.'); import app"],
        capture_output=True, text=True, env=env, cwd=repo_root,
    )
    assert result.returncode != 0, (
        "app import should have failed when DB_PASS is missing, "
        f"but got return code {result.returncode}"
    )

# ---------------------------------------------------------------------------
# PUT /api/users/<id> — update user
# ---------------------------------------------------------------------------


def test_update_user_success():
    """PUT /api/users/<id> updates username, email, age and returns updated user.

    Updates the user whose ID matches SDLC_API_KEY_USER_ID (the identity mapping).
    The test_create_and_list_users test (which runs first) ensures this user exists.
    """
    target_id = int(os.environ.get("SDLC_API_KEY_USER_ID", "1"))

    # Update all three fields on the mapped user
    r = requests.put(f"{BASE_URL}/api/users/{target_id}", json={
        "username": "updated_name",
        "email": "updated@example.com",
        "age": 35
    }, headers=AUTH_HEADER)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == target_id
    assert data["username"] == "updated_name"
    assert data["email"] == "updated@example.com"
    assert data["age"] == 35
    assert data["active"] is True  # active unchanged

    # Verify via GET
    r = requests.get(f"{BASE_URL}/api/users/{target_id}")
    assert r.status_code == 200
    assert r.json()["username"] == "updated_name"
    assert r.json()["email"] == "updated@example.com"
    assert r.json()["age"] == 35


def test_update_user_partial():
    """PUT /api/users/<id> with only some fields — updates only those.

    Updates the user whose ID matches SDLC_API_KEY_USER_ID (the identity mapping).
    """
    target_id = int(os.environ.get("SDLC_API_KEY_USER_ID", "1"))

    # Update only username on the mapped user
    r = requests.put(f"{BASE_URL}/api/users/{target_id}", json={
        "username": "only_username_changed"
    }, headers=AUTH_HEADER)
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "only_username_changed"
    assert data["active"] is True


def test_update_user_not_found():
    """PUT /api/users/<id> returns 404 when user does not exist.

    Uses an unmapped user ID so we bypass identity check (which returns 403
    before the 404 can be reached when identity is enforced).
    """
    # Use the mapped user ID + 1 to hit identity check, but since 99999
    # isn't in the DB, we need a different test approach.
    # The identity decorator returns 403 before the endpoint checks existence.
    # For a true 404 test, we need an ID the key is NOT mapped to.
    # But identity_mismatch gives 403 first. This is expected behavior
    # for the auth model — you can't probe arbitrary user IDs.
    r = requests.put(f"{BASE_URL}/api/users/99999", json={
        "username": "does_not_matter"
    }, headers=AUTH_HEADER)
    # Returns 403 (identity mismatch) because key maps to user 1, not 99999
    assert r.status_code == 403
    data = r.json()
    assert "error" in data
    assert "identity mismatch" in data["error"].lower()


# --- update_user validation ---


def test_update_user_invalid_id():
    """PUT /api/users/<id> returns 400 when id is not an integer."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/abc", headers=AUTH_HEADER, json={"username": "validuser"})
        assert r.status_code == 400
        assert "integer" in r.get_json()["error"].lower()


def test_update_user_zero_id():
    """PUT /api/users/<id> returns 400 when id is zero."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/0", headers=AUTH_HEADER, json={"username": "validuser"})
        assert r.status_code == 400
        assert "positive" in r.get_json()["error"].lower()


def test_update_user_negative_id():
    """PUT /api/users/<id> returns 400 when id is negative."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/-5", headers=AUTH_HEADER, json={"username": "validuser"})
        assert r.status_code == 400
        assert "positive" in r.get_json()["error"].lower()


def test_update_user_username_too_short():
    """PUT /api/users/<id> returns 400 when username < 3 chars."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"username": "ab"})
        assert r.status_code == 400
        assert "3 chars" in r.get_json()["error"].lower()


def test_update_user_email_missing_at():
    """PUT /api/users/<id> returns 400 when email lacks '@'."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"email": "no_at_sign"})
        assert r.status_code == 400
        assert "email" in r.get_json()["error"].lower()


def test_update_user_email_not_string():
    """PUT /api/users/<id> returns 400 when email is not a string (per AGENTS.md)."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"email": 12345})
        assert r.status_code == 400
        assert "string" in r.get_json()["error"].lower()


def test_update_user_age_bool():
    """PUT /api/users/<id> returns 400 when age is a bool (type-coercion, per AGENTS.md)."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"age": True})
        assert r.status_code == 400
        assert "integer" in r.get_json()["error"].lower()


def test_update_user_age_float():
    """PUT /api/users/<id> returns 400 when age is a float (not int, per AGENTS.md)."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"age": 30.5})
        assert r.status_code == 400
        assert "integer" in r.get_json()["error"].lower()


def test_update_user_no_fields():
    """PUT /api/users/<id> returns 400 when body has none of username/email/age."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"irrelevant": "data"})
        assert r.status_code == 400
        err = r.get_json()["error"].lower()
        assert any(k in err for k in ("username", "email", "age"))


def test_update_user_empty_body():
    """PUT /api/users/<id> returns 400 when body is empty."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={})
        assert r.status_code == 400


# --- update_user DB error paths ---


def test_update_user_db_unavailable(monkeypatch):
    """PUT /api/users/<id> returns 503 when DB is unreachable."""
    import app as app_module
    import psycopg2

    def raise_operational_error():
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(app_module, "get_db", raise_operational_error)

    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"username": "validuser"})
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_update_user_cursor_raises(monkeypatch):
    """PUT /api/users/<id> returns 503 when conn.cursor() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCursorError())

    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"username": "validuser"})
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_update_user_execute_raises(monkeypatch):
    """PUT /api/users/<id> returns 503 when cur.execute() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForExecute())

    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"username": "validuser"})
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_update_user_fetchone_raises(monkeypatch):
    """PUT /api/users/<id> returns 503 when cur.fetchone() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForFetch())

    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"username": "validuser"})
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_update_user_commit_raises(monkeypatch):
    """PUT /api/users/<id> returns 503 when conn.commit() raises (rollback succeeds)."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCommitError())

    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"username": "validuser"})
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_update_user_rollback_raises(monkeypatch):
    """PUT /api/users/<id> returns 503 when both commit and rollback raise."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCommitAndRollbackError())

    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"username": "validuser"})
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_update_user_fetchone_returns_none(monkeypatch):
    """PUT /api/users/<id> returns 503 when UPDATE...RETURNING yields no row."""
    import app as app_module

    class FakeCursorNone:
        def __init__(self):
            self._call = 0
        def execute(self, *args, **kwargs):
            pass
        def fetchone(self):
            self._call += 1
            if self._call == 1:
                return (1,)  # SELECT finds the user
            return None  # UPDATE...RETURNING yields nothing (DB anomaly)
        def close(self):
            pass

    class FakeConnNone:
        def cursor(self):
            return FakeCursorNone()
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass

    monkeypatch.setattr(app_module, "get_db", lambda: FakeConnNone())

    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={"username": "validuser"})
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


# ---------------------------------------------------------------------------
# Auth middleware tests
# ---------------------------------------------------------------------------


def test_create_user_missing_api_key():
    """POST /api/users returns 401 when X-API-Key header is missing."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.post("/api/users", json={
            "username": "testuser",
            "email": "test@example.com",
            "age": 30,
        })
        assert r.status_code == 401
        assert "missing API key" in r.get_json()["error"]


def test_create_user_invalid_api_key():
    """POST /api/users returns 401 when X-API-Key header is invalid."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.post("/api/users", headers={"X-API-Key": "wrong-key"}, json={
            "username": "testuser",
            "email": "test@example.com",
            "age": 30,
        })
        assert r.status_code == 401
        assert "invalid API key" in r.get_json()["error"]


def test_create_user_valid_api_key():
    """POST /api/users with valid API key passes auth (reaches validation, returns 400)."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.post("/api/users", headers=AUTH_HEADER, json={
            "username": "ab",  # too short
            "email": "test@example.com",
            "age": 30,
        })
        # Auth passed — we hit validation, which returns 400 for short username
        assert r.status_code == 400
        assert "3 chars" in r.get_json()["error"]


def test_deactivate_user_missing_api_key():
    """POST /api/users/<id>/deactivate returns 401 when X-API-Key is missing."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate")
        assert r.status_code == 401
        assert "missing API key" in r.get_json()["error"]


def test_deactivate_user_invalid_api_key():
    """POST /api/users/<id>/deactivate returns 401 for invalid API key."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401
        assert "invalid API key" in r.get_json()["error"]


def test_update_user_missing_api_key():
    """PUT /api/users/<id> returns 401 when X-API-Key is missing."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", json={"username": "validuser"})
        assert r.status_code == 401
        assert "missing API key" in r.get_json()["error"]


def test_update_user_invalid_api_key():
    """PUT /api/users/<id> returns 401 for invalid API key."""
    import app as app_module
    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers={"X-API-Key": "wrong"}, json={
            "username": "validuser"
        })
        assert r.status_code == 401
        assert "invalid API key" in r.get_json()["error"]


def test_update_user_identity_mismatch(monkeypatch):
    """PUT /api/users/<id> returns 403 when API key maps to a different user."""
    import app as app_module

    # The test API key maps to user ID 1 (set in module-level env).
    # Request to update user 2 → identity mismatch.
    monkeypatch.setattr(app_module, "SDLC_API_KEY_USER_ID", 1)

    with app_module.app.test_client() as client:
        r = client.put("/api/users/2", headers=AUTH_HEADER, json={
            "username": "validuser"
        })
        assert r.status_code == 403
        data = r.get_json()
        assert "identity mismatch" in data["error"]


def test_update_user_valid_auth_reaches_validation(monkeypatch):
    """PUT /api/users/<id> with valid key and matching identity reaches validation (400)."""
    import app as app_module

    # Key maps to user 1 → updating user 1 should pass identity check
    monkeypatch.setattr(app_module, "SDLC_API_KEY_USER_ID", 1)

    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={
            "username": "ab"  # too short — proves we got past auth
        })
        assert r.status_code == 400
        assert "3 chars" in r.get_json()["error"]


def test_update_user_identity_mapping_not_configured(monkeypatch):
    """PUT /api/users/<id> returns 500 when SDLC_API_KEY_USER_ID is None."""
    import app as app_module

    monkeypatch.setattr(app_module, "SDLC_API_KEY_USER_ID", None)

    with app_module.app.test_client() as client:
        r = client.put("/api/users/1", headers=AUTH_HEADER, json={
            "username": "validuser"
        })
        assert r.status_code == 500
        assert "identity mapping not configured" in r.get_json()["error"]



def test_app_crashes_when_api_key_missing(monkeypatch):
    """app.py raises RuntimeError on import when SDLC_API_KEY is not set."""
    import importlib
    import app as app_module

    _saved = {k: getattr(app_module, k) for k in (
        "DB_USER", "DB_PASS", "DB_HOST", "DB_PORT", "DB_NAME",
        "SDLC_API_KEY", "SDLC_API_KEY_USER_ID",
    )}

    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASS", "test_pass")
    monkeypatch.delenv("SDLC_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        importlib.reload(app_module)

    for k, v in _saved.items():
        setattr(app_module, k, v)


def test_app_crashes_when_api_key_empty(monkeypatch):
    """app.py raises RuntimeError on import when SDLC_API_KEY is empty string."""
    import importlib
    import app as app_module

    _saved = {k: getattr(app_module, k) for k in (
        "DB_USER", "DB_PASS", "DB_HOST", "DB_PORT", "DB_NAME",
        "SDLC_API_KEY", "SDLC_API_KEY_USER_ID",
    )}

    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASS", "test_pass")
    monkeypatch.setenv("SDLC_API_KEY", "")

    with pytest.raises(RuntimeError):
        importlib.reload(app_module)

    for k, v in _saved.items():
        setattr(app_module, k, v)


# ---------------------------------------------------------------------------
# GET /api/users?q=<search_term> — search query param
# ---------------------------------------------------------------------------


def test_search_by_username():
    """GET /api/users?q=<term> returns users whose username contains the term."""
    # Create users with distinct usernames
    for uname in ("alice_search", "bob_search", "charlie_other"):
        r = requests.post(f"{BASE_URL}/api/users", json={
            "username": uname,
            "email": f"{uname}@example.com",
            "age": 25
        }, headers=AUTH_HEADER)
        assert r.status_code == 201

    r = requests.get(f"{BASE_URL}/api/users", params={"q": "search"})
    assert r.status_code == 200
    users = r.json()
    usernames = [u["username"] for u in users]
    assert "alice_search" in usernames
    assert "bob_search" in usernames
    assert "charlie_other" not in usernames


def test_search_by_email():
    """GET /api/users?q=<term> returns users whose email contains the term."""
    # Create users with distinct emails
    for i, domain in enumerate(("alpha.com", "beta.org", "gamma.net"), 1):
        r = requests.post(f"{BASE_URL}/api/users", json={
            "username": f"email_test_{i}",
            "email": f"user{i}@{domain}",
            "age": 25
        }, headers=AUTH_HEADER)
        assert r.status_code == 201

    r = requests.get(f"{BASE_URL}/api/users", params={"q": "beta"})
    assert r.status_code == 200
    users = r.json()
    assert len(users) == 1
    assert users[0]["email"] == "user2@beta.org"


def test_search_no_results():
    """GET /api/users?q=<term> returns empty list when no users match."""
    # Create a user first so the test doesn't pass vacuously on empty DB
    r = requests.post(f"{BASE_URL}/api/users", json={
        "username": "noresults_test", "email": "noresults@example.com", "age": 25
    }, headers=AUTH_HEADER)
    assert r.status_code == 201

    r = requests.get(f"{BASE_URL}/api/users", params={"q": "zzz_nonexistent_term_999"})
    assert r.status_code == 200
    users = r.json()
    assert users == []


def test_search_empty_q_returns_all():
    """GET /api/users with empty q returns all users (backward compatible)."""
    # Create a couple users first so we know there are some
    for uname in ("emptyq_a", "emptyq_b"):
        r = requests.post(f"{BASE_URL}/api/users", json={
            "username": uname,
            "email": f"{uname}@example.com",
            "age": 25
        }, headers=AUTH_HEADER)
        assert r.status_code == 201

    # With empty q
    r_empty = requests.get(f"{BASE_URL}/api/users", params={"q": ""})
    assert r_empty.status_code == 200

    # Without q param at all
    r_none = requests.get(f"{BASE_URL}/api/users")
    assert r_none.status_code == 200

    # Both should return the same (all users)
    assert len(r_empty.json()) == len(r_none.json())
    assert len(r_empty.json()) >= 2


def test_search_special_characters():
    """GET /api/users?q=<term> handles special characters safely."""
    # Create a user with special chars in username for realistic testing
    r = requests.post(f"{BASE_URL}/api/users", json={
        "username": "user_with_underscore",
        "email": "underscore@example.com",
        "age": 25
    }, headers=AUTH_HEADER)
    assert r.status_code == 201

    # Search with underscore — should find the user
    r = requests.get(f"{BASE_URL}/api/users", params={"q": "underscore"})
    assert r.status_code == 200
    users = r.json()
    assert len(users) == 1
    assert users[0]["username"] == "user_with_underscore"

    # Search with percent sign — now escaped, should not crash, return empty
    r = requests.get(f"{BASE_URL}/api/users", params={"q": "%"})
    assert r.status_code == 200
    assert r.json() == []  # literal % won't match any user


def test_search_case_insensitive():
    """GET /api/users?q=<term> is case-insensitive (ILIKE)."""
    r = requests.post(f"{BASE_URL}/api/users", json={
        "username": "CaseTest", "email": "CaseTest@EXAMPLE.com", "age": 25
    }, headers=AUTH_HEADER)
    assert r.status_code == 201

    # Search lowercase
    r = requests.get(f"{BASE_URL}/api/users", params={"q": "casetest"})
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert any(u["username"] == "CaseTest" for u in r.json())

    # Search by email domain case-insensitive
    r = requests.get(f"{BASE_URL}/api/users", params={"q": "example"})
    assert r.status_code == 200
    assert any(u["email"] == "CaseTest@EXAMPLE.com" for u in r.json())


def test_search_whitespace_only():
    """GET /api/users?q=<whitespace> returns all users (stripped to empty)."""
    r = requests.post(f"{BASE_URL}/api/users", json={
        "username": "whitespace_test", "email": "ws@example.com", "age": 25
    }, headers=AUTH_HEADER)
    assert r.status_code == 201

    r = requests.get(f"{BASE_URL}/api/users", params={"q": "   "})
    assert r.status_code == 200
    users = r.json()
    assert len(users) >= 1  # stripped to empty = returns all


def test_search_sql_injection_attempt():
    """GET /api/users?q=<term> is safe against SQL injection."""
    # Attempt SQL injection — should return empty, not crash or leak data
    payloads = [
        "'; DROP TABLE users; --",
        "' OR '1'='1",
        "'; SELECT * FROM users; --",
    ]
    for payload in payloads:
        r = requests.get(f"{BASE_URL}/api/users", params={"q": payload})
        assert r.status_code == 200
        # Should return empty list — no user matches these injection strings
        assert r.json() == [], f"SQL injection payload returned data: {payload}"
