# Giải thích chi tiết về tham số Sleep Time

## Tổng quan

Hệ thống sử dụng **2 loại thời gian nghỉ** khác nhau để tránh bị block và tối ưu hóa việc thu thập dữ liệu:

```
Cycle 1: [Target1] --target_sleep--> [Target2] --target_sleep--> [Target3]
                                                                      |
                                                              --cycle_sleep--
                                                                      |
Cycle 2: [Target1] --target_sleep--> [Target2] --target_sleep--> [Target3]
```

---

## 1. `target_sleep_seconds` - Thời gian nghỉ giữa các targets

### Mục đích
Nghỉ **giữa mỗi lần scan từng target** trong cùng một chu kỳ.

### Khi nào được áp dụng
- Sau khi scan xong `target1.com`
- **Trước khi** bắt đầu scan `target2.com`
- Giúp giảm tải và tránh bị phát hiện quét liên tục

### Ví dụ minh họa

```json
{
  "targets": ["target1.com", "target2.com", "target3.com"],
  "scan_defaults": {
    "target_sleep_seconds": 300
  }
}
```

**Timeline:**
```
00:00 - Bắt đầu scan target1.com
00:05 - target1.com hoàn thành (1000 events)
00:05 - 00:10 → 😴 Sleep 300s (5 phút)

00:10 - Bắt đầu scan target2.com
00:15 - target2.com hoàn thành (800 events)
00:15 - 00:20 → 😴 Sleep 300s (5 phút)

00:20 - Bắt đầu scan target3.com
00:25 - target3.com hoàn thành (1200 events)
00:25 - KHÔNG sleep (là target cuối cùng)
       → Chuyển sang cycle_sleep
```

### Tại sao cần target_sleep?

**Vấn đề:** Quét liên tục nhiều domain từ cùng 1 IP
```
Your_VPS_IP → target1.com (1000 requests)
Your_VPS_IP → target2.com (1000 requests) ← ngay lập tức
Your_VPS_IP → target3.com (1000 requests) ← ngay lập tức
```
→ ⚠️ IP bị đánh dấu đáng ngờ, có thể bị block

**Giải pháp:** Thêm khoảng cách thời gian
```
Your_VPS_IP → target1.com (1000 requests)
                ⏰ 5 phút
Your_VPS_IP → target2.com (1000 requests)
                ⏰ 5 phút  
Your_VPS_IP → target3.com (1000 requests)
```
→ ✅ Hành vi tự nhiên hơn, giảm nguy cơ block

### Khuyến nghị giá trị

| Số lượng targets | Giá trị khuyến nghị | Lý do |
|------------------|---------------------|-------|
| 1-3 targets | 180-300s (3-5 phút) | Đủ để tránh pattern |
| 4-10 targets | 300-600s (5-10 phút) | Nhiều targets cần thận trọng hơn |
| 10+ targets | 600-900s (10-15 phút) | Scan kéo dài, cần spacing lớn |
| Free API tier | 600+ s | API free thường có rate limit nghiêm |

---

## 2. `cycle_sleep_seconds` - Thời gian nghỉ giữa các chu kỳ

### Mục đích
Nghỉ **sau khi scan xong TẤT CẢ targets** trong một chu kỳ, trước khi bắt đầu chu kỳ mới.

### Khi nào được áp dụng
- Sau khi hoàn thành target cuối cùng trong danh sách
- **Trước khi** bắt đầu lại từ target đầu tiên
- Cho phép hệ thống và các dịch vụ "rest"

### Ví dụ minh họa

```json
{
  "targets": ["target1.com", "target2.com"],
  "scan_defaults": {
    "target_sleep_seconds": 300,
    "cycle_sleep_seconds": 3600
  }
}
```

**Timeline đầy đủ:**
```
=== CYCLE 1 ===
00:00 - Scan target1.com (5 phút)
00:05 - 😴 target_sleep 300s
00:10 - Scan target2.com (5 phút)
00:15 - Hoàn thành cycle 1
00:15 - 01:15 → 😴😴😴 cycle_sleep 3600s (1 giờ)

=== CYCLE 2 ===
01:15 - Scan target1.com (5 phút)
01:20 - 😴 target_sleep 300s
01:25 - Scan target2.com (5 phút)
01:30 - Hoàn thành cycle 2
01:30 - 02:30 → 😴😴😴 cycle_sleep 3600s (1 giờ)

=== CYCLE 3 ===
02:30 - Scan target1.com...
...lặp lại vô hạn
```

