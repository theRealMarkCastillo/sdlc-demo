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

BASE_URL = os.environ.get("TEST_URL", "http://localhost:5000")


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
    })
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
    })
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
    })
    assert r.status_code == 201
    user_id = r.json()["id"]

    # Deactivate the user
    r = requests.post(f"{BASE_URL}/api/users/{user_id}/deactivate")
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
    r = requests.post(f"{BASE_URL}/api/users/99999/deactivate")
    assert r.status_code == 404
    data = r.json()
    assert "error" in data
    assert "not found" in data["error"].lower()


def test_deactivate_user_invalid_id():
    """POST /api/users/<id>/deactivate returns 400 for non-integer id."""
    r = requests.post(f"{BASE_URL}/api/users/abc/deactivate")
    assert r.status_code == 400
    data = r.json()
    assert "error" in data
    assert "integer" in data["error"].lower()


def test_deactivate_user_zero_id():
    """POST /api/users/<id>/deactivate returns 400 for zero id."""
    r = requests.post(f"{BASE_URL}/api/users/0/deactivate")
    assert r.status_code == 400
    data = r.json()
    assert "error" in data
    assert "positive" in data["error"].lower()


def test_deactivate_user_negative_id():
    """POST /api/users/<id>/deactivate returns 400 for negative id."""
    r = requests.post(f"{BASE_URL}/api/users/-5/deactivate")
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
    })
    assert r.status_code == 201
    user_id = r.json()["id"]

    # First deactivate
    r = requests.post(f"{BASE_URL}/api/users/{user_id}/deactivate")
    assert r.status_code == 200
    assert r.json()["active"] is False

    # Second deactivate (idempotent)
    r = requests.post(f"{BASE_URL}/api/users/{user_id}/deactivate")
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
        r = client.post("/api/users/1/deactivate")
        assert r.status_code == 503
        data = r.get_json()
        assert data["error"] == "database unavailable"


def test_deactivate_user_rollback_raises(monkeypatch):
    """POST /api/users/<id>/deactivate returns 503 when both commit and rollback raise."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCommitAndRollbackError())

    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate")
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
        r = client.post("/api/users", json={
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
        r = client.post("/api/users", json={
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
        r = client.post("/api/users", json={
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
        r = client.post("/api/users", json={
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
        r = client.post("/api/users", json={
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
        r = client.post("/api/users", json={
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
        r = client.post("/api/users", json={
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
        r = client.post("/api/users/1/deactivate")
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_deactivate_user_execute_raises(monkeypatch):
    """POST /api/users/<id>/deactivate returns 503 when cur.execute() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForExecute())

    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate")
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_deactivate_user_fetchone_raises(monkeypatch):
    """POST /api/users/<id>/deactivate returns 503 when cur.fetchone() raises."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnForFetch())

    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate")
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


def test_deactivate_user_commit_raises(monkeypatch):
    """POST /api/users/<id>/deactivate returns 503 when conn.commit() raises (rollback succeeds)."""
    import app as app_module

    monkeypatch.setattr(app_module, "get_db", lambda: _FakeConnCommitError())

    with app_module.app.test_client() as client:
        r = client.post("/api/users/1/deactivate")
        assert r.status_code == 503
        assert r.get_json()["error"] == "database unavailable"


# ---------------------------------------------------------------------------
# Secret rotation — env var validation tests
# ---------------------------------------------------------------------------


def test_app_crashes_when_db_pass_missing(monkeypatch):
    """app.py raises KeyError on import when DB_PASS env var is not set."""
    import importlib
    import app as app_module

    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.delenv("DB_PASS", raising=False)

    with pytest.raises(RuntimeError):
        importlib.reload(app_module)


def test_app_crashes_when_db_user_missing(monkeypatch):
    """app.py raises KeyError on import when DB_USER env var is not set."""
    import importlib
    import app as app_module

    monkeypatch.setenv("DB_PASS", "test_pass")
    monkeypatch.delenv("DB_USER", raising=False)

    with pytest.raises(RuntimeError):
        importlib.reload(app_module)


def test_app_crashes_when_both_credentials_missing(monkeypatch):
    """app.py raises KeyError when both DB_USER and DB_PASS are missing."""
    import importlib
    import app as app_module

    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.delenv("DB_PASS", raising=False)

    with pytest.raises(RuntimeError):
        importlib.reload(app_module)


def test_app_infra_vars_keep_defaults(monkeypatch):
    """DB_HOST, DB_PORT, DB_NAME keep their defaults when env vars are missing."""
    import importlib
    import app as app_module

    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASS", "test_pass")
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)

    importlib.reload(app_module)
    assert app_module.DB_HOST == "localhost"
    assert app_module.DB_PORT == "5432"
    assert app_module.DB_NAME == "sdlc_demo"


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
