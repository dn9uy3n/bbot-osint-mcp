## BBOT OSINT Continuous Monitoring Stack (Docker)

> **English version:** [README_EN.md](README_EN.md)

Hệ thống giám sát OSINT liên tục dựa trên BBOT với FastAPI, Neo4j để lưu trữ kết quả đầy đủ, và MCP server để query từ Cursor.

Tài liệu BBOT tham khảo: [GitHub BBOT](https://github.com/blacklanternsecurity/bbot)

### Mô tả dự án

Hệ thống **continuous monitoring** tự động quét targets theo chu kỳ, lưu dữ liệu đầy đủ vào Neo4j (DNS records, open ports, technologies, events), với API và MCP để query. Tối ưu để chạy 24/7 với ít luồng, giảm nguy cơ bị chặn.

### Tính năng chính

- **Automatic Continuous Scanning**: Tự động quét tất cả targets theo chu kỳ được cấu hình, không cần trigger thủ công.
- **2 loại Sleep Time**:
  - `target_sleep_seconds`: Nghỉ giữa mỗi target trong cùng chu kỳ (tránh quét liên tục).
  - `cycle_sleep_seconds`: Nghỉ sau khi quét xong tất cả targets trước khi bắt đầu chu kỳ mới.
- **Full Data Fidelity**: Lưu đầy đủ dữ liệu BBOT vào Neo4j (DNS_NAME, OPEN_TCP_PORT, TECHNOLOGY, Event raw data).
- **Incremental Updates**: Các lần quét sau chỉ cập nhật/thêm mới, không xóa dữ liệu cũ (trừ cleanup theo retention policy).
- **MCP Query Interface**: Cursor có thể kết nối qua MCP để query dữ liệu (`osint.query`, `osint.events.query`, `osint.status`).
- **REST API**: Query hosts và events qua HTTP API.
- **Automatic Cleanup**: Xóa events quá hạn, hosts offline lâu, và orphan nodes sau mỗi chu kỳ.
- **Telegram Notifications**: Thông báo sau mỗi chu kỳ quét hoàn thành.
- **Centralized Configuration**: Tất cả cấu hình trong `init_config.json` (targets, API keys, sleep times).

### Kiến trúc

- `docker-compose.yml`: Neo4j và service OSINT (FastAPI + MCP).
- `init_config.json`: cấu hình đầu vào (targets, API keys, Telegram, tham số scan).
- `services/osint`: mã nguồn API, BBOT runner, MCP server.
- `reverse-proxy/Caddyfile`: cấu hình Caddy với Let's Encrypt tự động.

#### Sơ đồ kiến trúc

```mermaid
graph TB
    subgraph "Client Layer"
        A[Cursor IDE<br/>MCP Query Only]
        B[Monitoring Dashboard]
        C[API Client/Script]
    end
    
    subgraph "VPS Server"
        D[Caddy Reverse Proxy<br/>Port 80/443<br/>Let's Encrypt TLS]
        
        subgraph "Internal Network"
            E[FastAPI Service<br/>Port 8000<br/>+ Continuous Scanner]
            F[Neo4j Database<br/>Port 7687]
            
            E -->|Ingest Data| F
            E -->|Auto Scan Loop| E
        end
        
        D --> E
    end
    
    subgraph "External Services"
        G[BBOT Modules<br/>SecurityTrails, Shodan,<br/>VirusTotal, etc.]
        H[Telegram Bot API]
    end
    
    A -->|MCP Query HTTPS| D
    B -->|HTTPS API| D
    C -->|HTTPS API| D
    E -->|Continuous Scan| G
    E -->|Cycle Complete Notify| H
    
    style D fill:#f9f,stroke:#333,stroke-width:2px
    style E fill:#bbf,stroke:#333,stroke-width:2px
    style F fill:#bfb,stroke:#333,stroke-width:2px
```

#### Continuous Monitoring Flow

```mermaid
sequenceDiagram
    participant S as Continuous Scanner
    participant B as BBOT
    participant N as Neo4j
    participant T as Telegram
    
    Note over S: Service starts
    S->>S: Load targets from init_config.json
    
    loop Every Cycle
        Note over S: Cycle Start
        
        loop For each target
            S->>B: Scan target[i]
            B-->>S: Events stream
            S->>N: Ingest events (incremental)
            
            alt Not last target
                Note over S: Sleep target_sleep_seconds
            end
        end
        
        S->>N: Cleanup old/offline data
        S->>T: Send cycle summary
        Note over S: Sleep cycle_sleep_seconds
    end
```

#### Luồng dữ liệu Neo4j

```mermaid
graph LR
    subgraph "BBOT Events"
        E1[DNS_NAME]
        E2[OPEN_TCP_PORT]
        E3[TECHNOLOGY]
        E4[URL]
        E5[EMAIL]
    end
    
    subgraph "Neo4j Nodes"
        N1[Host]
        N2[Domain]
        N3[DNS_NAME]
        N4[OPEN_TCP_PORT]
        N5[TECHNOLOGY]
        N6[IP]
        N7[URL]
        N8[Email]
        N9[Module]
        N10[Event]
    end
    
    E1 --> N3
    E2 --> N4
    E3 --> N5
    E4 --> N7
    E5 --> N8
    
    N1 -->|PART_OF| N2
    N3 -->|RESOLVES_TO| N1
    N4 -->|ON_HOST| N1
    N1 -->|USES_TECH| N5
    N10 -->|ABOUT| N1
    N10 -->|ABOUT| N2
    N10 -->|EMITTED_BY| N9
    
    style N1 fill:#bbf,stroke:#333,stroke-width:2px
    style N2 fill:#bfb,stroke:#333,stroke-width:2px
    style N3 fill:#fbb,stroke:#333,stroke-width:2px
    style N4 fill:#fbf,stroke:#333,stroke-width:2px
    style N5 fill:#ffb,stroke:#333,stroke-width:2px
```

---

## Hướng dẫn cài đặt từ đầu (Step-by-Step)

### Yêu cầu

- VPS chạy Ubuntu 22.04 hoặc 24.04
- Domain đã trỏ A-record về IP VPS (ví dụ: `osint.example.com`)
- Quyền root hoặc sudo
- Mở cổng 80 và 443 trên firewall

### Bước 1: Cập nhật hệ thống và cài Docker

SSH vào VPS và chạy:

```bash
# Cập nhật hệ thống
sudo apt-get update -y && sudo apt-get upgrade -y

# Cài các package cần thiết
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

# Thêm Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Thêm Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
   https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Cài Docker và Docker Compose
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# Bật Docker tự khởi động
sudo systemctl enable --now docker

# Kiểm tra Docker
sudo docker --version
sudo docker compose version
```

### Bước 2: Clone repository

```bash
cd /opt
sudo git clone https://github.com/your-username/bbot-osint-mcp.git
cd bbot-osint-mcp
sudo chown -R $USER:$USER .
```

### Bước 3: Sinh secrets mạnh

```bash
# Chạy script sinh secrets
bash scripts/init-secrets.sh

# Xem thông tin đã sinh (API_TOKEN, Neo4j password)
cat secrets/credentials.txt
```

**Lưu ý**: Ghi nhớ `API_TOKEN` trong file này để dùng khi gọi API và MCP.

### Bước 4: Tạo file cấu hình môi trường

```bash
# Copy file mẫu
cp .env.example .env

# Chỉnh sửa .env
nano .env
```

Điền các giá trị:

```env
# Domain và email cho Let's Encrypt
LE_DOMAIN=osint.example.com
LE_EMAIL=admin@example.com
PUBLIC_BASE_URL=https://osint.example.com

# Neo4j (password sẽ dùng từ secrets/neo4j_password)
NEO4J_USERNAME=neo4j

# Giới hạn rate và concurrency
RATE_LIMIT_PER_MINUTE=120
MAX_CONCURRENT_SCANS=2

# Cleanup policy
CLEANUP_ENABLED=true
EVENT_RETENTION_DAYS=30
OFFLINE_HOST_RETENTION_DAYS=30
ORPHAN_CLEANUP_ENABLED=true

# Telegram (tùy chọn, có thể để trống và điền vào init_config.json)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### Bước 5: Cấu hình init_config.json

File này chứa đầu vào cho scan và API keys của các dịch vụ BBOT.

```bash
# Copy file mẫu
cp init_config.json.example init_config.json

# Chỉnh sửa
nano init_config.json
```

**Cấu trúc chi tiết:**

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

**Giải thích chi tiết:**

1. **targets**: Danh sách domain mục tiêu mặc định. Khi gọi API `/scan` mà không truyền `targets`, sẽ dùng danh sách này.

2. **bbot_modules**: API keys cho các module BBOT:
   - `securitytrails`: Tìm subdomain qua SecurityTrails
   - `shodan_dns`: DNS enumeration qua Shodan
   - `virustotal`: Tìm subdomain và thông tin qua VirusTotal
   - `c99`: Nhiều nguồn OSINT (hỗ trợ nhiều key)
   - Xem thêm modules: [BBOT Modules](https://www.blacklanternsecurity.com/bbot/scanning/configuration/)

3. **TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID**: Để nhận thông báo khi scan xong.
   - Tạo bot: [@BotFather](https://t.me/botfather)
   - Lấy chat_id: [@userinfobot](https://t.me/userinfobot)

**Cấu hình scan_defaults (Quan trọng!):**

```json
{
  "targets": ["evilcorp.com", "target2.com"],
  "bbot_modules": {
    "securitytrails": { "api_key": "YOUR_KEY" }
  },
  "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF...",
  "TELEGRAM_CHAT_ID": "-1001234567890",
  
  "scan_defaults": {
    "presets": ["subdomain-enum"],
    "flags": [],
    "max_workers": 2,
    "spider_depth": 2,
    "spider_distance": 1,
    "spider_links_per_page": 10,
    "allow_deadly": false,
    "target_sleep_seconds": 300,
    "cycle_sleep_seconds": 3600
  }
}
```

**Giải thích các tham số quan trọng:**

1. **targets**: Danh sách tất cả targets sẽ được quét tự động. Scanner sẽ lặp qua từng target theo thứ tự.

2. **target_sleep_seconds** (mặc định 300 = 5 phút):
   - Thời gian **nghỉ giữa mỗi target** trong cùng một chu kỳ.
   - Ví dụ: Scan target1 → sleep 5 phút → Scan target2 → sleep 5 phút → Scan target3
   - **Mục đích**: Tránh quét liên tục nhiều targets gây chú ý, giảm nguy cơ block.
   - **Khuyến nghị**: 300-600s (5-10 phút) cho production.

3. **cycle_sleep_seconds** (mặc định 3600 = 1 giờ):
   - Thời gian **nghỉ sau khi quét xong TẤT CẢ targets** trước khi bắt đầu chu kỳ mới.
   - Ví dụ: [Quét all targets + cleanup] → sleep 1 giờ → [Quét all targets lại...]
   - **Mục đích**: Cho API keys và hệ thống "rest", tránh rate limit.
   - **Khuyến nghị**: 3600-7200s (1-2 giờ) cho monitoring thường xuyên, 86400s (24 giờ) cho daily audit.

📖 **Chi tiết đầy đủ về 2 tham số sleep**: Xem file [SLEEP_PARAMETERS.md](SLEEP_PARAMETERS.md)

### Bước 6: Kiểm tra DNS và Firewall

```bash
# Kiểm tra DNS đã trỏ đúng
dig +short osint.example.com
# Phải trả về IP VPS của bạn

# Kiểm tra firewall (Ubuntu UFW)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
sudo ufw status
```

### Bước 7: Khởi chạy stack

```bash
# Build và start containers
sudo docker compose up -d --build

# Theo dõi logs
sudo docker logs -f bbot_caddy
```

**Caddy sẽ tự động:**
- Xin chứng chỉ từ Let's Encrypt
- Cấu hình HTTPS tự động
- Redirect HTTP → HTTPS

Khi thấy log `certificate obtained successfully` là thành công.

### Bước 8: Kiểm tra dịch vụ

```bash
# Lấy API_TOKEN
API_TOKEN=$(grep '^API_TOKEN:' secrets/credentials.txt | awk '{print $2}')

# Test healthcheck
curl -s -H "X-API-Token: $API_TOKEN" "https://osint.example.com/healthz"
# Kết quả: {"status":"ok","scanner_running":true,"targets":["evilcorp.com"]}

# Kiểm tra trạng thái scanner
curl -s -H "X-API-Token: $API_TOKEN" "https://osint.example.com/status"
```

### Bước 9: Theo dõi quá trình scan

Continuous scanner tự động bắt đầu khi service khởi động. Theo dõi logs:

```bash
# Xem logs của OSINT service
sudo docker logs -f bbot_osint

# Filter chỉ xem scanner logs
sudo docker logs -f bbot_osint 2>&1 | grep -E "Scanning|Sleep|Cycle"
```

**Output mẫu:**
```
[INFO] === Starting scan cycle at 2025-10-27 14:30:00 ===
[INFO] [1/2] Scanning target: evilcorp.com
[INFO] ✓ Target evilcorp.com completed: 1247 events
[INFO] Sleeping 300s before next target...
[INFO] [2/2] Scanning target: target2.com
[INFO] ✓ Target target2.com completed: 892 events
[INFO] Running cleanup...
[INFO] === Cycle completed in 1534s, total events: 2139 ===
[INFO] Sleeping 3600s until next cycle...
```

**Telegram notification**: Sau mỗi chu kỳ, bạn sẽ nhận tin nhắn tóm tắt.

---

## Giải thích chi tiết về Cleanup (Dọn dẹp)

### Cleanup hoạt động như thế nào?

**Cleanup KHÔNG xóa toàn bộ dữ liệu**, chỉ xóa:

1. **Events quá hạn**: Events cũ hơn `EVENT_RETENTION_DAYS` (mặc định 30 ngày)
   - Ví dụ: Event scan từ 31 ngày trước sẽ bị xóa
   - **Dữ liệu quan trọng như Host, Domain vẫn được giữ**

2. **Host offline quá hạn**: Host có `status=offline` và `last_seen_ts` cũ hơn `OFFLINE_HOST_RETENTION_DAYS`
   - Chỉ xóa host đã offline quá lâu
   - Host online hoặc mới offline vẫn được giữ

3. **Orphan nodes** (node mồ côi): Nodes không có quan hệ nào
   - Ví dụ: Module không liên kết với Event nào
   - Giúp giữ database gọn gàng

### Cấu hình cleanup

Trong `.env`:

```env
# Bật/tắt cleanup
CLEANUP_ENABLED=true

# Giữ events trong 30 ngày
EVENT_RETENTION_DAYS=30

# Xóa host offline sau 30 ngày
OFFLINE_HOST_RETENTION_DAYS=30

# Xóa nodes mồ côi
ORPHAN_CLEANUP_ENABLED=true
```

**Lưu ý quan trọng:**
- Host **online** và Domain **KHÔNG BAO GIỜ** bị xóa tự động
- Chỉ xóa dữ liệu "rác" và dữ liệu cũ theo chính sách
- Cleanup chạy sau mỗi lần scan

### Ví dụ

Scan lần 1 (ngày 1):
- Thu về 100 subdomains, 1000 events
- Database: 100 hosts, 1000 events

Scan lần 2 (ngày 35):
- Thu về 120 subdomains mới
- Cleanup xóa: 1000 events cũ (>30 ngày), 10 hosts offline (>30 ngày)
- Database sau cleanup: 110 hosts online, 1200 events mới

---

## Sử dụng API

### Các endpoint chính

**1. Healthcheck & Status**

```bash
# Kiểm tra service health
curl -H "X-API-Token: $API_TOKEN" "https://osint.example.com/healthz"

# Xem trạng thái scanner chi tiết
curl -H "X-API-Token: $API_TOKEN" "https://osint.example.com/status"
```

**Response mẫu `/status`:**
```json
{
  "scanner_running": true,
  "targets": ["evilcorp.com", "target2.com"],
  "scan_config": {
    "presets": ["subdomain-enum"],
    "max_workers": 2,
    "target_sleep_seconds": 300,
    "cycle_sleep_seconds": 3600
  },
  "cleanup_enabled": true
}
```

**2. Query hosts**

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

**3. Query events (full fidelity)**

```bash
curl -X POST "https://osint.example.com/events/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{
    "types": ["DNS_NAME", "OPEN_TCP_PORT", "TECHNOLOGY"],
    "modules": ["subfinder", "httpx"],
    "domain": "evilcorp.com",
    "since_ts": 1729000000,
    "limit": 200
  }'
