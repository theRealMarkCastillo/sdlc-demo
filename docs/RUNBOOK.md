# Runbook

Operational procedures for the sdlc-demo project.

## Deploy

### Staging

```bash
cd ~/git/sdlc-demo
docker compose -f docker-compose.staging.yml -p sdlc-staging up -d --build
curl http://localhost:5001/health
```

### Production

```bash
docker compose -f docker-compose.prod.yml -p sdlc-prod up -d --build
curl http://localhost:5002/health
```

### Rollback

```bash
# Revert to previous commit
cd ~/git/sdlc-demo
git log --oneline -5  # find the last good commit
git revert <bad-commit-sha>
git push origin main

# Rebuild both environments
docker compose -f docker-compose.staging.yml -p sdlc-staging up -d --build
docker compose -f docker-compose.prod.yml -p sdlc-prod up -d --build
```

## Rotate Secrets

### Database credentials

1. Generate new passwords:
   ```bash
   openssl rand -hex 32  # for DB_PASS
   openssl rand -hex 32  # for POSTGRES_PASSWORD
   ```
2. Update `~/.hermes/.env` and `~/git/sdlc-demo/.env`
3. Rebuild with fresh volumes:
   ```bash
   cd ~/git/sdlc-demo
   docker compose -f docker-compose.staging.yml -p sdlc-staging down -v
   docker compose -f docker-compose.prod.yml -p sdlc-prod down -v
   docker compose -f docker-compose.staging.yml -p sdlc-staging up -d --build
   docker compose -f docker-compose.prod.yml -p sdlc-prod up -d --build
   ```
4. Verify: `curl http://localhost:5001/health && curl http://localhost:5002/health`
5. Open a kanban card: "secret rotation complete"

### API key

1. Generate: `openssl rand -hex 16`
2. Update `SDLC_API_KEY` in both `.env` files
3. Rebuild: `docker compose -f docker-compose.staging.yml -p sdlc-staging up -d --build`
4. Update any cron job env vars that reference the old key

## Restart the Monitor

The monitor runs as three cron jobs on the default profile. To restart:

```bash
# Check status
hermes cron list | grep sdlc

# If a job is paused
hermes cron resume <job_id>

# Trigger a manual run
hermes cron run <job_id>

# Check last run output
hermes cron log <job_id>

# Delete and recreate if broken
hermes cron remove <job_id>
# (then recreate with the same parameters)
```

## Recover from DB Password Mismatch

If `docker logs sdlc-prod-app-1` shows `FATAL: password authentication failed`:

```bash
cd ~/git/sdlc-demo

# Nuke and rebuild (fresh credentials from .env)
docker compose -f docker-compose.prod.yml -p sdlc-prod down -v
docker compose -f docker-compose.prod.yml -p sdlc-prod up -d --build
```

> This destroys production data. Only do this for a demo environment.

## Recover from Test Failures

If tests fail against staging after a deploy:

```bash
# Check staging health
curl http://localhost:5001/health

# Check logs
docker logs sdlc-staging-app-1 --tail 50

# Run specific failing tests
TEST_URL=http://localhost:5001 pytest tests/test_api.py::test_name -v

# If it's an auth issue, verify the API key
grep SDLC_API_KEY ~/git/sdlc-demo/.env
curl -X POST http://localhost:5001/api/users \
  -H "X-API-Key: $SDLC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"t@t.com","age":1}'
```

## Recover from Stale Kanban Cards

If a card is stuck in `blocked` or `ready` state:

```bash
# List all cards
HERMES_KANBAN_BOARD=sdlc hermes kanban list

# Show the stuck card
HERMES_KANBAN_BOARD=sdlc hermes kanban show <card_id>

# Unblock if needed
HERMES_KANBAN_BOARD=sdlc hermes kanban unblock <card_id>

# Archive if obsolete
HERMES_KANBAN_BOARD=sdlc hermes kanban archive <card_id>
```

## Run the Governance Score Reader Manually

```bash
python3 ~/.hermes/skills/workers/sdlc-governance/scripts/governance_scores.py --check
```

Without `--check`, the script will auto-edit AGENTS.md if thresholds are crossed.

## Query Langfuse Scores Directly

```bash
# All sdlc_* scores
docker exec langfuse-stack-clickhouse-1 clickhouse-client --query \
  "SELECT name, count() FROM default.scores WHERE name LIKE 'sdlc_%' GROUP BY name"

# Score trends for a specific card
docker exec langfuse-stack-clickhouse-1 clickhouse-client --query \
  "SELECT name, value, string_value FROM default.scores
   WHERE trace_id = 'card-t_cb819897' AND environment = 'default'"
```

## Run the Log Scan Manually

```bash
python3 ~/.hermes/scripts/sdlc-log-scan.py
```

## Recreate the Monitor Cron Job

If the monitor cron job is dead:

```bash
hermes cron create \
  --name sdlc-log-scan \
  --schedule "*/15 * * * *" \
  --no-agent \
  --script sdlc-log-scan.py \
  --deliver "telegram:8788236757"
```

## Health Check Endpoints

```bash
# Staging
curl http://localhost:5001/health
# → {"db":"connected","status":"healthy"}

# Production
curl http://localhost:5002/health
# → {"db":"connected","status":"healthy"}

# Langfuse
curl http://localhost:3000/api/public/health
# → {"status":"OK","version":"3.212.0"}
```
