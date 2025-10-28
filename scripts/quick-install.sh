#!/usr/bin/env bash
set -euo pipefail

# BBOT OSINT MCP - Quick Install/Repair Script
# Usage: ./scripts/quick-install.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_DAEMON_JSON="/etc/docker/daemon.json"
DNS_JSON='{ "dns": ["1.1.1.1", "8.8.8.8"] }'

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Error: $1 is required" >&2; exit 1; }
}

require_cmd docker
require_cmd bash

cd "$REPO_DIR"

# 1) Ensure local runtime directories exist
mkdir -p logs cache scans secrets
chmod 777 logs cache scans || true

# 2) Ensure docker daemon uses reliable DNS (if not already)
if [ "$(id -u)" -ne 0 ]; then
  SUDO=sudo
else
  SUDO=
fi

# Create daemon.json if missing or missing dns key
if ! [ -f "$DOCKER_DAEMON_JSON" ]; then
  echo "Writing $DOCKER_DAEMON_JSON with public DNS..."
  echo "$DNS_JSON" | $SUDO tee "$DOCKER_DAEMON_JSON" >/dev/null
else
  if ! grep -q '"dns"' "$DOCKER_DAEMON_JSON"; then
    echo "Backing up $DOCKER_DAEMON_JSON -> $DOCKER_DAEMON_JSON.bak"
    $SUDO cp "$DOCKER_DAEMON_JSON" "$DOCKER_DAEMON_JSON.bak"
    echo "Adding dns resolvers to $DOCKER_DAEMON_JSON"
    # Minimal merge: replace file with DNS setting when simple or empty
    echo "$DNS_JSON" | $SUDO tee "$DOCKER_DAEMON_JSON" >/dev/null
  fi
fi

# Restart docker to apply DNS
$SUDO systemctl daemon-reload || true
$SUDO systemctl restart docker

# 3) Generate secrets if missing
if ! [ -f secrets/api_token ] || ! [ -f secrets/neo4j_password ]; then
  echo "Generating secrets..."
  if [ -x scripts/init-secrets.sh ]; then
    bash scripts/init-secrets.sh
  else
    # Fallback generation
    openssl rand -hex 32 > secrets/api_token
    openssl rand -hex 32 > secrets/neo4j_password
    echo "API_TOKEN: $(cat secrets/api_token)" > secrets/credentials.txt
    echo "NEO4J_PASSWORD: $(cat secrets/neo4j_password)" >> secrets/credentials.txt
  fi
fi

# 4) Bring up stack
$SUDO docker compose down || true
$SUDO docker compose up -d --build

# 5) Show quick status
$SUDO docker ps
echo "\nTip: Check logs: sudo docker logs -f bbot_osint"
