"""SDLC Demo tests."""
import requests
import os

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
