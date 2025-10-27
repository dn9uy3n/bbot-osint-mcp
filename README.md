## BBOT OSINT MCP Stack (Docker)

Triển khai dịch vụ OSINT dựa trên BBOT với API FastAPI, Neo4j để lưu trữ kết quả (kèm timestamp và trạng thái), và MCP server để kết nối từ Cursor.

Tài liệu BBOT tham khảo: [GitHub BBOT](https://github.com/blacklanternsecurity/bbot)

### Mô tả dự án

Hệ thống hóa BBOT thành một dịch vụ OSINT chạy trên VPS: an toàn, có API, Neo4j để lưu dữ liệu đầy đủ (events, host, domain, ip, url, email), MCP server để thao tác từ Cursor. Tối ưu để chạy liên tục với ít luồng, giảm nguy cơ bị chặn.

### Tính năng

- Chạy BBOT với cấu hình "ít luồng" để tránh bị block, cho phép tích hợp API key qua file config.
- Lưu kết quả vào Neo4j, có trường thời gian `last_seen_ts` và `status` cho mỗi `Host`.
- API FastAPI để khởi chạy scan, query kết quả, và upsert dữ liệu từ client.
- MCP server để Cursor có thể kết nối và thực thi công cụ `osint.query`, `osint.scan`, `osint.events.query` an toàn.
- Cleanup sau scan (events quá hạn, host offline quá hạn, orphan nodes) và thông báo Telegram khi xong.
- Hỗ trợ cấu hình đầu vào qua `init_config.json` (targets, API keys module BBOT, Telegram bot).

### Kiến trúc

- `docker-compose.yml`: Neo4j và service OSINT (FastAPI + MCP).
- `config/bbot.yml`: cấu hình BBOT và API keys (mount vào container).
- `services/osint`: mã nguồn API, BBOT runner, MCP server.

### Chuẩn bị

1) Cài Docker và Docker Compose.
2) Sao chép `.env.example` thành `.env` và cập nhật biến môi trường an toàn.
3) Điền file `init_config.json` cho đầu vào ban đầu (targets, API keys BBOT, Telegram):
   - Mẫu: `init_config.json.example` (sao chép sang `init_config.json`)
   - Lưu ý: `init_config.json` đã nằm trong `.gitignore`, an toàn khi push public.

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

Lưu ý: nếu bạn vẫn muốn dùng `config/bbot.yml`, hệ thống sẽ merge thêm các `bbot_modules` từ `init_config.json` vào đó khi startup.

```bash
cp .env.example .env
cp init_config.json.example init_config.json
cp config/bbot.yml.example config/bbot.yml
```

Các khóa quan trọng trong `.env`:

- `API_TOKEN`: token bắt buộc ở header `X-API-Token` cho API/MCP.
- `NEO4J_USERNAME`, `NEO4J_PASSWORD`: tài khoản Neo4j.
- `BBOT_CONFIG_HOST_PATH`: đường dẫn file `bbot.yml` trên host.

### Khởi chạy (triển khai an toàn với Let's Encrypt/Caddy)

Trước khi chạy, hãy sinh secrets mạnh:

Linux/macOS:
```bash
bash scripts/init-secrets.sh
```

Windows (PowerShell):
```powershell
pwsh -File scripts/init-secrets.ps1
```

Thông tin đã sinh sẽ nằm ở `secrets/credentials.txt` để bạn đọc và dùng khi kết nối.

```bash
docker compose up -d --build
```

- Public: chỉ mở `80/443` trên reverse proxy Caddy. API/MCP sau proxy; Neo4j nội bộ.
- Caddy tự động xin chứng chỉ Let's Encrypt nếu domain trỏ về IP VPS.
- Biến môi trường cần thiết trong `.env`:

```env
LE_DOMAIN=osint.example.com
LE_EMAIL=admin@example.com
PUBLIC_BASE_URL=https://osint.example.com
```

- API/MCP public qua HTTPS: `https://$LE_DOMAIN/` và `https://$LE_DOMAIN/mcp`.

Lần khởi động đầu, API sẽ tạo constraint cho `Domain` và `Host`.

### Cấu hình BBOT chống block

- `engine.max_workers = 2`
- `web.spider_distance = 1`, `web.spider_depth = 2`, `web.spider_links_per_page = 10`
- Hạn chế tốc độ của `httpx` (nếu sử dụng module web).

