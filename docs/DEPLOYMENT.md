# Deployment Guide

This project supports two environments via Docker Compose: **staging** and **production**.

## Architecture

| Component | Staging | Production |
|-----------|---------|------------|
| App | `sdlc-staging-app-1` (port 5001) | `sdlc-prod-app-1` (port 5002) |
| DB | `sdlc-staging-db-1` (port 5433) | `sdlc-prod-db-1` (port 5434) |
| Volume | `sdlc-staging_pgdata` | `sdlc-prod_pgdata` |
| Image | `sdlc-demo-app:latest` | `sdlc-demo-app:latest` |

The two environments use different Docker Compose project names (`-p sdlc-staging`, `-p sdlc-prod`) so they can coexist on the same host with separate networks, volumes, and ports.

## Bring up

```bash
# Staging
docker compose -f docker-compose.staging.yml -p sdlc-staging up -d --build

# Production
docker compose -f docker-compose.prod.yml -p sdlc-prod up -d --build
```

## Smoke tests

```bash
curl http://localhost:5001/health    # staging
curl http://localhost:5002/health    # production
```

Both should return `{"db":"connected","status":"healthy"}`.

## Tear down

```bash
docker compose -f docker-compose.staging.yml -p sdlc-staging down
docker compose -f docker-compose.prod.yml -p sdlc-prod down
# Add -v to also remove volumes:
docker compose -f docker-compose.prod.yml -p sdlc-prod down -v
```

## How Deploys Work in the SDLC Pipeline

The SDLC orchestrator handles deploys through the `sdlc-deploy` skill:

1. **Deploy to staging** via `docker compose -f docker-compose.staging.yml up -d --build`
2. **Smoke tests** via `curl` to health endpoint
3. **Human gate** — P0/P1 cards require Telegram approval before production deploy
4. **Deploy to production** via `docker compose -f docker-compose.prod.yml up -d --build`

The full pipeline state lives on the **Hermes kanban board** (board: `sdlc`).
