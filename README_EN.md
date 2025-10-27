## BBOT OSINT MCP Stack (Docker)

> **Vietnamese version:** [README.md](README.md)

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
- `init_config.json`: input configuration (targets, API keys, Telegram, scan parameters).
- `services/osint`: API, BBOT runner, MCP server source code.
- `reverse-proxy/Caddyfile`: Caddy configuration with automatic Let's Encrypt.

---

## Step-by-Step Installation Guide

### Requirements

- VPS running Ubuntu 22.04 or 24.04
- Domain with A-record pointing to VPS IP (e.g., `osint.example.com`)
- Root or sudo access
- Ports 80 and 443 open on firewall

### Step 1: Update System and Install Docker

SSH into your VPS and run:

```bash
# Update system
sudo apt-get update -y && sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

# Add Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
   https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker and Docker Compose
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# Enable Docker on boot
sudo systemctl enable --now docker

# Verify installation
sudo docker --version
sudo docker compose version
```

### Step 2: Clone Repository

```bash
cd /opt
sudo git clone https://github.com/your-username/bbot-osint-mcp.git
cd bbot-osint-mcp
sudo chown -R $USER:$USER .
```

### Step 3: Generate Strong Secrets

```bash
# Run secret generation script
bash scripts/init-secrets.sh

# View generated credentials (API_TOKEN, Neo4j password)
cat secrets/credentials.txt
```

**Note**: Save the `API_TOKEN` from this file for API and MCP calls.

### Step 4: Create Environment Configuration

```bash
# Copy example file
cp .env.example .env

# Edit .env
nano .env
```

Fill in values:

```env
# Domain and email for Let's Encrypt
LE_DOMAIN=osint.example.com
LE_EMAIL=admin@example.com
PUBLIC_BASE_URL=https://osint.example.com

# Neo4j (password from secrets/neo4j_password)
NEO4J_USERNAME=neo4j

# Rate limit and concurrency
RATE_LIMIT_PER_MINUTE=120
MAX_CONCURRENT_SCANS=2

# Cleanup policy
CLEANUP_ENABLED=true
EVENT_RETENTION_DAYS=30
OFFLINE_HOST_RETENTION_DAYS=30
ORPHAN_CLEANUP_ENABLED=true

# Telegram (optional, can leave empty and fill in init_config.json)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### Step 5: Configure init_config.json

This file contains scan inputs and BBOT service API keys.

```bash
# Copy example file
cp init_config.json.example init_config.json

# Edit configuration
nano init_config.json
```

**Detailed Structure:**

```json
{
  "targets": [
    "evilcorp.com",
    "target2.com"
  ],
  "bbot_modules": {
    "securitytrails": { "api_key": "YOUR_SECURITYTRAILS_KEY" },
    "shodan_dns": { "api_key": "YOUR_SHODAN_KEY" },
    "virustotal": { "api_key": "YOUR_VIRUSTOTAL_KEY" },
    "c99": { "api_key": ["YOUR_C99_KEY_1", "YOUR_C99_KEY_2"] }
  },
  "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
  "TELEGRAM_CHAT_ID": "-1001234567890"
}
```

**Detailed Explanation:**

1. **targets**: Default target domain list. When calling `/scan` API without passing `targets`, this list will be used.

2. **bbot_modules**: API keys for BBOT modules:
   - `securitytrails`: Find subdomains via SecurityTrails
   - `shodan_dns`: DNS enumeration via Shodan
   - `virustotal`: Find subdomains and info via VirusTotal
   - `c99`: Multiple OSINT sources (supports multiple keys)
   - See more modules: [BBOT Modules](https://www.blacklanternsecurity.com/bbot/scanning/configuration/)

3. **TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID**: To receive notifications when scan completes.
   - Create bot: [@BotFather](https://t.me/botfather)
   - Get chat_id: [@userinfobot](https://t.me/userinfobot)

**Advanced Configuration (Optional):**

You can add advanced BBOT parameters to `init_config.json`:

```json
{
  "targets": ["evilcorp.com"],
  "bbot_modules": {
    "securitytrails": { "api_key": "YOUR_KEY" }
  },
  "TELEGRAM_BOT_TOKEN": "",
  "TELEGRAM_CHAT_ID": "",
  
  "scan_defaults": {
    "max_workers": 2,
    "spider_depth": 2,
    "spider_distance": 1,
    "spider_links_per_page": 10,
    "sleep_after_scan_seconds": 120
  }
}
```

**Note**: Currently `scan_defaults` is not automatically applied; you need to pass them directly when calling `/scan` API. This feature will be added in a future version.

### Step 6: Verify DNS and Firewall

```bash
# Check DNS points correctly
dig +short osint.example.com
# Should return your VPS IP

# Check firewall (Ubuntu UFW)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
sudo ufw status
```

### Step 7: Start the Stack

```bash
# Build and start containers
sudo docker compose up -d --build