```

**Lưu ý**: Không có endpoint `/scan` để trigger scan thủ công. Scanner tự động chạy theo chu kỳ với targets trong `init_config.json`.

---

## Tích hợp vào Cursor (MCP Client)

### Bước 1: Cài đặt MCP trong Cursor

1. Mở Cursor Settings
2. Tìm phần MCP configuration
3. Thêm cấu hình server:

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

### Bước 2: Restart MCP client

Trong Cursor:
1. Command Palette (Ctrl+Shift+P / Cmd+Shift+P)
2. Gõ "MCP: Restart"
3. Chọn "MCP: Restart Client"

### Bước 3: Sử dụng tools

Bạn sẽ thấy 3 tools (chỉ để query, không trigger scan):

1. **osint.query**: Query hosts từ Neo4j
2. **osint.events.query**: Query events chi tiết
3. **osint.status**: Xem trạng thái scanner

**Ví dụ trong Cursor chat:**

```
Call MCP tool: osint.query {"domain":"evilcorp.com","online_only":true}
```

```
Call MCP tool: osint.events.query {"types":["DNS_NAME","OPEN_TCP_PORT"],"limit":100}
```

```
Call MCP tool: osint.status {}
```

**Lưu ý**: MCP **KHÔNG có** tool `osint.scan`. Scan tự động chạy theo chu kỳ từ service backend.

---

## Neo4j Data Model

### Nodes

- `Domain {name}`: Domain chính
- `Host {fqdn, status, last_seen_ts, sources, ports}`: Subdomain/host
- `IP {addr}`: Địa chỉ IP
- `URL {value}`: URLs
- `Email {value}`: Email addresses
- `DNS_NAME {name, last_seen_ts}`: DNS records từ BBOT
- `OPEN_TCP_PORT {endpoint, port, host, last_seen_ts}`: Cổng mở (ví dụ: `example.com:443`)
- `TECHNOLOGY {name}`: Công nghệ phát hiện được (ví dụ: `nginx`, `PHP`, `WordPress`)
- `Module {name}`: BBOT modules
- `Event {id, type, ts, raw}`: Events từ BBOT (lưu đầy đủ raw data)

### Relationships

- `(:Host)-[:PART_OF]->(:Domain)`: Host thuộc domain
- `(:DNS_NAME)-[:RESOLVES_TO]->(:Host)`: DNS name resolve tới host
- `(:OPEN_TCP_PORT)-[:ON_HOST]->(:Host)`: Port mở trên host nào
- `(:Host)-[:USES_TECH]->(:TECHNOLOGY)`: Host sử dụng công nghệ gì
- `(:Event)-[:ABOUT]->(:Domain|:Host|:IP|:URL|:Email|:DNS_NAME|:OPEN_TCP_PORT|:TECHNOLOGY)`: Event về entity nào
- `(:Event)-[:EMITTED_BY]->(:Module)`: Event từ module nào

### Truy vấn Neo4j

Truy cập Neo4j Browser: `http://VPS_IP:7474` (chỉ từ localhost, dùng SSH tunnel)

