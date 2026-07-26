"""SDLC Demo tests."""
import pytest
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
