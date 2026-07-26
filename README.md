# sdlc-demo

A minimal Flask + PostgreSQL REST API built end-to-end through the [Hermes SDLC system](docs/ARCHITECTURE.md). Used to demonstrate the multi-reviewer AND-gate, tiebreaker routing, closed-loop pattern edits, structured human gates via Telegram, and incident-response monitoring.

## Quick Start

```bash
# Staging (always available, used for testing)
docker compose -f docker-compose.staging.yml -p sdlc-staging up -d --build
curl http://localhost:5001/health

# Production (deployed via SDLC pipeline after human approval)
docker compose -f docker-compose.prod.yml -p sdlc-prod up -d --build
curl http://localhost:5002/health

# Tests
pip install -r requirements.txt -r tests/requirements.txt
TEST_URL=http://localhost:5001 pytest tests/ -v
```

## Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database migrations. Migrations run automatically in Docker via `entrypoint.sh` before the app starts.

### Local Development

Set `DATABASE_URL` to your local Postgres instance, then run migrations:

```bash
export DATABASE_URL=postgresql://sdlc_user:${DB_PASS}@localhost:5433/sdlc_demo
alembic upgrade head
```

### Creating New Migrations

```bash
alembic revision --autogenerate -m "description of change"
```

Review the generated migration script in `alembic/versions/`, then apply it:

```bash
alembic upgrade head
```

### Rolling Back

```bash
alembic downgrade -1   # revert last migration
alembic downgrade base  # revert all migrations
```

## Documentation

| Doc | What it covers |
|-----|----------------|
| **[docs/PLAN.md](docs/PLAN.md)** | Original design plan with 3 source citations and design decisions |
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | 8-node cycle, identity scopes, storage map, with diagrams |
| **[docs/INCIDENT-RESPONSE.md](docs/INCIDENT-RESPONSE.md)** | How monitor catches production issues and routes to fix |
| **[docs/REVIEW-PROCESS.md](docs/REVIEW-PROCESS.md)** | Multi-reviewer AND-gate, tiebreaker, retry protocol |
| **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** | Staging vs prod infrastructure, log pipeline, smoke tests |
| **[docs/API.md](docs/API.md)** | Endpoints, request/response examples |
| **[docs/SDLC-SYSTEM.md](docs/SDLC-SYSTEM.md)** | How this project fits into the SDLC pipeline |

## Endpoints

All mutating endpoints (POST, PUT, DELETE) require an `X-API-Key` header. GET endpoints are public.

| Method | Path | Status |
|--------|------|--------|
| GET | `/health` | 200 if DB connected |
| GET | `/api/users` | 200, list |
| POST | `/api/users` | 201 created, 401 no key, 400 invalid |
| GET | `/api/users/<id>` | 200 found, 400 invalid/negative, 404 not found, 503 DB unavailable |
| POST | `/api/users/<id>/deactivate` | 200 deactivated, 401 no key, 404 not found |
| PUT | `/api/users/<id>` | 200 updated, 401 no key, 403 identity mismatch, 404 not found |

### Authentication

All mutating endpoints require an `X-API-Key` header with the value of `SDLC_API_KEY`. Example:

```bash
curl -H "X-API-Key: your-api-key-here" -X POST http://localhost:5001/api/users \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "age": 30}'
```

**Identity check:** PUT `/api/users/<id>` additionally verifies that the caller's API key maps to the target user ID (via `SDLC_API_KEY_USER_ID`). You can only update your own user — attempting to update another user returns 403.

## Project Structure

```
sdlc-demo/
├── app.py                    # Flask app (~215 lines, single file for demo)
# tests/test_api.py         # 39 tests
├── Dockerfile                # Python 3.12 + Flask + psycopg2 + Alembic
├── entrypoint.sh             # Run migrations then start app
├── alembic.ini               # Alembic configuration
├── alembic/                  # Migration scripts
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── docker-compose.staging.yml # Project: sdlc-staging, port 5001
├── docker-compose.prod.yml    # Project: sdlc-prod, port 5002
├── AGENTS.md                 # Worker conventions, closed-loop rules
├── README.md                 # You are here
└── docs/                     # All project documentation
```

## SDLC Integration

This project was built by SDLC cards on the Hermes kanban board (`HERMES_KANBAN_BOARD=sdlc`):

| Card | Feature | Status |
|------|---------|--------|
| SDLC-001 | Input validation, type-coercion closed loop | Done |
| SDLC-002 | `update_user_email` helper, tiebreaker proven | Done |
| SDLC-003 | `GET /api/users/<id>` with retries | Done |
| SDLC-004 | Auto-created by monitor (test incident) | Done |
| SDLC-005 | Auto-created by monitor (recurrence dedup) | Done |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full pipeline state.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | Postgres connection string for Alembic |
| `DB_HOST` | localhost | Postgres host |
| `DB_PORT` | 5432 | Postgres port |
| `DB_NAME` | sdlc_demo | Database name |
| `DB_USER` | required — set in .env | Database user |
| `DB_PASS` | required — set in .env | Database password |
| `SDLC_API_KEY` | required — set in .env | API key for mutating endpoints |
| `SDLC_API_KEY_USER_ID` | 1 | User ID mapped to SDLC_API_KEY (for identity check on PUT) |

These are set in the docker-compose files; a `.env` file is required for local development — copy `.env.example` to `.env` and fill in values.

## Project Path

This repo lives at `~/git/sdlc-demo/`. The path is stored as the env var `SDLC_DEMO_PATH` in `~/.hermes/.env`. Cron jobs and subagent prompts use `${SDLC_DEMO_PATH}` for substitution.