```bash
# SSH tunnel để truy cập Neo4j
ssh -L 7474:localhost:7474 -L 7687:localhost:7687 user@VPS_IP
```

Sau đó mở trình duyệt: `http://localhost:7474`

**Ví dụ queries:**

```cypher
// Tìm tất cả subdomains của evilcorp.com
MATCH (h:Host)-[:PART_OF]->(d:Domain {name: "evilcorp.com"})
WHERE h.status = "online"
RETURN h.fqdn, h.last_seen_ts, h.ports
ORDER BY h.last_seen_ts DESC

// Tìm tất cả open ports của một domain
MATCH (op:OPEN_TCP_PORT)-[:ON_HOST]->(h:Host)-[:PART_OF]->(d:Domain {name: "evilcorp.com"})
RETURN h.fqdn, op.port, op.last_seen_ts
ORDER BY op.port

// Tìm công nghệ được sử dụng
MATCH (h:Host)-[:USES_TECH]->(t:TECHNOLOGY)
WHERE h.fqdn CONTAINS "evilcorp.com"
RETURN h.fqdn, collect(t.name) as technologies

// Tìm DNS records
MATCH (dn:DNS_NAME)-[:RESOLVES_TO]->(h:Host)-[:PART_OF]->(d:Domain {name: "evilcorp.com"})
RETURN dn.name, h.fqdn, dn.last_seen_ts
ORDER BY dn.last_seen_ts DESC

// Tìm events liên quan đến một host
MATCH (ev:Event)-[:ABOUT]->(h:Host {fqdn: "www.evilcorp.com"})
RETURN ev.type, ev.ts, ev.raw
ORDER BY ev.ts DESC
LIMIT 50
```