Tham khảo cấu hình và presets/flags trong tài liệu BBOT: [BBOT README](https://github.com/blacklanternsecurity/bbot)

### API Usage

Header bắt buộc: `X-API-Token: <API_TOKEN>`

- Healthcheck:

```bash
curl http://localhost:8000/healthz
```

- Khởi chạy scan an toàn:

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

- Query kết quả:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{"domain":"evilcorp.com","online_only":true,"limit":50}'
```

### Cleanup và Thông báo Telegram

- Cleanup tự động sau mỗi scan, có thể điều chỉnh qua biến môi trường:
  - `CLEANUP_ENABLED=true|false`
  - `EVENT_RETENTION_DAYS=30`
  - `OFFLINE_HOST_RETENTION_DAYS=30`
  - `ORPHAN_CLEANUP_ENABLED=true|false`
- Telegram:
  - Đặt `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` trong `.env` để bật thông báo.
  - Sau mỗi scan, bot sẽ báo số events thu được và số lượng phần tử bị dọn dẹp.

- Query events (đầy đủ fidelity từ BBOT):

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

- Upsert trực tiếp (client cập nhật thủ công):

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
- Quan hệ `(:Host)-[:PART_OF]->(:Domain)`

Constraints khởi tạo:

```cypher
CREATE CONSTRAINT domain_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT host_unique IF NOT EXISTS FOR (h:Host) REQUIRE h.fqdn IS UNIQUE;
```

### MCP Server

- Mount tại `/mcp` trong cùng FastAPI, yêu cầu header `X-API-Token`.
- Tools:
  - `osint.query(domain?, host?, online_only?, limit=50)`
  - `osint.scan(targets, presets=["subdomain-enum"], allow_deadly=false)`
  - `osint.events.query(types?, modules?, domain?, host?, since_ts?, until_ts?, limit=200)`

### Tích hợp vào Cursor (MCP Client)

1) Cài đặt extension MCP Client của Cursor và cấu hình server HTTP:

```json
{
  "mcpServers": {
    "bbot-osint": {
      "type": "http",
      "url": "https://$LE_DOMAIN/mcp",
      "headers": {
        "X-API-Token": "YOUR_STRONG_TOKEN"
      }
    }
  }
}

### Hướng dẫn chi tiết triển khai Let's Encrypt với Caddy

1) Chuẩn bị DNS: tạo bản ghi A cho `$LE_DOMAIN` trỏ tới IP VPS.
2) Chỉnh `.env` điền `LE_DOMAIN`, `LE_EMAIL`, `PUBLIC_BASE_URL`.
3) Kiểm tra `reverse-proxy/Caddyfile` đã dùng biến `{$LE_DOMAIN}` và `{$LE_EMAIL}`.
4) Mở cổng 80/443 trên firewall VPS.
5) Khởi động stack:

```bash
docker compose up -d --build
```

6) Caddy sẽ tự động xin chứng chỉ từ Let's Encrypt và lưu trong volumes `caddy_data`.
7) Kiểm tra truy cập `https://$LE_DOMAIN/healthz` với header `X-API-Token`.

Troubleshooting:
- Nếu không ra chứng chỉ, kiểm tra DNS đã trỏ đúng, firewall mở 80/443, logs container `proxy`.
- Dùng `docker logs bbot_caddy` để xem chi tiết ACME.
```

2) Trong Cursor, restart MCP client. Bạn sẽ thấy các tools:
   - `osint.query`
   - `osint.scan`
   - `osint.events.query`

3) Gọi tools trực tiếp trong Command Palette hoặc từ chat. Ví dụ:

```text
Call MCP tool: osint.query {"domain":"evilcorp.com","online_only":true}
```

```python
# pseudo-client: gửi request tool tới /mcp theo chuẩn MCP client của bạn
```

### Bảo mật

- Luôn đặt `API_TOKEN` mạnh, truyền qua `X-API-Token`.
- Đặt dịch vụ sau reverse proxy có TLS (nginx/caddy/traefik) hoặc bật TLS ở uvicorn.
- Hạn chế IP truy cập hoặc VPN.
- Không chạy presets/flags "deadly" trừ khi bạn hiểu rủi ro (BBOT có cờ `--allow-deadly`).

### Reverse Proxy (ví dụ nginx)

```nginx
server {
  listen 443 ssl;
  server_name osint.example.com;

  ssl_certificate /etc/letsencrypt/live/osint.example.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/osint.example.com/privkey.pem;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

### Tips vận hành

- Điều chỉnh cấu hình BBOT ở `config/bbot.yml` để cân bằng tốc độ và an toàn.
- Theo dõi Neo4j Browser để kiểm tra dữ liệu.
- Log API/worker để giám sát tiến trình.