### Tại sao cần cycle_sleep?

**Vấn đề:** Scan lặp đi lặp lại liên tục

```
Scan all targets → Cleanup → Scan all targets → Cleanup...
```
Mỗi chu kỳ 20 phút → 72 chu kỳ/ngày → Quá nhiều!

**Hậu quả:**
- 🚫 API keys bị rate limit
- 🚫 IP VPS bị blacklist
- 🚫 Database phình to (quá nhiều duplicate data)
- 🚫 Không cần thiết (dữ liệu không thay đổi nhanh đến vậy)

**Giải pháp:** Cycle sleep cho đủ thời gian

```
Scan all targets → Cleanup → 😴 1 giờ → Scan all targets → ...
```
24 chu kỳ/ngày → Hợp lý!

### Khuyến nghị giá trị

| Use case | Giá trị khuyến nghị | Lý do |
|----------|---------------------|-------|
| **Development/Testing** | 300-600s (5-10 phút) | Test nhanh |
| **Production monitoring** | 3600-7200s (1-2 giờ) | Cân bằng freshness và an toàn |
| **Daily check** | 86400s (24 giờ) | Dữ liệu ít thay đổi |
| **Weekly audit** | 604800s (7 ngày) | Chỉ cần kiểm tra định kỳ |

---

## 3. So sánh trực quan

### Scenario: 3 targets, target_sleep=300s, cycle_sleep=3600s

```
Timeline:
│
├─ Cycle 1 Start (00:00)
│  ├─ Target 1 scan (5 min) ──────────────► [00:00 - 00:05]
│  ├─ 😴 target_sleep (5 min) ────────────► [00:05 - 00:10]
│  ├─ Target 2 scan (5 min) ──────────────► [00:10 - 00:15]
│  ├─ 😴 target_sleep (5 min) ────────────► [00:15 - 00:20]
│  ├─ Target 3 scan (5 min) ──────────────► [00:20 - 00:25]
│  └─ Cleanup + Telegram notify ──────────► [00:25]
│
├─ 😴😴😴 cycle_sleep (60 min) ──────────────► [00:25 - 01:25]
│
├─ Cycle 2 Start (01:25)
│  ├─ Target 1 scan...
│  └─ ...
```

**Tổng thời gian 1 cycle:** 25 phút actual work + 60 phút rest = 85 phút

---

## 4. Cấu hình thực tế

### Case 1: Monitoring nhanh (cho development)

```json
{
  "targets": ["myapp.com"],
  "scan_defaults": {
    "target_sleep_seconds": 0,
    "cycle_sleep_seconds": 600
  }
}
```
- 1 target duy nhất → không cần target_sleep
- Cycle mỗi 10 phút cho testing nhanh

### Case 2: Production monitoring chuẩn

```json
{
  "targets": ["app1.com", "app2.com", "app3.com"],
  "scan_defaults": {
    "target_sleep_seconds": 300,
    "cycle_sleep_seconds": 3600
  }
}
```
- 3 targets → sleep 5 phút giữa mỗi target
- Cycle lặp mỗi giờ

### Case 3: Large scale monitoring

```json
{
  "targets": ["t1.com", "t2.com", ..., "t20.com"],
  "scan_defaults": {
    "target_sleep_seconds": 600,
    "cycle_sleep_seconds": 7200
  }
}
```
- 20 targets → sleep 10 phút giữa targets
- Cycle mỗi 2 giờ để an toàn

### Case 4: Daily audit mode

```json
{
  "targets": ["client1.com", "client2.com"],
  "scan_defaults": {
    "target_sleep_seconds": 1800,
    "cycle_sleep_seconds": 86400
  }
}
```
- Sleep 30 phút giữa targets (rất an toàn)
- Cycle mỗi 24 giờ (1 lần/ngày)

---

## 5. Công thức tính toán

### Tổng thời gian 1 cycle

```
Total = (Scan_Time_Per_Target × Num_Targets) 
      + (target_sleep_seconds × (Num_Targets - 1))
      + cycle_sleep_seconds
```

