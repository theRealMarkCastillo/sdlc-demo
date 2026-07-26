#!/bin/bash
# deploy.sh — SDLC deploy via Docker Compose
# Usage: bash scripts/deploy.sh [staging|prod]
# Sources .env explicitly so shell env pollution can't break compose interpolation.
set -euo pipefail

ENV="${1:-staging}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Source .env into a clean subshell
set -a
source .env
set +a

COMPOSE_FILE="docker-compose.${ENV}.yml"

echo "=== Deploying to $ENV ==="
echo "  Compose file: $COMPOSE_FILE"

# Down old containers (keep volumes for data persistence)
docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true

# Build and start
docker compose -f "$COMPOSE_FILE" up -d --build

# Wait for health
echo "  Waiting for healthy..."
for i in $(seq 1 15); do
    if curl -sf "http://localhost:${PORT:-5000}/health" > /dev/null 2>&1; then
        echo "  ✓ Healthy"
        exit 0
    fi
    sleep 2
done

echo "  ✗ Timeout — check logs"
docker compose -f "$COMPOSE_FILE" logs app --tail 20
exit 1
