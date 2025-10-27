# Hướng dẫn gỡ cài đặt & Quản lý (Uninstall & Management Guide)

## Mục lục
- [Tạm dừng để sửa config](#tạm-dừng-để-sửa-config)
- [Gỡ cài đặt hoàn toàn](#gỡ-cài-đặt-hoàn-toàn)
- [Gỡ cài đặt nhưng giữ dữ liệu](#gỡ-cài-đặt-nhưng-giữ-dữ-liệu)
- [Chỉ xóa dữ liệu Neo4j](#chỉ-xóa-dữ-liệu-neo4j)
- [Gỡ Docker (tùy chọn)](#gỡ-docker-tùy-chọn)

---

## Tạm dừng để sửa config

Khi cần sửa `init_config.json`, thêm targets mới, hoặc cập nhật API keys mà KHÔNG mất dữ liệu.

### Phương pháp 1: Tạm dừng containers

```bash
cd ~/bbot-osint-mcp

# Dừng tất cả services
sudo docker compose stop

# Sửa config
nano init_config.json

# Ví dụ: Thêm target mới
# {
#   "targets": ["evilcorp.com", "newcorp.com", "target3.com"],
#   ...
# }

# Khởi động lại
sudo docker compose start

# Xem logs để đảm bảo config mới được load
sudo docker logs -f bbot_osint
```

**Lưu ý:** Khi dùng `stop/start`, volumes (Neo4j data) được giữ nguyên.

### Phương pháp 2: Chỉ restart OSINT service

Nếu chỉ sửa `init_config.json` hoặc `config/bbot.yml`:

```bash
cd ~/bbot-osint-mcp

# Sửa config
nano init_config.json

# Restart chỉ OSINT service (Neo4j vẫn chạy)
sudo docker compose restart osint

# Kiểm tra config mới
sudo docker logs -f bbot_osint | head -20
```

**Khi nào dùng:** Thay đổi targets, API keys, sleep times, scan_defaults.

### Phương pháp 3: Hot reload (không downtime)

Sửa config trong khi service đang chạy, sau đó restart:

```bash
cd ~/bbot-osint-mcp

# Service đang chạy, sửa config
nano init_config.json

# Chỉ cần restart osint, không cần stop
sudo docker compose restart osint

# Hoặc rebuild nếu sửa code
sudo docker compose up -d --build osint
```

### Phương pháp 4: Sửa .env (cần rebuild)

Nếu thay đổi biến môi trường:

```bash
cd ~/bbot-osint-mcp

# Dừng services
sudo docker compose down

# Sửa .env
nano .env

# Thay đổi ví dụ:
# EVENT_RETENTION_DAYS=60
# CLEANUP_ENABLED=false

# Khởi động lại (down/up để reload env)
sudo docker compose up -d

# Xem logs
sudo docker logs -f bbot_osint
```

### So sánh các phương pháp

| Phương pháp | Downtime | Giữ data | Use case |
|-------------|----------|----------|----------|
| `stop/start` | ✅ Có | ✅ Có | Sửa config an toàn |
| `restart osint` | ⚠️ Ngắn (~5s) | ✅ Có | Sửa init_config.json |
| `up -d --build` | ⚠️ Ngắn (~10s) | ✅ Có | Sửa code Python |
| `down/up` | ✅ Có | ✅ Có | Sửa .env hoặc docker-compose.yml |

### Ví dụ thực tế

#### Thêm target mới vào monitoring

```bash
cd ~/bbot-osint-mcp
sudo docker compose stop osint

# Backup config trước
cp init_config.json init_config.json.backup

# Thêm target
cat init_config.json | jq '.targets += ["newcorp.com"]' > init_config.json.tmp
mv init_config.json.tmp init_config.json

# Restart
sudo docker compose start osint

# Kiểm tra targets mới
curl -H "X-API-Token: $(cat secrets/api_token)" \
  https://osint.example.com/status | jq '.targets'
```

#### Thay đổi cycle sleep time

```bash
cd ~/bbot-osint-mcp

# Sửa cycle_sleep_seconds từ 3600 → 7200 (1h → 2h)
nano init_config.json
# Tìm "cycle_sleep_seconds": 3600
# Đổi thành "cycle_sleep_seconds": 7200

# Restart
sudo docker compose restart osint

# Verify
sudo docker logs bbot_osint 2>&1 | grep "Cycle sleep"
```

#### Cập nhật API keys

```bash
cd ~/bbot-osint-mcp

# Sửa API keys
nano init_config.json

# Ví dụ:
# "bbot_modules": {
#   "virustotal": { "api_key": "NEW_VT_KEY_HERE" },
#   "shodan_dns": { "api_key": "NEW_SHODAN_KEY" }
# }

# Apply changes
sudo docker compose restart osint

# Verify trong logs
sudo docker logs bbot_osint 2>&1 | grep -i "api key"
```

#### Tắt cleanup tạm thời

```bash
cd ~/bbot-osint-mcp

# Sửa .env
nano .env
# Đổi: CLEANUP_ENABLED=false

# Restart để apply
sudo docker compose down
sudo docker compose up -d

# Kiểm tra
curl -H "X-API-Token: $(cat secrets/api_token)" \
  https://osint.example.com/status | jq '.cleanup_enabled'
# Output: false
```

### Checklist sau khi sửa config

- [ ] Service đã khởi động lại: `sudo docker ps | grep bbot`
- [ ] Config mới được load: `sudo docker logs bbot_osint | head -30`
- [ ] Targets đúng: `curl -H "X-API-Token: $TOKEN" https://osint.example.com/status`
- [ ] Không có lỗi: `sudo docker logs bbot_osint 2>&1 | grep -i error`
- [ ] Scanner đang chạy: `sudo docker logs -f bbot_osint | grep "Scanning"`

### Rollback nếu có lỗi

```bash
# Nếu config mới gây lỗi
cd ~/bbot-osint-mcp

# Restore backup
cp init_config.json.backup init_config.json

# Restart
sudo docker compose restart osint

# Hoặc rollback toàn bộ
sudo docker compose down
git checkout init_config.json
sudo docker compose up -d
```

---

## Gỡ cài đặt hoàn toàn

Xóa tất cả: containers, images, volumes, dữ liệu, và source code.

### Bước 1: Dừng và xóa containers

```bash
cd ~/bbot-osint-mcp

# Dừng tất cả containers
sudo docker compose down

# Xóa containers và volumes
sudo docker compose down -v
```

### Bước 2: Xóa Docker images

```bash
# List images liên quan
sudo docker images | grep bbot

# Xóa images
sudo docker rmi bbot-osint-mcp-osint:latest
sudo docker rmi neo4j:5.23.1
sudo docker rmi caddy:2.8-alpine

# Hoặc xóa tất cả images không dùng
sudo docker image prune -a
```

### Bước 3: Xóa volumes (dữ liệu)

```bash
# List volumes
sudo docker volume ls | grep bbot

# Xóa từng volume
sudo docker volume rm bbot-osint-mcp_neo4j_data
sudo docker volume rm bbot-osint-mcp_neo4j_logs
sudo docker volume rm bbot-osint-mcp_caddy_data
sudo docker volume rm bbot-osint-mcp_caddy_config

# Hoặc xóa tất cả volumes không dùng
sudo docker volume prune
```

### Bước 4: Xóa source code

```bash
# Backup secrets trước nếu cần
cp ~/bbot-osint-mcp/secrets/credentials.txt ~/bbot-credentials-backup.txt

# Xóa toàn bộ thư mục
rm -rf ~/bbot-osint-mcp
```

### Bước 5: Dọn dẹp firewall rules (nếu không dùng nữa)

```bash
# Đóng ports 80/443 nếu không cần
sudo ufw delete allow 80/tcp
sudo ufw delete allow 443/tcp
sudo ufw status
```

### Bước 6: Xóa DNS records (tùy chọn)

Nếu không dùng subdomain `osint.example.com` nữa:
- Vào DNS provider (Cloudflare, etc.)
- Xóa A record trỏ đến VPS

---

## Gỡ cài đặt nhưng giữ dữ liệu

Xóa containers và images, nhưng giữ Neo4j data để có thể cài lại sau.

### Bước 1: Dừng containers (không xóa volumes)

```bash
cd ~/bbot-osint-mcp

# Chỉ dừng, không xóa volumes
sudo docker compose down
```

### Bước 2: Xóa images

```bash
sudo docker rmi bbot-osint-mcp-osint:latest
sudo docker rmi caddy:2.8-alpine
# Giữ Neo4j image nếu muốn
```

### Bước 3: Backup volumes (khuyến nghị)

```bash
# Tạo backup từ volume
sudo docker run --rm \
  -v bbot-osint-mcp_neo4j_data:/data \
  -v ~/backups:/backup \
  ubuntu tar czf /backup/neo4j-data-$(date +%Y%m%d).tar.gz /data

# Kiểm tra backup
ls -lh ~/backups/
```

### Bước 4: Xóa source code (giữ backup)

```bash
# Backup init_config.json và secrets
cp ~/bbot-osint-mcp/init_config.json ~/bbot-config-backup.json
cp ~/bbot-osint-mcp/secrets/credentials.txt ~/bbot-credentials-backup.txt

# Xóa source
rm -rf ~/bbot-osint-mcp
```

**Để cài lại sau:**

```bash
# Clone lại repo
git clone https://github.com/dn9uy3n/bbot-osint-mcp.git
cd bbot-osint-mcp

# Restore config
cp ~/bbot-config-backup.json init_config.json
mkdir -p secrets
cp ~/bbot-credentials-backup.txt secrets/credentials.txt

# Volumes cũ sẽ tự động được mount lại
sudo docker compose up -d
```

---

## Chỉ xóa dữ liệu Neo4j

Giữ hệ thống chạy nhưng xóa sạch database để bắt đầu lại.

### Cách 1: Xóa toàn bộ database

```bash
# Dừng service
sudo docker compose stop osint neo4j

# Xóa Neo4j volume
sudo docker volume rm bbot-osint-mcp_neo4j_data

# Start lại (database mới rỗng)
sudo docker compose up -d
```

### Cách 2: Xóa từng loại nodes (selective)

```bash
# SSH tunnel để kết nối Neo4j
ssh -L 7474:localhost:7474 -L 7687:localhost:7687 user@VPS_IP
```

Vào Neo4j Browser: `http://localhost:7474`

```cypher
// Xóa tất cả events
MATCH (e:Event)
DELETE e

// Xóa tất cả hosts offline
MATCH (h:Host {status: "offline"})
DETACH DELETE h

// Xóa orphan nodes
MATCH (n)
WHERE NOT (n)--()
DELETE n

// Xóa toàn bộ (cẩn thận!)
MATCH (n)
DETACH DELETE n
```

### Cách 3: Chạy cleanup cực mạnh

```bash
# Vào container
sudo docker exec -it bbot_osint bash

# Python shell
python3 << EOF
from app.repository import neo4j_driver
import time

# Delete all events
with neo4j_driver.driver.session() as session:
    session.run("MATCH (e:Event) DELETE e")
    
# Delete all offline hosts
with neo4j_driver.driver.session() as session:
    session.run("MATCH (h:Host {status: 'offline'}) DETACH DELETE h")
    
# Delete orphans
with neo4j_driver.driver.session() as session:
    session.run("MATCH (n) WHERE NOT (n)--() DELETE n")

print("Cleanup completed")
EOF
```

---

## Gỡ Docker (tùy chọn)

Nếu bạn muốn gỡ hoàn toàn Docker khỏi VPS:

### Ubuntu/Debian

```bash
# Dừng Docker
sudo systemctl stop docker
sudo systemctl stop docker.socket
sudo systemctl stop containerd

# Gỡ cài đặt
sudo apt-get purge docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo apt-get autoremove

# Xóa dữ liệu
sudo rm -rf /var/lib/docker
sudo rm -rf /var/lib/containerd
sudo rm -rf /etc/docker

# Xóa groups
sudo groupdel docker
```

---

## Checklist sau khi gỡ cài đặt

### ✅ Hoàn toàn sạch sẽ

- [ ] Containers đã xóa: `sudo docker ps -a | grep bbot`
- [ ] Images đã xóa: `sudo docker images | grep bbot`
- [ ] Volumes đã xóa: `sudo docker volume ls | grep bbot`
- [ ] Source code đã xóa: `ls ~/bbot-osint-mcp`
- [ ] Firewall rules đã xóa (nếu cần)
- [ ] DNS records đã xóa (nếu cần)

### ✅ Giữ dữ liệu để cài lại

- [ ] Volumes vẫn tồn tại: `sudo docker volume ls | grep bbot`
- [ ] Backup credentials: `ls ~/bbot-credentials-backup.txt`
- [ ] Backup config: `ls ~/bbot-config-backup.json`
- [ ] Backup Neo4j data: `ls ~/backups/neo4j-data-*.tar.gz`

---

## Troubleshooting

### Lỗi: "volume is in use"

```bash
# Kiểm tra container nào đang dùng
sudo docker ps -a | grep bbot

# Xóa containers trước
sudo docker rm -f $(sudo docker ps -aq --filter "name=bbot")

# Thử lại
sudo docker volume rm bbot-osint-mcp_neo4j_data
```

### Lỗi: "cannot remove image, image is being used"

```bash
# Force remove
sudo docker rmi -f bbot-osint-mcp-osint:latest

# Hoặc xóa tất cả dangling images
sudo docker image prune -a -f
```

### Không thể xóa thư mục (permission denied)

```bash
# Xóa với sudo
sudo rm -rf ~/bbot-osint-mcp

# Nếu vẫn lỗi, kiểm tra process đang dùng
sudo lsof +D ~/bbot-osint-mcp
```

### Restore từ backup

```bash
# Restore Neo4j data từ tar.gz
sudo docker run --rm \
  -v bbot-osint-mcp_neo4j_data:/data \
  -v ~/backups:/backup \
  ubuntu tar xzf /backup/neo4j-data-20251027.tar.gz -C /

# Restart services
cd ~/bbot-osint-mcp
sudo docker compose up -d
```

---

## Script tự động gỡ cài đặt

Tạo file `uninstall.sh`:

```bash
#!/bin/bash

echo "BBOT OSINT MCP - Uninstall Script"
echo "=================================="
echo ""
echo "Chọn tùy chọn:"
echo "1) Gỡ hoàn toàn (xóa tất cả)"
echo "2) Gỡ nhưng giữ dữ liệu"
echo "3) Chỉ xóa dữ liệu Neo4j"
echo "4) Hủy"
echo ""
read -p "Lựa chọn (1-4): " choice

case $choice in
  1)
    echo "Gỡ cài đặt hoàn toàn..."
    cd ~/bbot-osint-mcp
    sudo docker compose down -v
    sudo docker rmi bbot-osint-mcp-osint:latest neo4j:5.23.1 caddy:2.8-alpine
    cd ~
    rm -rf ~/bbot-osint-mcp
    echo "✅ Đã gỡ hoàn toàn!"
    ;;
  2)
    echo "Backup và gỡ cài đặt..."
    cp ~/bbot-osint-mcp/init_config.json ~/bbot-config-backup.json
    cp ~/bbot-osint-mcp/secrets/credentials.txt ~/bbot-credentials-backup.txt
    cd ~/bbot-osint-mcp
    sudo docker compose down
    cd ~
    rm -rf ~/bbot-osint-mcp
    echo "✅ Đã gỡ cài đặt! Dữ liệu được giữ trong Docker volumes."
    echo "Backup: ~/bbot-config-backup.json, ~/bbot-credentials-backup.txt"
    ;;
  3)
    echo "Xóa dữ liệu Neo4j..."
    cd ~/bbot-osint-mcp
    sudo docker compose stop neo4j
    sudo docker volume rm bbot-osint-mcp_neo4j_data
    sudo docker compose up -d
    echo "✅ Database đã được reset!"
    ;;
  4)
    echo "Hủy thao tác."
    ;;
  *)
    echo "Lựa chọn không hợp lệ."
    ;;
esac
```

**Sử dụng:**

```bash
# Download script
curl -O https://raw.githubusercontent.com/dn9uy3n/bbot-osint-mcp/main/scripts/uninstall.sh
chmod +x uninstall.sh

# Chạy
./uninstall.sh
```

---

**Quay lại:** [README.md](../README.md)

