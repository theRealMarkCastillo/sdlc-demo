# API Reference

Flask + PostgreSQL REST API with API key authentication and identity-based access control.

## Authentication

All mutating endpoints (`POST`, `PUT`, `DELETE`) require an `X-API-Key` header set to the value of the `SDLC_API_KEY` environment variable.

- **Missing key** → `401 {"error": "missing API key"}`
- **Invalid key** → `401 {"error": "invalid API key"}`

**Identity check:** `PUT /api/users/<id>` additionally verifies the caller's key is mapped to the target user via `SDLC_API_KEY_USER_ID`. Updating another user's record returns `403 {"error": "identity mismatch — you can only update your own user"}`.

GET endpoints (`/health`, `/api/users`, `/api/users/<id>`) are public.

## Endpoints

| Method | Path | Auth | Success | Errors |
|--------|------|------|---------|--------|
| GET | `/health` | no | 200 | 500 (DB down) |
| GET | `/api/users` | no | 200 (array) | 503 |
| POST | `/api/users` | yes | 201 | 400, 401, 503 |
| GET | `/api/users/<id>` | no | 200 | 400, 404, 503 |
| POST | `/api/users/<id>/deactivate` | yes | 200 | 400, 401, 404, 503 |
| PUT | `/api/users/<id>` | yes | 200 | 400, 401, 403, 404, 503 |

## Request/Response Examples

### GET /health
```bash
curl http://localhost:5001/health
# {"db":"connected","status":"healthy"}
```

### POST /api/users (with auth)
```bash
curl -X POST http://localhost:5001/api/users \
  -H "X-API-Key: $SDLC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","age":30}'
# 201 {"age":30,"email":"alice@example.com","id":1,"username":"alice"}
```

### POST /api/users (without auth)
```bash
curl -X POST http://localhost:5001/api/users \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","age":30}'
# 401 {"error":"missing API key"}
```

### GET /api/users
```bash
curl http://localhost:5001/api/users
# [{"active":true,"age":30,"email":"alice@example.com","id":1,"username":"alice"}, ...]
```

### GET /api/users/1
```bash
curl http://localhost:5001/api/users/1
# {"active":true,"age":30,"email":"alice@example.com","id":1,"username":"alice"}
```

### GET /api/users/abc (invalid ID)
```bash
curl http://localhost:5001/api/users/abc
# 400 {"error":"id must be an integer"}
```

### GET /api/users/0 (non-positive)
```bash
curl http://localhost:5001/api/users/0
# 400 {"error":"id must be a positive integer"}
```

### GET /api/users/99999 (not found)
```bash
curl http://localhost:5001/api/users/99999
# 404 {"error":"user not found"}
```

### POST /api/users/1/deactivate
```bash
curl -X POST http://localhost:5001/api/users/1/deactivate \
  -H "X-API-Key: $SDLC_API_KEY"
# 200 {"active":false,"email":"alice@example.com","id":1,"username":"alice","age":30}
```

### POST /api/users/1/deactivate (already inactive — idempotent)
```bash
# Returns 200, same response. Deactivating twice is safe.
```

### PUT /api/users/1 (update — identity match)
```bash
curl -X PUT http://localhost:5001/api/users/1 \
  -H "X-API-Key: $SDLC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice_updated"}'
# 200 {"active":true,"age":30,"email":"alice@example.com","id":1,"username":"alice_updated"}
```

### PUT /api/users/2 (identity mismatch)
```bash
curl -X PUT http://localhost:5001/api/users/2 \
  -H "X-API-Key: $SDLC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username":"hacker"}'
# 403 {"error":"identity mismatch — you can only update your own user"}
```

### PUT /api/users/1 (partial update — email only)
```bash
curl -X PUT http://localhost:5001/api/users/1 \
  -H "X-API-Key: $SDLC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"newemail@example.com"}'
# 200 — only email changed, username and age unchanged
```

### PUT /api/users/1 (validation error)
```bash
curl -X PUT http://localhost:5001/api/users/1 \
  -H "X-API-Key: $SDLC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"age":true}'
# 400 {"error":"age must be an integer"}
```

## Error Format

All errors return `{"error": "human-readable message"}`.

| Status | Meaning |
|--------|---------|
| 200 | Success (or idempotent no-op) |
| 201 | Created |
| 400 | Invalid input (bad ID, validation failed, empty body, bool-as-int) |
| 401 | Missing or invalid API key |
| 403 | Identity mismatch (tried to update another user) |
| 404 | Resource not found |
| 500 | Identity mapping not configured (server config error) |
| 503 | Database unavailable |

## Validation Rules

- **username:** string, ≥3 characters
- **email:** string, must contain `@`
- **age:** integer only — booleans and floats rejected (type-coercion guard per AGENTS.md)
- **id:** positive integer (auto-increment keys start at 1)
- **PUT body:** at least one of username, email, age required
