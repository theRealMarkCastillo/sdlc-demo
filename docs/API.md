# API Reference

Auto-derived from `app.py` route decorators.

| Method | Path | Handler | DoD coverage |
|--------|------|---------|--------------|
| GET | `/health` | `health()` | DB connectivity check, used by deploy smoke tests |
| GET | `/api/users` | `list_users()` | List all users, returns JSON array |
| POST | `/api/users` | `create_user()` | Create user with input validation |
| GET | `/api/users/<user_id>` | `get_user()` | Single user lookup (SDLC-003, with validation) |

## Request/Response Examples

### GET /api/users/1 (success)
```bash
curl http://localhost:5001/api/users/1
# {"active":true,"age":30,"email":"alice@example.com","id":1,"username":"alice"}
```

### GET /api/users/abc (invalid ID)
```bash
curl http://localhost:5002/api/users/abc
# 400 {"error":"id must be an integer"}
```

### GET /api/users/0 (non-positive)
```bash
curl http://localhost:5001/api/users/0
# 400 {"error":"id must be a positive integer"}
```

### GET /api/users/99999 (not found)
```bash
curl http://localhost:5002/api/users/99999
# 404 {"error":"user not found"}
```

## Error Format

All errors return JSON with a single `error` field:

```json
{"error": "human-readable message"}
```

HTTP status codes used:
- `200` — success
- `201` — created
- `400` — invalid input (invalid type, validation failed)
- `404` — resource not found
- `503` — service unavailable (DB unreachable)
