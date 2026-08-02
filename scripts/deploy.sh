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
mkdir -p secrets
printf '%s\n' "${DB_PASS}"           > "secrets/${ENV}_db_pass.txt"
printf '%s\n' "${SDLC_API_KEY}"     > "secrets/${ENV}_sdlc_api_key.txt"
printf '%s\n' "${POSTGRES_PASSWORD}" > "secrets/${ENV}_postgres_password.txt"
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

# Start containers (secret files are read at container startup and bind-mounted;
# they must persist on disk for the lifetime of the container.)
docker compose -f "$COMPOSE_FILE" --project-name "$PROJECT_NAME" up -d --build

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
