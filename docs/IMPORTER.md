## Importer (output.json → Neo4j)

Mục tiêu: Bảo toàn đầy đủ thông tin từ BBOT `output.json` theo từng dòng JSON (JSON lines) và xây dựng đồ thị quan hệ chính xác quanh Domain hiện tại.

Nguyên tắc xử lý
- Mỗi dòng JSON tạo một `(EVENT)` trước, gắn `type`, `raw`, `tags`.
- Xác định Domain hiện tại từ dòng `SCAN` trong cùng tệp (lấy `data.target.seeds`). Các entity khác sinh sau đó sẽ được liên kết với Domain này.
- Tạo node chính theo `type` và `data`; MERGE để không trùng lặp; gắn `tags` (hợp nhất).
- Các thực thể liên kết (HOST, IP_ADDRESS, URL, OPEN_TCP_PORT, …) nếu chưa có sẽ được MERGE và liên kết.

Mapping cốt lõi
- SCAN: `(sc:SCAN {name: data.name})` + `(sc)-[:TARGETS]->(d:Domain {name: seed})`
- DNS_NAME: `(dn:DNS_NAME {name: dns_children.NS[0] | fallback data/host})`, `(dn)-[:ON_HOST]->(h:Host {name: host})`, `(h)-[:RESOLVES_TO]->(i:IP_ADDRESS {addr})` từ `resolved_hosts`
- OPEN_TCP_PORT: `(op:OPEN_TCP_PORT {endpoint: host:port, port})`, `(op)-[:ON_HOST]->(h:Host {name: host})`, `(op)-[:RESOLVES_TO]->(i:IP_ADDRESS {addr})`
- TECHNOLOGY: `(t:TECHNOLOGY {name: data.technology})`, `(h:Host {name: host})-[:USES_TECH]->(t)`, `(h)-[:RESOLVES_TO]->(i:IP_ADDRESS)` khi có
- EMAIL_ADDRESS: `(e:EMAIL_ADDRESS {value: data|string})`, `(e)-[:ON_HOST]->(h:Host {name: host})`
- MOBILE_APP: `(ma:MOBILE_APP {name: data.id|name})`, `(ma)-[:OF_DOMAIN]->(d)`; (tuỳ chọn) `(ma)-[:DOWNLOAD_URL]->(u:URL {value: data.url})`
- URL: `(u:URL {value: data|string})`, `(u)-[:ON_HOST]->(h:Host {name: host})`, `(u)-[:RESOLVES_TO]->(i:IP_ADDRESS)` từ `resolved_hosts`
- URL_UNVERIFIED: `(uu:URL_UNVERIFIED {value: data|string})`, `(uu)-[:ON_HOST]->(h)`
- ASN: `(a:ASN {number: data|string (strip 'AS')})`, `(a)-[:OF_DOMAIN]->(d)`
- FINDING: `(f:FINDING {id: data.description|title|name})`, `(f)-[:RELATED_URL]->(u)` nếu có, `(f)-[:ON_HOST]->(h:Host {name: host})`, `(h)-[:RESOLVES_TO]->(i:IP_ADDRESS)`
- STORAGE_BUCKET: `(sb:STORAGE_BUCKET {name: data.name})`, `(sb)-[:EXPOSED_AT]->(u)` nếu có, `(sb)-[:ON_HOST]->(h:Host {name: host})`
- PROTOCOL: `(pr:PROTOCOL {name: data.protocol})`, `(pr)-[:ON_HOST]->(h:Host {name: host})`, `(pr)-[:ON_PORT]->(op:OPEN_TCP_PORT {endpoint: host:port})`, `(h)-[:RESOLVES_TO]->(i:IP_ADDRESS)`
- SOCIAL: `(s:SOCIAL {handle: data.platform|name})`, `(s)-[:OF_DOMAIN]->(d)`; (tuỳ chọn) `(s)-[:ON_HOST]->(h)`
- CODE_REPOSITORY: `(cr:CODE_REPOSITORY {url: data.url})`, `(cr)-[:OF_DOMAIN]->(d)`; (tuỳ chọn) `(cr)-[:ON_HOST]->(h)`
- IP_ADDRESS: `(i:IP_ADDRESS {addr: data|string})`, `(i)-[:OF_DOMAIN]->(d)`

Chiến lược thư mục scan
- Sau khi target hoàn tất: đợi 1s để phát hiện thư mục scan mới; đợi thêm 15s để file flush xong, rồi nhập từ `output.json` của thư mục mới.
- Nếu không có thư mục mới: fallback theo tên scan (nếu có) hoặc lấy thư mục gần nhất có `output.json`.

Ghi chú
- Dùng MERGE cho tất cả node/quan hệ; tags được hợp nhất: `tags = apoc.coll.toSet(coalesce(tags, []) + $tags)`.
- Constraints đã thêm cho nhiều label để đảm bảo MERGE nhanh và không trùng.

## Ingest từ Worker Từ Xa

- API trung tâm cung cấp endpoint `POST /ingest/output`.
- Bảo vệ bằng header `X-Worker-Id` và `X-Worker-Token` (khai báo trong `init_config.json` mục `workers`).
- Payload JSON:

```json
{
  "scan_name": "diabolic_carlos",
  "default_domain": "masterisehomes.com",
  "encoding": "gzip",
  "payload_b64": "<base64 của output.json (gzip)>"
}
```

- Mỗi worker nên dùng script `python -m app.worker_ingest`:

```bash
python -m app.worker_ingest \
  --file /root/.bbot/scans/<scan>/output.json \
  --url https://central.example.com/ingest/output \
  --worker-id worker-1 \
  --worker-token <token> \
  --domain masterisehomes.com \
  --scan-name <scan>
```

- Server sẽ trả về `{ "imported": <records>, "worker": "worker-1" }`. Dữ liệu được xử lý như ingest nội bộ, đảm bảo tránh trùng lặp.
- Khi `deployment_role = "worker"` và `central_api.auto_upload=true`, worker sẽ tự động đọc file `output.json` mới sinh sau mỗi lần quét và gọi endpoint này.
- Nếu chạy ở chế độ trung tâm thuần (`deployment_role = "central"` hoặc không khai báo), importer xử lý trực tiếp `output.json` trên chính máy chủ và không cần cấu hình `central_api`.