---

## Bảo mật

### Các biện pháp đã áp dụng

1. **API Token**: Bắt buộc header `X-API-Token` cho mọi endpoint
2. **Docker Secrets**: Credentials lưu trong Docker secrets, không hardcode
3. **Internal Network**: Neo4j chỉ lộ trên mạng nội bộ Docker
4. **HTTPS Only**: Caddy tự động redirect HTTP → HTTPS
5. **Container Hardening**: Read-only filesystem, drop capabilities, no-new-privileges
6. **Rate Limiting**: Giới hạn request per IP

### Khuyến nghị bổ sung

1. **Firewall**: Chỉ mở 80/443 public, SSH qua IP whitelist
2. **VPN**: Truy cập Neo4j và quản trị qua VPN
3. **Monitoring**: Theo dõi logs và cảnh báo 429/401
4. **Secrets Rotation**: Xoay vòng API_TOKEN định kỳ
5. **Backup**: Backup Neo4j data volume thường xuyên

```bash
# Backup Neo4j
sudo docker compose exec neo4j neo4j-admin database dump neo4j \
  --to-path=/data/backups/backup-$(date +%Y%m%d).dump
```

---

## Troubleshooting

### 1. Let's Encrypt không ra cert

**Kiểm tra:**
```bash
# DNS đã trỏ đúng?
dig +short osint.example.com

# Firewall đã mở 80/443?
sudo ufw status

# Logs Caddy
sudo docker logs bbot_caddy
```

