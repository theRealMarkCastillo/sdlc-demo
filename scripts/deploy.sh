#!/bin/bash
# deploy.sh — SDLC deploy via Docker Compose
# Usage: bash scripts/deploy.sh [staging|prod]
# Sources env-specific .env file and stages Docker Compose file-based secrets.
set -euo pipefail

ENV="${1:-staging}"

# Validate environment
if [[ "$ENV" != "staging" && "$ENV" != "prod" ]]; then
    echo "ERROR: Invalid environment '$ENV'. Use 'staging' or 'prod'."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Source env-specific .env file
ENV_FILE=".env.${ENV}"
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found. Copy .env.example and fill in real values:"
    echo "  cp .env.example $ENV_FILE"
    exit 1
fi
set -a
source "$ENV_FILE"
set +a

COMPOSE_FILE="docker-compose.${ENV}.yml"
PROJECT_NAME="sdlc-${ENV}"

# Stage Docker Compose file-based secrets from env vars
# Docker Compose reads these files at container start; they're mounted
# at /run/secrets/<name> and are NOT visible via docker inspect.
#
# Uses env-specific namespaced variables first (e.g., STAGING_DB_PASS),
# falling back to the shared variable (DB_PASS) for backward compatibility.
mkdir -p secrets
DB_PASS_VAR="${ENV^^}_DB_PASS"
API_KEY_VAR="${ENV^^}_SDLC_API_KEY"
PG_PASS_VAR="${ENV^^}_POSTGRES_PASSWORD"

DB_PASS_VAL="${!DB_PASS_VAR:-${DB_PASS:?DB_PASS and $DB_PASS_VAR are both unset}}"
API_KEY_VAL="${!API_KEY_VAR:-${SDLC_API_KEY:?SDLC_API_KEY and $API_KEY_VAR are both unset}}"
PG_PASS_VAL="${!PG_PASS_VAR:-${POSTGRES_PASSWORD:?POSTGRES_PASSWORD and $PG_PASS_VAR are both unset}}"

echo "$DB_PASS_VAL"     > "secrets/${ENV}_db_pass.txt"
echo "$API_KEY_VAL"     > "secrets/${ENV}_sdlc_api_key.txt"
echo "$PG_PASS_VAL"     > "secrets/${ENV}_postgres_password.txt"
chmod 600 "secrets/${ENV}_db_pass.txt" "secrets/${ENV}_sdlc_api_key.txt" "secrets/${ENV}_postgres_password.txt"

# Port map for health checks — must match docker-compose.*.yml host ports
case "$ENV" in
    staging) APP_PORT=5001 ;;
    prod)    APP_PORT=5002 ;;
esac

echo "=== Deploying to $ENV (project: $PROJECT_NAME, port: $APP_PORT) ==="
echo "  Compose file: $COMPOSE_FILE"
echo "  Env file:     $ENV_FILE"

# Down old containers (keep volumes for data persistence)
docker compose -f "$COMPOSE_FILE" --project-name "$PROJECT_NAME" down 2>/dev/null || true

# Build and start
docker compose -f "$COMPOSE_FILE" --project-name "$PROJECT_NAME" up -d --build

# Clean up staged secret files (already read by Docker Compose during build)
rm -f "secrets/${ENV}_db_pass.txt" "secrets/${ENV}_sdlc_api_key.txt" "secrets/${ENV}_postgres_password.txt"

# Wait for health
echo "  Waiting for healthy..."
for i in $(seq 1 15); do
    if curl -sf "http://localhost:${APP_PORT}/health" > /dev/null 2>&1; then
        echo "  ✓ Healthy"
        exit 0
    fi
    sleep 2
done

echo "  ✗ Timeout — check logs"
docker compose -f "$COMPOSE_FILE" --project-name "$PROJECT_NAME" logs app --tail 20
exit 1