**Ví dụ:**
- 3 targets, mỗi target scan 5 phút
- target_sleep = 300s
- cycle_sleep = 3600s

```
Total = (5min × 3) + (300s × 2) + 3600s
      = 15min + 10min + 60min
      = 85 phút
```

### Số chu kỳ mỗi ngày

```
Cycles_Per_Day = 86400 / Total_Cycle_Time_In_Seconds
```

**Ví dụ trên:**
```
Cycles_Per_Day = 86400 / (85 × 60)
               = 86400 / 5100
               ≈ 17 chu kỳ/ngày
```

---

## 6. Best Practices

### ✅ DO

1. **Bắt đầu bảo thủ, sau đó tối ưu**
   ```json
   {
     "target_sleep_seconds": 600,
     "cycle_sleep_seconds": 7200
   }
   ```
   Chạy vài ngày, nếu không có vấn đề → giảm dần

2. **Tăng sleep nếu gặp warning**
   - Thấy "rate limit exceeded" → tăng gấp đôi
   - API key bị suspend → tăng gấp 3-4 lần

3. **Sử dụng Telegram để monitor**
   - Nhận thông báo sau mỗi cycle
   - Biết được timing thực tế

### ❌ DON'T

1. **Đặt cả 2 tham số = 0**
   ```json
   {"target_sleep_seconds": 0, "cycle_sleep_seconds": 0}
   ```
   → ⚠️ Scan liên tục không nghỉ → Chắc chắn bị block

2. **Quá tham lam với free API**
   - Free tier thường có giới hạn nghiêm
   - Nên dùng cycle_sleep >= 3600s

3. **Quên tính toán tổng thời gian**
   - 20 targets × 5 phút = 100 phút chỉ để scan
   - Chưa kể sleep time → có thể cycle quá dài

---

## 7. Troubleshooting

### Vấn đề: Bị rate limit từ API providers

**Triệu chứng:**
```
ERROR: SecurityTrails API: Rate limit exceeded
ERROR: Shodan: Too many requests
```

**Giải pháp:**
```json
{
  "target_sleep_seconds": 900,
  "cycle_sleep_seconds": 10800
}
```
Tăng lên 15 phút và 3 giờ

### Vấn đề: Database quá lớn

**Triệu chứng:**
- Neo4j volume > 50GB
- Query chậm

**Giải pháp:**
1. Tăng `cycle_sleep_seconds` để giảm tần suất scan
2. Giảm `EVENT_RETENTION_DAYS` để cleanup nhiều hơn
3. Xem xét có cần scan thường xuyên không

### Vấn đề: Dữ liệu không đủ fresh

**Triệu chứng:**
- Subdomain mới không phát hiện kịp
- Muốn realtime hơn

**Giải pháp:**
```json
{
  "cycle_sleep_seconds": 1800
}
```
Giảm xuống 30 phút, nhưng phải:
- Có API keys paid tier
- Monitor cẩn thận rate limits
- Chuẩn bị bị block và có backup plan

---

## 8. Monitoring

### Check logs để verify timing

```bash
docker logs -f bbot_osint | grep -E "Sleep|Cycle"
```

**Output mẫu:**
```
[INFO] Sleeping 300s before next target...
[INFO] === Cycle completed in 1534s, total events: 2847 ===
[INFO] Sleeping 3600s until next cycle...
[INFO] === Starting scan cycle at 2025-01-15 14:30:00 ===
```

### Query Neo4j để kiểm tra data freshness

```cypher
// Kiểm tra last_seen_ts của hosts
MATCH (h:Host)
RETURN h.fqdn, h.last_seen_ts, 
       datetime({epochSeconds: h.last_seen_ts}) as last_seen
ORDER BY h.last_seen_ts DESC
LIMIT 20
```

Nếu `last_seen` của hầu hết hosts cách nhau ~1 giờ → cycle_sleep = 3600s đang hoạt động đúng.

---

**Tóm lại:**
- `target_sleep_seconds`: Nghỉ giữa mỗi target (trong 1 cycle)
- `cycle_sleep_seconds`: Nghỉ giữa mỗi cycle hoàn chỉnh
- Bắt đầu bảo thủ, tối ưu dần dựa trên monitoring