# Monitor logs
sudo docker logs -f bbot_caddy
```

**Caddy will automatically:**
- Request certificate from Let's Encrypt
- Configure HTTPS automatically
- Redirect HTTP → HTTPS

When you see log `certificate obtained successfully`, it's successful.

### Step 8: Verify Service

```bash
# Get API_TOKEN
API_TOKEN=$(grep '^API_TOKEN:' secrets/credentials.txt | awk '{print $2}')

# Test healthcheck
curl -s -H "X-API-Token: $API_TOKEN" "https://osint.example.com/healthz"
# Result: {"status":"ok"}
```

### Step 9: Run First Scan

```bash
curl -X POST "https://osint.example.com/scan" \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{
    "targets": ["example.com"],
    "presets": ["subdomain-enum"],
    "max_workers": 2,
    "spider_depth": 2,
    "spider_distance": 1,
    "spider_links_per_page": 10,
    "allow_deadly": false,
    "sleep_after_scan_seconds": 60
  }'
```

**Telegram notification**: If configured, you'll receive a message when scan completes.

---

## Detailed Cleanup Explanation

### How Does Cleanup Work?

**Cleanup DOES NOT delete all data**, only removes:

1. **Expired Events**: Events older than `EVENT_RETENTION_DAYS` (default 30 days)
   - Example: Event scans from 31 days ago will be deleted
   - **Important data like Host, Domain are still kept**

2. **Expired Offline Hosts**: Hosts with `status=offline` and `last_seen_ts` older than `OFFLINE_HOST_RETENTION_DAYS`
   - Only deletes hosts that have been offline too long
   - Online hosts or recently offline hosts are kept

3. **Orphan nodes**: Nodes with no relationships
   - Example: Module not linked to any Event
   - Helps keep database clean

### Cleanup Configuration

In `.env`:

```env
# Enable/disable cleanup
CLEANUP_ENABLED=true

# Keep events for 30 days
EVENT_RETENTION_DAYS=30

# Delete offline hosts after 30 days
OFFLINE_HOST_RETENTION_DAYS=30

# Delete orphan nodes
ORPHAN_CLEANUP_ENABLED=true
```

**Important Note:**
- **Online** hosts and Domains are **NEVER** automatically deleted
- Only deletes "garbage" and old data according to policy
- Cleanup runs after each scan

### Example

Scan 1 (day 1):
- Collected 100 subdomains, 1000 events
- Database: 100 hosts, 1000 events

Scan 2 (day 35):
- Collected 120 new subdomains
- Cleanup deletes: 1000 old events (>30 days), 10 offline hosts (>30 days)
- Database after cleanup: 110 online hosts, 1200 new events

---

## API Usage

### Main Endpoints

**1. Healthcheck**

```bash
curl -H "X-API-Token: $API_TOKEN" "https://osint.example.com/healthz"
```

**2. Scan (with all parameters)**

```bash
curl -X POST "https://osint.example.com/scan" \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{
    "targets": ["evilcorp.com"],
    "presets": ["subdomain-enum"],
    "flags": [],
    "max_workers": 2,
    "spider_depth": 2,
    "spider_distance": 1,
    "spider_links_per_page": 10,
    "allow_deadly": false,
    "sleep_after_scan_seconds": 120
  }'
```

**Parameter Explanation:**
- `targets`: List of domains to scan
- `presets`: BBOT presets (`subdomain-enum`, `spider`, `web-basic`, etc.)
- `max_workers`: Number of concurrent threads (recommended 2-3)
- `spider_depth`, `spider_distance`, `spider_links_per_page`: Web crawling limits
- `sleep_after_scan_seconds`: Sleep after scan (avoid blocking with continuous scans)

**3. Query Hosts**

```bash
curl -X POST "https://osint.example.com/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{
    "domain": "evilcorp.com",
    "online_only": true,
    "limit": 100
  }'
```

**4. Query Events (Full Fidelity)**

```bash
curl -X POST "https://osint.example.com/events/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{
    "types": ["DNS_NAME", "URL"],
    "modules": ["subfinder", "httpx"],
    "domain": "evilcorp.com",
    "since_ts": 1729000000,
    "limit": 200
  }'
```

**5. Manual Upsert**

```bash
curl -X POST "https://osint.example.com/upsert" \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{
    "domain": "evilcorp.com",
    "host": "www.evilcorp.com",
    "status": "online",
    "last_seen_ts": 1730000000,
    "sources": ["manual"],
    "ports": [80, 443]
  }'
