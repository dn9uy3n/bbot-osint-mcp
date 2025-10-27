## BBOT OSINT MCP Stack (Docker)

Deploy a secure OSINT service based on BBOT with FastAPI API, Neo4j for full-fidelity storage (events, hosts, domains, IPs, URLs, emails), and MCP server for Cursor integration. Optimized for continuous low-concurrency scanning to reduce blocking risk.

BBOT reference: [GitHub BBOT](https://github.com/blacklanternsecurity/bbot)

### Project Description

Systematize BBOT into a production-ready OSINT service running on VPS: secure, with API, Neo4j for comprehensive data storage (events, host, domain, ip, url, email), and MCP server for Cursor interaction. Optimized for continuous operation with low concurrency to minimize blocking.

### Features

- Run BBOT with "low-concurrency" config to avoid blocking, integrate API keys via config file.
- Store results in Neo4j with `last_seen_ts` and `status` for each `Host`.
- FastAPI API to trigger scans, query results, and upsert data from clients.
- MCP server for Cursor to connect and execute `osint.query`, `osint.scan`, `osint.events.query` securely.
- Automatic cleanup after scans (expired events, offline hosts, orphan nodes) and Telegram notifications on completion.
- Input configuration via `init_config.json` (targets, BBOT API keys, Telegram bot).

### Architecture

- `docker-compose.yml`: Neo4j and OSINT service (FastAPI + MCP).
- `init_config.json`: input configuration (targets, API keys, Telegram).
- `services/osint`: API, BBOT runner, MCP server source code.

### Preparation

1) Install Docker and Docker Compose.
2) Copy `.env.example` to `.env` and set secure environment variables.
3) Fill in `init_config.json` for initial input (targets, BBOT API keys, Telegram):
   - Template: `init_config.json.example` (copy to `init_config.json`)
   - Note: `init_config.json` is in `.gitignore`, safe for public push.

```json
{
  "targets": ["evilcorp.com"],
  "bbot_modules": {
    "securitytrails": { "api_key": "CHANGE_ME" },
    "shodan_dns": { "api_key": "CHANGE_ME" },
    "virustotal": { "api_key": "CHANGE_ME" },
    "c99": { "api_key": ["CHANGE_ME"] }
  },
  "TELEGRAM_BOT_TOKEN": "",
  "TELEGRAM_CHAT_ID": ""
}
```

If you prefer using `config/bbot.yml`, the system will merge `bbot_modules` from `init_config.json` into it on startup.

```bash
cp .env.example .env
cp init_config.json.example init_config.json
cp config/bbot.yml.example config/bbot.yml
```

Key variables in `.env`:

- `LE_DOMAIN`: your domain (e.g., `osint.example.com`)
- `LE_EMAIL`: email for Let's Encrypt registration
- `PUBLIC_BASE_URL`: public base URL

### Deployment (Secure with Let's Encrypt/Caddy)

Generate strong secrets before starting:

Linux/macOS:
```bash
bash scripts/init-secrets.sh
```

Windows (PowerShell):
```powershell
pwsh -File scripts/init-secrets.ps1
```

Generated credentials will be in `secrets/credentials.txt` for connection.

```bash
docker compose up -d --build
```

- Public: only ports 80/443 exposed via Caddy reverse proxy. API/MCP behind proxy; Neo4j internal only.
- Caddy automatically requests Let's Encrypt certificates if domain points to VPS IP.
- Required environment variables in `.env`:

```env
LE_DOMAIN=osint.example.com
LE_EMAIL=admin@example.com
PUBLIC_BASE_URL=https://osint.example.com
```

- API/MCP public via HTTPS: `https://$LE_DOMAIN/` and `https://$LE_DOMAIN/mcp`.

On first startup, API will create constraints for `Domain` and `Host`.

### BBOT Anti-Blocking Configuration

- `engine.max_workers = 2`
- `web.spider_distance = 1`, `web.spider_depth = 2`, `web.spider_links_per_page = 10`
- Rate limit for `httpx` (if using web modules).

