# sdlc-demo

A minimal Flask + PostgreSQL REST API for demonstrating the [Hermes SDLC system](../wiki/concepts/sdlc-architecture.md).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (DB connection) |
| GET | `/api/users` | List all users |
| POST | `/api/users` | Create a user |
| GET | `/api/users/<id>` | Get a single user by ID (SDLC-003) |

## Architecture

- **App:** Flask 3 + psycopg2
- **DB:** PostgreSQL 16
- **Deployment:** Docker Compose (separate staging and prod projects)
- **Tests:** pytest + requests against live staging endpoint

## Running locally

### Staging
```bash
docker compose -f docker-compose.staging.yml -p sdlc-staging up -d --build
curl http://localhost:5001/health
```

### Production
```bash
docker compose -f docker-compose.prod.yml -p sdlc-prod up -d --build
curl http://localhost:5002/health
```

The two compose files use different Docker project names (`-p sdlc-staging` / `-p sdlc-prod`), different volume names, and different host ports (5001 vs 5002) so they can coexist.

### Tests
```bash
pip install -r requirements.txt -r tests/requirements.txt
TEST_URL=http://localhost:5001 pytest tests/ -v
```

## History

This project was built incrementally through the SDLC pipeline:

| Card | Feature | Commit | Outcome |
|------|---------|--------|---------|
| SDLC-003 | GET /api/users/<id> | [3fac3d6](https://github.com/your-org/sdlc-demo) | First endpoint deployed |
| SDLC-003 retry 1 | Code quality fixes | [778c833](#) | Dead code removed, DB error handling |
| SDLC-003 retry 2 | Resource leak fix | [044d0dc](#) | finally block on cleanup |

## SDLC Integration

- **Board:** `hermes kanban` with `HERMES_KANBAN_BOARD=sdlc`
- **Profile:** `~/.hermes/profiles/sdlc-monitor/`
- **Project conventions:** See `AGENTS.md` (closed-loop rules from SDLC-001)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | localhost | Postgres host |
| `DB_PORT` | 5432 | Postgres port |
| `DB_NAME` | sdlc_demo | Database name |
| `DB_USER` | sdlc_user | Database user |
| `DB_PASS` | sdlc_pass | Database password |

These are injected by the Docker Compose files; no `.env` needed for local dev.