```

---

## Cursor Integration (MCP Client)

### Step 1: Install MCP in Cursor

1. Open Cursor Settings
2. Find MCP configuration section
3. Add server configuration:

```json
{
  "mcpServers": {
    "bbot-osint": {
      "type": "http",
      "url": "https://osint.example.com/mcp",
      "headers": {
        "X-API-Token": "YOUR_API_TOKEN_FROM_SECRETS"
      }
    }
  }
}
```

### Step 2: Restart MCP Client

In Cursor:
1. Command Palette (Ctrl+Shift+P / Cmd+Shift+P)
2. Type "MCP: Restart"
3. Select "MCP: Restart Client"

### Step 3: Use Tools

You'll see 3 tools:

1. **osint.query**: Query hosts from Neo4j
2. **osint.scan**: Trigger BBOT scan
3. **osint.events.query**: Query detailed events

**Example in Cursor chat:**

```
Call MCP tool: osint.query {"domain":"evilcorp.com","online_only":true}
```

or

```
Call MCP tool: osint.scan {"targets":["evilcorp.com"],"presets":["subdomain-enum"]}
```

---

## Neo4j Data Model

### Nodes

- `Domain {name}`: Main domain
- `Host {fqdn, status, last_seen_ts, sources, ports}`: Subdomain/host
- `IP {addr}`: IP addresses
- `URL {value}`: URLs
- `Email {value}`: Email addresses
- `Module {name}`: BBOT modules
- `Event {id, type, ts, raw}`: Events from BBOT

### Relationships

- `(:Host)-[:PART_OF]->(:Domain)`: Host belongs to domain
- `(:Event)-[:ABOUT]->(:Domain|:Host|:IP|:URL|:Email)`: Event about which entity
- `(:Event)-[:EMITTED_BY]->(:Module)`: Event from which module

### Querying Neo4j

Access Neo4j Browser: `http://VPS_IP:7474` (only from localhost, use SSH tunnel)

```bash
# SSH tunnel to access Neo4j
ssh -L 7474:localhost:7474 -L 7687:localhost:7687 user@VPS_IP
```

Then open browser: `http://localhost:7474`

**Example queries:**

```cypher
// Find all subdomains of evilcorp.com
MATCH (h:Host)-[:PART_OF]->(d:Domain {name: "evilcorp.com"})
WHERE h.status = "online"
RETURN h.fqdn, h.last_seen_ts, h.ports
ORDER BY h.last_seen_ts DESC

// Find events related to a host
MATCH (ev:Event)-[:ABOUT]->(h:Host {fqdn: "www.evilcorp.com"})
RETURN ev.type, ev.ts, ev.raw
ORDER BY ev.ts DESC
LIMIT 50
```

---

## Security

### Applied Security Measures

1. **API Token**: Required `X-API-Token` header for all endpoints
2. **Docker Secrets**: Credentials stored in Docker secrets, not hardcoded
3. **Internal Network**: Neo4j only exposed on internal Docker network
4. **HTTPS Only**: Caddy automatically redirects HTTP → HTTPS
5. **Container Hardening**: Read-only filesystem, drop capabilities, no-new-privileges
6. **Rate Limiting**: Request limits per IP

### Additional Recommendations

1. **Firewall**: Only open 80/443 publicly, SSH via IP whitelist
2. **VPN**: Access Neo4j and admin via VPN
3. **Monitoring**: Monitor logs and alert on 429/401 spikes
4. **Secrets Rotation**: Rotate API_TOKEN periodically
5. **Backup**: Regular backup of Neo4j data volume

```bash
# Backup Neo4j
sudo docker compose exec neo4j neo4j-admin database dump neo4j \
  --to-path=/data/backups/backup-$(date +%Y%m%d).dump
```

---

## Troubleshooting

### 1. Let's Encrypt Certificate Not Issued

**Check:**
```bash
# DNS pointing correctly?
dig +short osint.example.com

# Firewall allows 80/443?
sudo ufw status

# Caddy logs
sudo docker logs bbot_caddy
```

**Solution:**
- Ensure DNS points to VPS IP
- Turn off Cloudflare proxy (gray cloud) during first certificate request
- Verify ports 80/443 are not blocked

### 2. API Returns 401 Unauthorized

**Cause**: Wrong or missing `X-API-Token`

**Solution:**
```bash
# Check correct token
cat secrets/credentials.txt | grep API_TOKEN

# Test with correct token
curl -H "X-API-Token: $(grep '^API_TOKEN:' secrets/credentials.txt | awk '{print $2}')" \
  "https://osint.example.com/healthz"
```

### 3. Scan Gets Blocked/Rate Limited

**Cause**: Scanning too fast

**Solution:**
- Reduce `max_workers` to 1-2
- Increase `sleep_after_scan_seconds`
- Use API keys for modules (in `init_config.json`)

### 4. Database Full

**Solution:**
- Reduce `EVENT_RETENTION_DAYS` and `OFFLINE_HOST_RETENTION_DAYS`
- Run manual cleanup:

```bash
# Enter container
sudo docker exec -it bbot_osint bash

# Python shell
python3 -c "
from app.repository import cleanup_graph
import time
stats = cleanup_graph(int(time.time()))
print(stats)
"
```

---

## Operational Tips

1. **View realtime logs:**
```bash
sudo docker compose logs -f
```

2. **Restart services:**
```bash
sudo docker compose restart osint
```

3. **Update code:**
```bash
git pull
sudo docker compose up -d --build
```

4. **View Neo4j stats:**
```cypher
// In Neo4j Browser
MATCH (n) RETURN labels(n) as type, count(*) as count
```

5. **Export data:**
```bash
# Query and export JSON
curl -X POST "https://osint.example.com/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{"domain":"evilcorp.com","limit":10000}' \
  | jq '.results' > export.json
```

---

**Happy Deploying!** 🎉

If you encounter issues, please open an issue on GitHub or contact us.
