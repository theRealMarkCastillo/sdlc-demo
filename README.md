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

## Documentation

| Doc | What it covers |
|-----|----------------|
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | 8-node cycle, identity scopes, storage map, with diagrams |
| **[docs/INCIDENT-RESPONSE.md](docs/INCIDENT-RESPONSE.md)** | How monitor catches production issues and routes to fix |
| **[docs/REVIEW-PROCESS.md](docs/REVIEW-PROCESS.md)** | Multi-reviewer AND-gate, tiebreaker, retry protocol |
| **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** | Staging vs prod infrastructure, log pipeline, smoke tests |
| **[docs/API.md](docs/API.md)** | Endpoints, request/response examples |
| **[docs/SDLC-SYSTEM.md](docs/SDLC-SYSTEM.md)** | How this project fits into the SDLC pipeline |

## Endpoints

| Method | Path | Status |
|--------|------|--------|
| GET | `/health` | 200 if DB connected |
| GET | `/api/users` | 200, list |
| POST | `/api/users` | 201 created, 400 invalid |
| GET | `/api/users/<id>` | 200 found, 400 invalid/negative, 404 not found, 503 DB unavailable |

## Project Structure

```
sdlc-demo/
├── app.py                    # Flask app (~140 lines, single file for demo)
├── tests/test_api.py         # 7 tests, hits live staging
├── Dockerfile                # Python 3.12 + Flask + psycopg2
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
| `DB_HOST` | localhost | Postgres host |
| `DB_PORT` | 5432 | Postgres port |
| `DB_NAME` | sdlc_demo | Database name |
| `DB_USER` | sdlc_user | Database user |
| `DB_PASS` | sdlc_pass | Database password |

These are set in the docker-compose files; no `.env` needed for local development.

## Project Path

This repo lives at `~/git/sdlc-demo/`. The path is stored as the env var `SDLC_DEMO_PATH` in `~/.hermes/.env`. Cron jobs and subagent prompts use `${SDLC_DEMO_PATH}` for substitution.