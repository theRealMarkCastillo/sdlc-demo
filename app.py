"""SDLC Demo App — a minimal Flask + PostgreSQL API."""

import os
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "sdlc_demo")
DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]


def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS
    )


@app.route("/health")
def health():
    try:
        conn = get_db()
        conn.close()
        return jsonify({"status": "healthy", "db": "connected"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route("/api/users", methods=["GET"])
def list_users():
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, username, email, age, active FROM users ORDER BY id")
        rows = cur.fetchall()
    except psycopg2.Error as e:
        app.logger.error("DB error in list_users: %s [%s]", type(e).__name__, getattr(e, 'pgcode', 'N/A'))
        return jsonify({"error": "database unavailable"}), 503
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()
    return jsonify([
        {"id": r[0], "username": r[1], "email": r[2], "age": r[3], "active": r[4]}
        for r in rows
    ])


@app.route("/api/users", methods=["POST"])
def create_user():
    data = request.get_json() or {}
    username = data.get("username", "")
    email = data.get("email", "")
    age = data.get("age", 0)

    if not username or len(username) < 3:
        return jsonify({"error": "username must be at least 3 chars"}), 400
    if "@" not in email:
        return jsonify({"error": "invalid email"}), 400

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, email, age) VALUES (%s, %s, %s) RETURNING id",
            (username, email, age)
        )
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            return jsonify({"error": "database unavailable"}), 503
        user_id = row[0]
        conn.commit()
    except psycopg2.Error as e:
        app.logger.error("DB error in create_user: %s [%s]", type(e).__name__, getattr(e, 'pgcode', 'N/A'))
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return jsonify({"error": "database unavailable"}), 503
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()
    return jsonify({"id": user_id, "username": username, "email": email, "age": age}), 201


@app.route("/api/users/<user_id>", methods=["GET"])
def get_user(user_id: str):
    """Return a single user by ID.

    Args:
        user_id: The user ID from the URL path.

    Returns:
        JSON user object on success, or error response with appropriate status.
    """
    # Validate id is a valid integer at the API boundary
    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        return jsonify({"error": "id must be an integer"}), 400

    # Flask URL parameters are always str → int() always returns int.
    # The SDLC-001 type-coercion check (type(x) is not int) applies to
    # JSON-parsed inputs where bool can sneak in, not to URL path params.

    # Reject non-positive IDs (auto-increment primary keys start at 1)
    if uid <= 0:
        return jsonify({"error": "id must be a positive integer"}), 400

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, email, age, active FROM users WHERE id = %s",
            (uid,)
        )
        row = cur.fetchone()
    except psycopg2.Error as e:
        app.logger.error("DB error in get_user: %s [%s]", type(e).__name__, getattr(e, 'pgcode', 'N/A'))
        return jsonify({"error": "database unavailable"}), 503
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

    if row is None:
        return jsonify({"error": "user not found"}), 404

    return jsonify({
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "age": row[3],
        "active": row[4],
    })


@app.route("/api/users/<user_id>/deactivate", methods=["POST"])
def deactivate_user(user_id: str):
    """Deactivate a user by ID. Idempotent — deactivating an already-inactive user returns 200.

    Args:
        user_id: The user ID from the URL path.

    Returns:
        JSON user object with active=false on success, or error response.
    """
    # Validate id is a valid integer at the API boundary
    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        return jsonify({"error": "id must be an integer"}), 400

    # Reject non-positive IDs (auto-increment primary keys start at 1)
    if uid <= 0:
        return jsonify({"error": "id must be a positive integer"}), 400

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        # UPDATE ... RETURNING fetches the updated row in one round trip.
        # If no row matches, RETURNING yields nothing → cur.fetchone() is None.
        cur.execute(
            "UPDATE users SET active = %s WHERE id = %s "
            "RETURNING id, username, email, age, active",
            (False, uid)
        )
        row = cur.fetchone()
        conn.commit()
    except psycopg2.Error as e:
        app.logger.error("DB error in deactivate_user: %s [%s]", type(e).__name__, getattr(e, 'pgcode', 'N/A'))
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass  # connection dead, nothing to roll back
        return jsonify({"error": "database unavailable"}), 503
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

    if row is None:
        return jsonify({"error": "user not found"}), 404

    return jsonify({
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "age": row[3],
        "active": row[4],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
