# Hướng dẫn chi tiết init_config.json

## Mục lục
- [Tổng quan](#tổng-quan)
- [Cấu trúc cơ bản](#cấu-trúc-cơ-bản)
- [Targets - Danh sách domain](#targets---danh-sách-domain)
- [BBOT Modules - API Keys](#bbot-modules---api-keys)
- [Telegram Notifications](#telegram-notifications)
- [Scan Defaults](#scan-defaults)
- [Template đầy đủ tính năng](#template-đầy-đủ-tính-năng)
- [Best Practices](#best-practices)

---

## Tổng quan

File `init_config.json` là file cấu hình trung tâm cho BBOT OSINT Continuous Monitoring Stack. Tất cả các thiết lập quan trọng được định nghĩa ở đây.

**Vị trí file:** `~/bbot-osint-mcp/init_config.json`

**Cách apply thay đổi:**
```bash
# Sau khi sửa file
sudo docker compose restart osint
```

---

## Cấu trúc cơ bản

```json
{
  "targets": [...],
  "bbot_modules": {...},
  "TELEGRAM_BOT_TOKEN": "...",
  "TELEGRAM_CHAT_ID": "...",
  "scan_defaults": {...}
}
```

---

## Targets - Danh sách domain

### Cú pháp

```json
{
  "targets": [
    "domain1.com",
    "domain2.com",
    "domain3.net"
  ]
}
```

### Quy tắc

1. **Chỉ domain, không có protocol**
   - ✅ `"example.com"`
   - ❌ `"https://example.com"`
   - ❌ `"http://example.com"`

2. **Chỉ root domain hoặc subdomain**
   - ✅ `"example.com"` - sẽ scan tất cả subdomains
   - ✅ `"app.example.com"` - chỉ scan subdomain này
   - ❌ `"example.com/path"` - không hợp lệ

3. **Không giới hạn số lượng**
   - Có thể có 1 đến hàng trăm targets
   - Lưu ý: nhiều targets = cycle dài hơn

### Ví dụ thực tế

#### Single domain monitoring
```json
{
  "targets": [
    "mycompany.com"
  ]
}
```

#### Multiple domains (portfolio)
```json
{
  "targets": [
    "company1.com",
    "company2.net",
    "company3.org",
    "company4.io"
  ]
}
```

#### Mixed domains and subdomains
```json
{
  "targets": [
    "mainsite.com",           // Scan all subdomains
    "blog.mainsite.com",      // Also specifically scan blog
    "api.service.com",        // Only scan this subdomain
    "clientsite.com"
  ]
}
```

#### Large-scale monitoring (20+ domains)
```json
{
  "targets": [
    "client1.com",
    "client2.com",
    "client3.com",
    // ... 17 more ...
    "client20.com"
  ],
  "scan_defaults": {
    "target_sleep_seconds": 600,      // 10 min between targets
    "cycle_sleep_seconds": 14400      // 4 hours between cycles
  }
}
```

### Tính toán thời gian

**Công thức:**
```
Cycle time = (targets × avg_scan_time) + (targets-1 × target_sleep) + cycle_sleep
```

**Ví dụ:** 10 targets, mỗi scan 5 phút, target_sleep=300s, cycle_sleep=3600s
```
Cycle time = (10 × 5min) + (9 × 5min) + 60min
           = 50min + 45min + 60min
           = 155 phút (~2.5 giờ)
```

---

## BBOT Modules - API Keys

### Tổng quan

BBOT hỗ trợ hàng chục modules để thu thập OSINT data. Nhiều modules cần API keys để hoạt động.

### Danh sách modules phổ biến

| Module | Miễn phí? | Công dụng | Link đăng ký |
|--------|-----------|-----------|--------------|
| **virustotal** | ✅ Có free tier | Subdomain, DNS records | https://www.virustotal.com/gui/join-us |
| **shodan** | ⚠️ Có free tier | Open ports, services | https://account.shodan.io/register |
| **securitytrails** | ⚠️ 50 req/month | Subdomain enum, DNS history | https://securitytrails.com/app/signup |
| **censys** | ⚠️ 250 req/month | Certificate search, hosts | https://search.censys.io/register |
| **hunter** | ⚠️ 25 req/month | Email addresses | https://hunter.io/users/sign_up |
| **dehashed** | ❌ Paid | Leaked credentials | https://dehashed.com/register |
| **bevigil** | ✅ Free | Mobile app analysis | https://bevigil.com/osint-api |
| **binaryedge** | ⚠️ 250 req/month | Internet scanning | https://app.binaryedge.io/sign-up |
| **fullhunt** | ⚠️ Free tier | Attack surface | https://fullhunt.io/signup |
| **github** | ✅ Free | GitHub repos, secrets | https://github.com/settings/tokens |
| **urlscan** | ✅ Free | Website scanner | https://urlscan.io/user/signup |
| **leakix** | ✅ Free | Leaked data | https://leakix.net/ |
| **c99** | ❌ Paid | Multiple sources | https://api.c99.nl/ |

### Cú pháp

```json
{
  "bbot_modules": {
    "module_name": {
      "api_key": "YOUR_API_KEY_HERE"
    }
  }
}
```

### Ví dụ cơ bản

```json
{
  "bbot_modules": {
    "virustotal": {
      "api_key": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6"
    },
    "shodan_dns": {
      "api_key": "ABC123DEF456GHI789JKL012MNO345"
    },
    "securitytrails": {
      "api_key": "st_abc123def456ghi789jkl012mno345pqr678"
    }
  }
}
```

### Multiple API keys (rotation)

Một số modules hỗ trợ nhiều keys để tránh rate limit:

```json
{
  "bbot_modules": {
    "c99": {
      "api_key": [
        "KEY_1_HERE",
        "KEY_2_HERE",
        "KEY_3_HERE"
      ]
    },
    "shodan_dns": {
      "api_key": [
        "SHODAN_KEY_1",
        "SHODAN_KEY_2"
      ]
    }
  }
}
```

### Ví dụ đầy đủ nhiều modules

```json
{
  "bbot_modules": {
    "virustotal": {
      "api_key": "YOUR_VT_API_KEY"
    },
    "shodan_dns": {
      "api_key": "YOUR_SHODAN_API_KEY"
    },
    "securitytrails": {
      "api_key": "YOUR_ST_API_KEY"
    },
    "censys": {
      "api_id": "YOUR_CENSYS_API_ID",
      "api_secret": "YOUR_CENSYS_API_SECRET"
    },
    "hunter": {
      "api_key": "YOUR_HUNTER_API_KEY"
    },
    "github": {
      "api_key": "ghp_YOUR_GITHUB_TOKEN"
    },
    "bevigil": {
      "api_key": "YOUR_BEVIGIL_API_KEY"
    },
    "fullhunt": {
      "api_key": "YOUR_FULLHUNT_API_KEY"
    },
    "binaryedge": {
      "api_key": "YOUR_BINARYEDGE_API_KEY"
    }
  }
}
```

### Modules không cần API key

Các modules sau hoạt động mà không cần key:

```json
{
  "scan_defaults": {
    "presets": ["subdomain-enum"],
    "flags": [],
    // Các modules này tự động chạy:
    // - anubisdb (free subdomain enum)
    // - hackertarget (free DNS tools)
    // - dnsdumpster (free DNS recon)
    // - sublist3r (aggregator)
    // - crt.sh (certificate transparency)
    // - rapiddns (DNS records)
  }
}
```

### Lấy API keys

#### VirusTotal
1. Đăng ký: https://www.virustotal.com/gui/join-us
2. Vào Profile → API Key
3. Copy key (dạng: `a1b2c3d4e5f6...`)

#### Shodan
1. Đăng ký: https://account.shodan.io/register
2. Vào Account → API Key
3. Copy key (dạng: `ABC123DEF456...`)

#### SecurityTrails
1. Đăng ký: https://securitytrails.com/app/signup
2. Vào API → Generate API Key
3. Copy key (dạng: `st_abc123def456...`)

#### GitHub (cho secrets scanning)
1. Vào: https://github.com/settings/tokens
2. Generate new token (classic)
3. Chọn scopes: `repo`, `read:org`
4. Copy token (dạng: `ghp_...`)

---

## Telegram Notifications

### Tại sao cần Telegram?

- Nhận thông báo ngay khi mỗi cycle hoàn thành
- Biết được số lượng events tìm thấy
- Theo dõi cleanup statistics
- Không cần SSH vào server để check

### Cú pháp

```json
{
  "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
  "TELEGRAM_CHAT_ID": "-1001234567890"
}
```

### Cách lấy Telegram Bot Token

#### Bước 1: Tạo bot
1. Mở Telegram, tìm `@BotFather`
2. Gửi: `/newbot`
3. Đặt tên bot: `My OSINT Monitor`
4. Đặt username: `my_osint_bot` (phải kết thúc bằng `bot`)
5. Nhận token (dạng: `123456789:ABCdefGHI...`)

#### Bước 2: Lấy Chat ID

**Option A: Personal chat**
1. Start chat với bot của bạn
2. Gửi tin nhắn bất kỳ: `/start`
3. Truy cập: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Tìm `"chat":{"id":123456789}` trong response
5. Copy số `123456789`

**Option B: Group chat**
1. Tạo group, add bot vào
2. Gửi tin nhắn trong group
3. Truy cập: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Tìm `"chat":{"id":-1001234567890}` (số âm)
5. Copy `-1001234567890`

**Option C: Dùng bot helper**
1. Tìm `@userinfobot` trên Telegram
2. Start chat
3. Bot sẽ reply với user ID của bạn

### Ví dụ

```json
{
  "TELEGRAM_BOT_TOKEN": "6847291035:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",
  "TELEGRAM_CHAT_ID": "987654321"
}
```

### Test Telegram config

Sau khi cấu hình xong:

```bash
# Test gửi tin nhắn
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage" \
  -d "chat_id=<YOUR_CHAT_ID>" \
  -d "text=Test from BBOT OSINT"
```

Nếu nhận được tin nhắn → cấu hình đúng ✅

### Message format

Sau mỗi cycle, bạn sẽ nhận tin nhắn:

```
🔍 Scan cycle completed

Duration: 1534s
Targets: 3
Events: 2139

Cleanup:
- Events deleted: 234
- Offline hosts deleted: 12
- Orphan nodes deleted: 8
```

### Tắt Telegram (optional)

Nếu không muốn thông báo, để trống:

```json
{
  "TELEGRAM_BOT_TOKEN": "",
  "TELEGRAM_CHAT_ID": ""
}
```

---

## Scan Defaults

### Tổng quan

Section `scan_defaults` định nghĩa cách BBOT chạy scan và thời gian nghỉ.

### Cú pháp đầy đủ

```json
{
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

### Tham số chi tiết

#### 1. presets (danh sách preset scan)

BBOT có các preset được định nghĩa sẵn:

```json
{
  "presets": ["subdomain-enum"]
}
```

**Các preset phổ biến:**

| Preset | Mô tả | Modules |
|--------|-------|---------|
| `subdomain-enum` | Tìm subdomains | anubisdb, crt, hackertarget, virustotal, etc. |
| `spider` | Crawl website | httpx, spider modules |
| `web-basic` | Web recon cơ bản | httpx, wappalyzer, robots |
| `email-enum` | Tìm emails | hunter, dehashed |
| `cloud-enum` | Cloud assets | azure, aws modules |
| ~~`aggressive`~~ | (không còn hỗ trợ) | Sử dụng kết hợp nhiều preset thay thế |

**Multiple presets:**
```json
{
  "presets": ["subdomain-enum", "spider", "email-enum"]
}
```

**⚠️ Lưu ý:** `aggressive` không còn khả dụng. Nếu cần mạnh hơn, hãy dùng nhiều preset cùng lúc: `["subdomain-enum", "spider", "email-enum"]`.

#### 2. flags (tùy chọn nâng cao)

```json
{
  "flags": [
    "subdomain-enum",   // Enable subdomain enumeration
    "active",           // Active scanning (có thể gây chú ý)
    "safe"              // Chỉ passive scanning (an toàn)
  ]
}
```

**Recommended:** Để trống `[]` và chỉ dùng `presets`

#### 3. max_workers (số luồng đồng thời)

```json
{
  "max_workers": 2
}
```

| Giá trị | Use case | Tốc độ | Nguy cơ block |
|---------|----------|--------|---------------|
| 1 | Cực kỳ thận trọng | Chậm | Rất thấp |
| 2 | **Production (recommended)** | Trung bình | Thấp |
| 3-5 | Testing/urgent | Nhanh | Trung bình |
| 10+ | ⚠️ Không khuyến nghị | Rất nhanh | Cao |

#### 4. spider_depth (độ sâu crawl)

```json
{
  "spider_depth": 2
}
```

| Giá trị | Crawl level | Số pages | Use case |
|---------|-------------|----------|----------|
| 0 | Không crawl | 0 | Chỉ subdomain enum |
| 1 | Homepage only | ~10 | Light recon |
| 2 | **Recommended** | ~100 | Normal recon |
| 3 | Deep crawl | ~1000 | Thorough scan |
| 4+ | ⚠️ Rất sâu | 10000+ | Có thể quá lâu |

#### 5. spider_distance (khoảng cách từ seed)

```json
{
  "spider_distance": 1
}
```

- `0`: Chỉ crawl chính xác domain target
- `1`: Crawl domain và subdomains (recommended)
- `2+`: Crawl cả external links (không khuyến nghị)

#### 6. spider_links_per_page

```json
{
  "spider_links_per_page": 10
}
```

Giới hạn số links theo dõi trên mỗi page.

- `5`: Rất thận trọng
- `10`: **Recommended**
- `20+`: Có thể crawl quá nhiều

#### 7. allow_deadly (modules nguy hiểm)

```json
{
  "allow_deadly": false
}
```

- `false`: **Recommended** - Chỉ passive modules
- `true`: ⚠️ Bật active scanning (nuclei, exploit modules)

**⚠️ WARNING:** `allow_deadly: true` có thể:
- Trigger IDS/IPS
- Bị coi là tấn công
- Vi phạm ToS

#### 8. target_sleep_seconds (nghỉ giữa targets)

```json
{
  "target_sleep_seconds": 300
}
```

Xem chi tiết: [SLEEP_PARAMETERS.md](../SLEEP_PARAMETERS.md)

| Giá trị | Use case |
|---------|----------|
| 0 | ⚠️ Không nghỉ (nguy hiểm) |
| 60-120 | Testing |
| 300 | **Production (1-5 targets)** |
| 600 | Production (6-20 targets) |
| 900+ | Large scale (20+ targets) |

#### 9. cycle_sleep_seconds (nghỉ giữa cycles)

```json
{
  "cycle_sleep_seconds": 3600
}
```

| Giá trị | Chu kỳ | Use case |
|---------|---------|----------|
| 600 | 10 phút | Development/testing |
| 1800 | 30 phút | Urgent monitoring |
| 3600 | **1 giờ** | **Production frequent** |
| 7200 | 2 giờ | Production balanced |
| 14400 | 4 giờ | Production conservative |
| 86400 | 24 giờ | Daily audit |

---

## Template đầy đủ tính năng

### Template 1: Production Standard (Recommended)

Cân bằng tốc độ, độ sâu, và an toàn.

```json
{
  "targets": [
    "example.com",
    "client1.com",
    "client2.net"
  ],
  "bbot_modules": {
    "virustotal": {
      "api_key": "YOUR_VIRUSTOTAL_API_KEY"
    },
    "shodan_dns": {
      "api_key": "YOUR_SHODAN_API_KEY"
    },
    "securitytrails": {
      "api_key": "YOUR_SECURITYTRAILS_API_KEY"
    },
    "hunter": {
      "api_key": "YOUR_HUNTER_API_KEY"
    },
    "github": {
      "api_key": "ghp_YOUR_GITHUB_TOKEN"
    }
  },
  "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
  "TELEGRAM_CHAT_ID": "987654321",
  "scan_defaults": {
    "presets": ["subdomain-enum", "email-enum"],
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

### Template 2: Conservative (An toàn tối đa)

Cho free API keys hoặc môi trường nhạy cảm.

```json
{
  "targets": [
    "example.com"
  ],
  "bbot_modules": {
    "virustotal": {
      "api_key": "YOUR_VT_API_KEY"
    }
  },
  "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
  "TELEGRAM_CHAT_ID": "987654321",
  "scan_defaults": {
    "presets": ["subdomain-enum"],
    "flags": ["safe"],
    "max_workers": 1,
    "spider_depth": 1,
    "spider_distance": 0,
    "spider_links_per_page": 5,
    "allow_deadly": false,
    "target_sleep_seconds": 600,
    "cycle_sleep_seconds": 7200
  }
}
```

### Template 3: Aggressive (Paid APIs, nhiều resources)

Scan nhanh với API keys paid.

```json
{
  "targets": [
    "target1.com",
    "target2.com",
    "target3.com",
    "target4.com",
    "target5.com"
  ],
  "bbot_modules": {
    "virustotal": {
      "api_key": "YOUR_VT_KEY"
    },
    "shodan_dns": {
      "api_key": [
        "SHODAN_KEY_1",
        "SHODAN_KEY_2",
        "SHODAN_KEY_3"
      ]
    },
    "securitytrails": {
      "api_key": "YOUR_ST_KEY"
    },
    "censys": {
      "api_id": "YOUR_CENSYS_ID",
      "api_secret": "YOUR_CENSYS_SECRET"
    },
    "dehashed": {
      "api_key": "YOUR_DEHASHED_KEY",
      "username": "YOUR_USERNAME"
    },
    "c99": {
      "api_key": [
        "C99_KEY_1",
        "C99_KEY_2"
      ]
    }
  },
  "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
  "TELEGRAM_CHAT_ID": "987654321",
  "scan_defaults": {
    "presets": ["subdomain-enum", "spider", "email-enum", "cloud-enum"],
    "flags": [],
    "max_workers": 3,
    "spider_depth": 3,
    "spider_distance": 1,
    "spider_links_per_page": 15,
    "allow_deadly": false,
    "target_sleep_seconds": 180,
    "cycle_sleep_seconds": 1800
  }
}
```

### Template 4: Large Scale (20+ domains)

Monitoring nhiều domains trong portfolio.

```json
{
  "targets": [
    "client01.com", "client02.com", "client03.com", "client04.com",
    "client05.com", "client06.com", "client07.com", "client08.com",
    "client09.com", "client10.com", "client11.com", "client12.com",
    "client13.com", "client14.com", "client15.com", "client16.com",
    "client17.com", "client18.com", "client19.com", "client20.com"
  ],
  "bbot_modules": {
    "virustotal": {
      "api_key": "YOUR_VT_KEY"
    },
    "shodan_dns": {
      "api_key": "YOUR_SHODAN_KEY"
    }
  },
  "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
  "TELEGRAM_CHAT_ID": "987654321",
  "scan_defaults": {
    "presets": ["subdomain-enum"],
    "flags": [],
    "max_workers": 2,
    "spider_depth": 1,
    "spider_distance": 0,
    "spider_links_per_page": 5,
    "allow_deadly": false,
    "target_sleep_seconds": 600,
    "cycle_sleep_seconds": 14400
  }
}
```

**⏱️ Cycle time estimate:** ~5 hours per cycle

### Template 5: Minimal (Không API keys)

Chỉ dùng free modules, không cần API keys.

```json
{
  "targets": [
    "example.com"
  ],
  "bbot_modules": {},
  "TELEGRAM_BOT_TOKEN": "",
  "TELEGRAM_CHAT_ID": "",
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

**Modules hoạt động:** anubisdb, crt.sh, hackertarget, dnsdumpster, rapiddns

---

## Best Practices

### 1. Bắt đầu nhỏ, mở rộng dần

```json
// Bước 1: Test với 1 domain
{
  "targets": ["example.com"],
  "scan_defaults": {
    "cycle_sleep_seconds": 600
  }
}

// Bước 2: Thêm API keys
{
  "bbot_modules": {
    "virustotal": {"api_key": "..."}
  }
}

// Bước 3: Thêm targets
{
  "targets": ["example.com", "client1.com", "client2.com"]
}

// Bước 4: Tối ưu sleep times
{
  "scan_defaults": {
    "target_sleep_seconds": 300,
    "cycle_sleep_seconds": 3600
  }
}
```

### 2. Backup trước khi thay đổi

```bash
cp init_config.json init_config.json.backup-$(date +%Y%m%d)
```

### 3. Validate JSON syntax

```bash
# Check JSON syntax
cat init_config.json | jq '.'

# Nếu lỗi → fix syntax
# Nếu OK → safe to apply
```

### 4. Monitor first cycle

Sau khi apply config mới:

```bash
# Watch logs
sudo docker logs -f bbot_osint | grep -E "Scanning|Sleep|Cycle|Error"

# Check status
curl -H "X-API-Token: $(cat secrets/api_token)" \
  https://osint.example.com/status | jq '.'
```

### 5. Adjust based on results

Nếu thấy rate limit errors:
```json
{
  "scan_defaults": {
    "max_workers": 1,              // Giảm từ 2 → 1
    "target_sleep_seconds": 600,   // Tăng từ 300 → 600
    "cycle_sleep_seconds": 7200    // Tăng từ 3600 → 7200
  }
}
```

Nếu quá chậm:
```json
{
  "scan_defaults": {
    "max_workers": 3,              // Tăng từ 2 → 3
    "target_sleep_seconds": 180,   // Giảm từ 300 → 180
    "cycle_sleep_seconds": 1800    // Giảm từ 3600 → 1800
  }
}
```

### 6. Document your config

Thêm comments bằng cách tạo file `init_config.notes.txt`:

```txt
init_config.json - Production Config
Last updated: 2025-10-27
Targets: 5 client domains
API Keys: VT, Shodan, SecurityTrails (all paid)
Cycle time: ~2 hours
Notes: Conservative settings for paid APIs
```

### 7. Version control

```bash
# Track changes
git add init_config.json
git commit -m "Updated targets: added client3.com"
```

### 8. Security

- ❌ **NEVER** commit `init_config.json` với API keys thật
- ✅ Dùng `init_config.json.example` với placeholders
- ✅ Add `init_config.json` vào `.gitignore`

---

## Troubleshooting

### Config không được load

```bash
# Check logs
sudo docker logs bbot_osint | grep "init_config"

# Common issues:
# - JSON syntax error → validate with jq
# - File không tồn tại → check path
# - Permission denied → check file permissions
```

### API keys không hoạt động

```bash
# Test API key
# VirusTotal:
curl -H "x-apikey: YOUR_VT_KEY" \
  "https://www.virustotal.com/api/v3/domains/example.com"

# Shodan:
curl "https://api.shodan.io/shodan/host/8.8.8.8?key=YOUR_SHODAN_KEY"
```

### Telegram không nhận tin nhắn

```bash
# Test bot
curl -X POST "https://api.telegram.org/botYOUR_TOKEN/sendMessage" \
  -d "chat_id=YOUR_CHAT_ID" \
  -d "text=Test"

# Check logs
sudo docker logs bbot_osint | grep -i telegram
```

---

**Quay lại:** [README.md](../README.md)

