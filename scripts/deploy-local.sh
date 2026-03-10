#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILE="docker-compose.local.yml"

echo "=== EmailSolver Local Deploy ==="
echo

if [ ! -f .env ]; then
    echo "ERROR: .env file not found."
    echo "Copy .env.example to .env and fill in your values:"
    echo "  cp .env.example .env"
    exit 1
fi

echo "[1/3] Building containers..."
docker compose -f "$COMPOSE_FILE" build

echo
echo "[2/3] Starting services (migrations will run automatically)..."
docker compose -f "$COMPOSE_FILE" up -d

echo
echo "[3/3] Waiting for app to be healthy..."
MAX_WAIT=60
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo
        echo "=== Local deploy successful ==="
        echo "  App:    http://localhost:8000"
        echo "  Health: http://localhost:8000/health"
        echo "  Docs:   http://localhost:8000/docs"
        exit 0
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    printf "."
done

echo
echo "ERROR: App did not become healthy within ${MAX_WAIT}s"
echo "Check logs with: docker compose -f $COMPOSE_FILE logs app"
exit 1
