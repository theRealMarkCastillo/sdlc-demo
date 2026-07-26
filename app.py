"""SDLC Demo App — a minimal Flask + PostgreSQL API."""

import os
from functools import wraps

import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "sdlc_demo")
try:
    DB_USER = os.environ["DB_USER"]
    DB_PASS = os.environ["DB_PASS"]
except KeyError as e:
    raise RuntimeError(
        f"Missing required environment variable: {e.args[0]}. "
        f"Copy .env.example to .env and fill in real values."
    ) from e

if not DB_USER or not DB_PASS:
    raise RuntimeError(
        "DB_USER and DB_PASS must be non-empty. "
        "Check your .env file — values may be blank."
    )

# --- Auth config ---

try:
    SDLC_API_KEY = os.environ["SDLC_API_KEY"]
except KeyError as e:
    raise RuntimeError(
        f"Missing required environment variable: {e.args[0]}. "
        f"Set it to a secure random string for API authentication."
    ) from e

if not SDLC_API_KEY:
    raise RuntimeError(
        "SDLC_API_KEY must be non-empty. "
        "Check your .env file — the value may be blank."
    )

# Key → user_id mapping for identity checks on user-scoped endpoints.
# Set SDLC_API_KEY_USER_ID to the user ID associated with SDLC_API_KEY.
# Falls back to None (identity checks disabled) when unset.
_API_KEY_USER_ID_RAW = os.environ.get("SDLC_API_KEY_USER_ID", "")
SDLC_API_KEY_USER_ID = int(_API_KEY_USER_ID_RAW) if _API_KEY_USER_ID_RAW else None


# --- Auth decorators ---

def require_api_key(f):
    """Decorator: require valid X-API-Key header. Returns 401 if missing/invalid."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return jsonify({"error": "missing API key"}), 401
        if api_key != SDLC_API_KEY:
            return jsonify({"error": "invalid API key"}), 401
        return f(*args, **kwargs)
    return decorated


def require_identity_match(f):
    """Decorator: require caller's API key identity matches the target user_id.

    Must be stacked inside @require_api_key. Uses SDLC_API_KEY_USER_ID
    to verify the authenticated caller owns the resource being modified.
    Returns 403 on identity mismatch, 500 if mapping is not configured.

    Non-integer, zero, and negative IDs pass through to the endpoint
    for proper validation — identity is only enforced for valid user IDs.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = kwargs.get("user_id")
        if SDLC_API_KEY_USER_ID is None:
            return jsonify(
                {"error": "API key identity mapping not configured"}
            ), 500
        try:
            uid = int(user_id)  # type: ignore[arg-type]  # caught by ValueError below
        except (ValueError, TypeError):
            # Non-integer — let endpoint handle validation
            return f(*args, **kwargs)
        if uid <= 0:
            # Zero or negative — let endpoint handle validation
            return f(*args, **kwargs)
        if SDLC_API_KEY_USER_ID != uid:
            return jsonify(
                {"error": "identity mismatch — you can only update your own user"}
            ), 403
        return f(*args, **kwargs)
    return decorated


# --- Database ---

def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS
    )


# --- Endpoints ---

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
    """Return users, optionally filtered by a search term.

    Query params:
        q (str, optional): Case-insensitive search term matched against
            username and email via ILIKE with surrounding wildcards.
            When missing or empty, returns all users.

    Returns:
        JSON list of user objects matching the (optional) filter.
    """
    q = request.args.get("q", "")
    # Strip whitespace and cap length to prevent resource exhaustion
    q = q.strip()[:200]
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        if q:
            # Escape LIKE wildcards so user input isn't misinterpreted
            safe_q = q.replace("%", r"\%").replace("_", r"\_")
            pattern = f"%{safe_q}%"
            cur.execute(
                "SELECT id, username, email, age, active FROM users "
                "WHERE (username ILIKE %s OR email ILIKE %s) ORDER BY id",
                (pattern, pattern)
            )
        else:
            cur.execute(
                "SELECT id, username, email, age, active FROM users ORDER BY id"
            )
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
@require_api_key
def create_user():
    data = request.get_json() or {}
    username = data.get("username", "")
    email = data.get("email", "")
    age = data.get("age", 0)

    if not username or len(username) < 3:
        return jsonify({"error": "username must be at least 3 chars"}), 400
    if not isinstance(email, str):
        return jsonify({"error": "email must be a string"}), 400
    if "@" not in email:
        return jsonify({"error": "invalid email"}), 400
    if isinstance(age, bool) or type(age) is not int:
        return jsonify({"error": "age must be an integer"}), 400

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
@require_api_key
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


@app.route("/api/users/<user_id>", methods=["PUT"])
@require_api_key
@require_identity_match
def update_user(user_id: str):
    """Update an existing user's username, email, and/or age.

    Args:
        user_id: The user ID from the URL path.

    Returns:
        JSON updated user object on success, or error response.
    """
    # Validate id is a valid integer at the API boundary
    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        return jsonify({"error": "id must be an integer"}), 400

    # Reject non-positive IDs (auto-increment primary keys start at 1)
    if uid <= 0:
        return jsonify({"error": "id must be a positive integer"}), 400

    data = request.get_json() or {}

    # At least one updatable field must be present
    if not any(k in data for k in ("username", "email", "age")):
        return jsonify(
            {"error": "at least one of username, email, age required"}
        ), 400

    # Validate username if present — must be a string >= 3 chars
    username = data.get("username")
    if username is not None:
        if not isinstance(username, str) or len(username) < 3:
            return jsonify({"error": "username must be at least 3 chars"}), 400

    # Validate email if present — must be a string and contain '@'
    email = data.get("email")
    if email is not None:
        if not isinstance(email, str):
            return jsonify({"error": "email must be a string"}), 400
        if "@" not in email:
            return jsonify({"error": "invalid email"}), 400

    # Validate age if present — must be int and not bool (per AGENTS.md type-coercion)
    age = data.get("age")
    if age is not None:
        if isinstance(age, bool) or type(age) is not int:
            return jsonify({"error": "age must be an integer"}), 400

    # Build dynamic SET clause
    set_clauses: list[str] = []
    values: list[object] = []
    if username is not None:
        set_clauses.append("username = %s")
        values.append(username)
    if email is not None:
        set_clauses.append("email = %s")
        values.append(email)
    if age is not None:
        set_clauses.append("age = %s")
        values.append(age)

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        # Phase 1: check existence — 404 if user doesn't exist
        cur.execute("SELECT id FROM users WHERE id = %s", (uid,))
        if cur.fetchone() is None:
            return jsonify({"error": "user not found"}), 404

        # Phase 2: UPDATE ... RETURNING — column names from our code, values parameterized
        cur.execute(  # nosec B608
            f"UPDATE users SET {', '.join(set_clauses)} WHERE id = %s "
            f"RETURNING id, username, email, age, active",
            values + [uid]
        )
        row = cur.fetchone()
        conn.commit()
    except psycopg2.Error as e:
        app.logger.error(
            "DB error in update_user: %s [%s]",
            type(e).__name__, getattr(e, 'pgcode', 'N/A')
        )
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

    # Phase 3: UPDATE...RETURNING yielded no row — DB anomaly
    if row is None:
        return jsonify({"error": "database unavailable"}), 503

    return jsonify({
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "age": row[3],
        "active": row[4],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
