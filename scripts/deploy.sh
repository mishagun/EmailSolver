#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== EmailSolver Deploy ==="
echo

# Pre-flight: check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found."
    echo "Copy .env.example to .env and fill in your values:"
    echo "  cp .env.example .env"
    exit 1
fi

# Validate required vars aren't placeholders
REQUIRED_VARS=(
    "GOOGLE_CLIENT_ID:your-google-client-id"
    "GOOGLE_CLIENT_SECRET:your-google-client-secret"
    "JWT_SECRET_KEY:change-me-to-a-random-secret"
    "FERNET_KEY:change-me-to-a-fernet-key"
    "ANTHROPIC_API_KEY:your-anthropic-api-key"
)

for entry in "${REQUIRED_VARS[@]}"; do
    var_name="${entry%%:*}"
    placeholder="${entry#*:}"
    value=$(grep "^${var_name}=" .env | cut -d'=' -f2- || true)

    if [ -z "$value" ] || [ "$value" = "$placeholder" ]; then
        echo "ERROR: $var_name is missing or still set to placeholder in .env"
        exit 1
    fi
done

echo "[1/3] Building containers..."
docker compose build

echo
echo "[2/3] Starting services (migrations will run automatically)..."
docker compose up -d

echo
echo "[3/3] Waiting for app to be healthy..."
MAX_WAIT=60
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo
        echo "=== Deploy successful ==="
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
echo "Check logs with: docker compose logs app"
exit 1
