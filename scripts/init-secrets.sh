#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
SECRETS_DIR="$ROOT_DIR/secrets"
API_TOKEN_FILE="$SECRETS_DIR/api_token"
NEO4J_PASS_FILE="$SECRETS_DIR/neo4j_password"
CREDS_OUT="$SECRETS_DIR/credentials.txt"

mkdir -p "$SECRETS_DIR"

gen_hex() {
  # 64 hex chars (256 bits)
  openssl rand -hex 32
}

gen_pass() {
  # Hex password (no special chars like / + = that cause issues with Neo4j AUTH)
  # 32 bytes = 64 hex chars
  openssl rand -hex 32
}

if [ ! -s "$API_TOKEN_FILE" ]; then
  API_TOKEN="$(gen_hex)"
  # Write without trailing newline
  printf "%s" "$API_TOKEN" > "$API_TOKEN_FILE"
  chmod 600 "$API_TOKEN_FILE"
else
  API_TOKEN="$(cat "$API_TOKEN_FILE")"
fi

if [ ! -s "$NEO4J_PASS_FILE" ]; then
  NEO4J_PASSWORD="$(gen_pass)"
  printf "%s" "$NEO4J_PASSWORD" > "$NEO4J_PASS_FILE"
  chmod 600 "$NEO4J_PASS_FILE"
else
  NEO4J_PASSWORD="$(cat "$NEO4J_PASS_FILE")"
fi

cat > "$CREDS_OUT" <<EOF
Generated at: $(date -Iseconds)

API_TOKEN: $API_TOKEN
NEO4J_USERNAME: neo4j
NEO4J_PASSWORD: $NEO4J_PASSWORD

Keep this file secret. It is not committed to git (see secrets/.gitignore).
EOF
chmod 600 "$CREDS_OUT"

echo "Secrets generated in $SECRETS_DIR"

