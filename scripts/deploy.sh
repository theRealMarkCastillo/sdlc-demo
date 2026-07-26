#!/bin/bash
# deploy.sh — SDLC deploy via Docker Compose
# Usage: bash scripts/deploy.sh [staging|prod]
# Sources .env explicitly so shell env pollution can't break compose interpolation.
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

# Source .env into a clean subshell
set -a
source .env
set +a

COMPOSE_FILE="docker-compose.${ENV}.yml"
PROJECT_NAME="sdlc-${ENV}"

# Port map for health checks — must match docker-compose.*.yml host ports
case "$ENV" in
    staging) APP_PORT=5001 ;;
    prod)    APP_PORT=5002 ;;
esac

echo "=== Deploying to $ENV (project: $PROJECT_NAME, port: $APP_PORT) ==="
echo "  Compose file: $COMPOSE_FILE"

# Down old containers (keep volumes for data persistence)
docker compose -f "$COMPOSE_FILE" --project-name "$PROJECT_NAME" down 2>/dev/null || true

# Build and start
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