Refer to BBOT docs for presets/flags: [BBOT README](https://github.com/blacklanternsecurity/bbot)

### API Usage

Required header: `X-API-Token: <API_TOKEN>`

- Healthcheck:

```bash
curl http://localhost:8000/healthz
```

- Trigger safe scan:

```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{
    "targets": ["evilcorp.com"],
    "presets": ["subdomain-enum"],
    "max_workers": 2,
    "spider_depth": 2,
    "spider_distance": 1,
    "spider_links_per_page": 10,
    "allow_deadly": false,
    "sleep_after_scan_seconds": 120
  }'
```

- Query results:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{"domain":"evilcorp.com","online_only":true,"limit":50}'
```

### Cleanup and Telegram Notifications

- Automatic cleanup after each scan, configurable via environment variables:
  - `CLEANUP_ENABLED=true|false`
  - `EVENT_RETENTION_DAYS=30`
  - `OFFLINE_HOST_RETENTION_DAYS=30`
  - `ORPHAN_CLEANUP_ENABLED=true|false`
- Telegram:
  - Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` to enable notifications.
  - After each scan, bot reports number of events collected and cleanup statistics.

- Query events (full BBOT fidelity):

```bash
curl -X POST http://localhost:8000/events/query \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{
    "types": ["DNS_NAME","URL"],
    "modules": ["subfinder","httpx"],
    "domain": "evilcorp.com",
    "since_ts": 1729000000,
    "limit": 100
  }'
```

- Direct upsert (client manual update):

```bash
curl -X POST http://localhost:8000/upsert \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{
    "domain":"evilcorp.com",
    "host":"www.evilcorp.com",
    "status":"online",
    "last_seen_ts": 1730000000,
    "sources": ["manual"],
    "ports": [80,443]
  }'
```

### Neo4j Data Model

- Node `Domain {name}`
- Node `Host {fqdn, status, last_seen_ts, sources, ports}`
- Node `IP {addr}`, `URL {value}`, `Email {value}`, `Module {name}`, `Event {id, type, ts, raw}`
- Relationships: `(:Host)-[:PART_OF]->(:Domain)`, `(:Event)-[:ABOUT]->(:Domain|:Host|:IP|:URL|:Email)`, `(:Event)-[:EMITTED_BY]->(:Module)`

Constraints initialized on startup:

```cypher
CREATE CONSTRAINT domain_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT host_unique IF NOT EXISTS FOR (h:Host) REQUIRE h.fqdn IS UNIQUE;
CREATE CONSTRAINT ip_unique IF NOT EXISTS FOR (i:IP) REQUIRE i.addr IS UNIQUE;
CREATE CONSTRAINT url_unique IF NOT EXISTS FOR (u:URL) REQUIRE u.value IS UNIQUE;
CREATE CONSTRAINT email_unique IF NOT EXISTS FOR (e:Email) REQUIRE e.value IS UNIQUE;
CREATE CONSTRAINT module_unique IF NOT EXISTS FOR (m:Module) REQUIRE m.name IS UNIQUE;
CREATE CONSTRAINT event_unique IF NOT EXISTS FOR (ev:Event) REQUIRE ev.id IS UNIQUE;
```

### MCP Server

- Mounted at `/mcp` within FastAPI, requires `X-API-Token` header.
- Tools:
  - `osint.query(domain?, host?, online_only?, limit=50)`
  - `osint.scan(targets, presets=["subdomain-enum"], allow_deadly=false)`
  - `osint.events.query(types?, modules?, domain?, host?, since_ts?, until_ts?, limit=200)`

### Cursor Integration (MCP Client)

1) Install MCP Client extension in Cursor and configure HTTP server:

```json
{
  "mcpServers": {
    "bbot-osint": {
      "type": "http",
      "url": "https://osint.example.com/mcp",
      "headers": {
        "X-API-Token": "YOUR_STRONG_TOKEN"
      }
    }
  }
}
```

2) Restart MCP client in Cursor. You'll see tools:
   - `osint.query`
   - `osint.scan`
   - `osint.events.query`

3) Call tools directly in Command Palette or chat. Example:

```text
Call MCP tool: osint.query {"domain":"evilcorp.com","online_only":true}
```

### Detailed Let's Encrypt/Caddy Deployment Guide

1) Prepare DNS: create A record for `$LE_DOMAIN` pointing to VPS IP.
2) Edit `.env` and fill `LE_DOMAIN`, `LE_EMAIL`, `PUBLIC_BASE_URL`.
3) Check `reverse-proxy/Caddyfile` uses variables `{$LE_DOMAIN}` and `{$LE_EMAIL}`.
4) Open ports 80/443 on VPS firewall.
5) Start stack:

```bash
docker compose up -d --build
```

6) Caddy will automatically request certificate from Let's Encrypt and store in `caddy_data` volume.
7) Test access `https://$LE_DOMAIN/healthz` with `X-API-Token` header.

Troubleshooting:
- If certificate not issued, check DNS pointing correctly, firewall allows 80/443, review container logs.
- Use `docker logs bbot_caddy` to see ACME details.

### Security

- Always use strong `API_TOKEN`, passed via `X-API-Token` header.
- Place service behind TLS reverse proxy (caddy/nginx/traefik) or enable TLS at uvicorn.
- Restrict IP access or use VPN.
- Don't run "deadly" presets/flags unless you understand the risks (BBOT has `--allow-deadly` flag).

### IP Access (Without Domain)

- Can't use Let's Encrypt with IP. Two secure options:
  1) Use Caddy internal CA (self-signed HTTPS), need to trust CA on client.
  2) Use HTTP via IP but within VPN/SSH tunnel.

- Using Caddy internal CA:
  - Change Caddyfile mount in `docker-compose.yml` to `reverse-proxy/Caddyfile.ip`:
    - `./reverse-proxy/Caddyfile.ip:/etc/caddy/Caddyfile:ro`
  - Start `docker compose up -d --build`
  - Trust CA on client:
    ```bash
    docker exec bbot_caddy caddy trust
    ```
    On Linux, this attempts auto-import CA to trust store. On Windows/macOS, export CA and import manually per Caddy docs. Then access `https://<IP_VPS>/`.

- Using HTTP with VPN/SSH tunnel:
  - Keep Caddy on HTTP (or use `Caddyfile.ip` but access via `http://<IP_VPS>`), and use WireGuard/OpenVPN/SSH -L to encrypt transport.
  - With SSH:
    ```bash
    ssh -L 8443:127.0.0.1:443 user@IP_VPS
    ```
    Then access `https://127.0.0.1:8443/` from client.

### Operational Tips

- Adjust BBOT config in `config/bbot.yml` to balance speed and safety.
- Monitor Neo4j Browser to inspect data.
- Review API/worker logs to monitor progress.

---

**Vietnamese version:** [README.md](README.md)