**Giải pháp:**
- Đảm bảo DNS trỏ về IP VPS
- Tắt Cloudflare proxy (mây xám) trong quá trình xin cert lần đầu
- Kiểm tra port 80/443 không bị chặn

### 2. API trả về 401 Unauthorized

**Nguyên nhân**: Sai hoặc thiếu `X-API-Token`

**Giải pháp:**
```bash
# Kiểm tra token đúng
cat secrets/credentials.txt | grep API_TOKEN

# Test với token đúng
curl -H "X-API-Token: $(grep '^API_TOKEN:' secrets/credentials.txt | awk '{print $2}')" \
  "https://osint.example.com/healthz"
```

### 3. Scan bị block/rate limit

**Nguyên nhân**: Quét quá nhanh

**Giải pháp:**
- Giảm `max_workers` xuống 1-2
- Tăng `sleep_after_scan_seconds`
- Sử dụng API keys cho các module (trong `init_config.json`)

### 4. Database đầy

**Giải pháp:**
- Giảm `EVENT_RETENTION_DAYS` và `OFFLINE_HOST_RETENTION_DAYS`
- Chạy cleanup thủ công:

```bash
# Vào container
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

## Tips vận hành

1. **Xem logs realtime:**
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

4. **Xem stats Neo4j:**
```cypher
// Trong Neo4j Browser
MATCH (n) RETURN labels(n) as type, count(*) as count
```

5. **Export dữ liệu:**
```bash
# Query và export JSON
curl -X POST "https://osint.example.com/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{"domain":"evilcorp.com","limit":10000}' \
  | jq '.results' > export.json
```

---

**Chúc bạn triển khai thành công!** 🎉

Nếu gặp vấn đề, vui lòng mở issue trên GitHub hoặc liên hệ.
