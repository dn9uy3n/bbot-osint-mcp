from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import ORJSONResponse
from typing import AsyncIterator
from .auth import require_token
from .models import ScanRequest, QueryRequest, SubdomainRecord, EventsQueryRequest
from .bbot_runner import async_start_scan
from .repository import upsert_subdomain, query_subdomains, ensure_constraints, ingest_event, query_events, cleanup_graph
from ..mcp.server import get_app as get_mcp_app
from .config import settings
import asyncio
from .notifications import notify_telegram
from .config_loader import apply_init_config

app = FastAPI(title="BBOT OSINT API", default_response_class=ORJSONResponse)


# Simple token-protected health
@app.get("/healthz", dependencies=[Depends(require_token)])
def healthz():
    return {"status": "ok"}


_scan_semaphore = asyncio.Semaphore(settings.max_concurrent_scans)


async def _rate_limit(request: Request):
    # Very simple IP-based limiter in-memory (sufficient for single instance)
    # For production, consider Redis-based limiter.
    ip = request.client.host if request.client else "unknown"
    key = ("rl", ip)
    store = getattr(app.state, "rate_store", None)
    if store is None:
        store = {}
        app.state.rate_store = store
    from time import time
    now = int(time())
    window = now // 60
    count, current_window = store.get(key, (0, window))
    if current_window != window:
        count = 0
        current_window = window
    count += 1
    store[key] = (count, current_window)
    if count > settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


@app.post("/scan", dependencies=[Depends(require_token)])
async def scan(req: ScanRequest, request: Request):
    await _rate_limit(request)
    
    # Apply scan_defaults from init_config.json if values not provided
    if settings.scan_defaults:
        if not req.targets and settings.default_targets:
            req.targets = settings.default_targets
        if req.max_workers == 2 and settings.scan_defaults.get("max_workers"):
            req.max_workers = settings.scan_defaults.get("max_workers")
        if req.spider_depth == 2 and settings.scan_defaults.get("spider_depth"):
            req.spider_depth = settings.scan_defaults.get("spider_depth")
        if req.spider_distance == 1 and settings.scan_defaults.get("spider_distance"):
            req.spider_distance = settings.scan_defaults.get("spider_distance")
        if req.spider_links_per_page == 10 and settings.scan_defaults.get("spider_links_per_page"):
            req.spider_links_per_page = settings.scan_defaults.get("spider_links_per_page")
        if req.sleep_after_scan_seconds == 0 and settings.scan_defaults.get("sleep_after_scan_seconds"):
            req.sleep_after_scan_seconds = settings.scan_defaults.get("sleep_after_scan_seconds")
    
    if req.max_workers > settings.max_concurrent_scans:
        req.max_workers = settings.max_concurrent_scans
    await _scan_semaphore.acquire()
    async def stream() -> AsyncIterator[dict]:
        async for event in async_start_scan(req):
            # Ingest all events into Neo4j for full fidelity
            ingest_event(event, default_domain=(req.targets[0] if req.targets else None))
            yield event

    # Note: For simplicity returning as a collected list. For true streaming use StreamingResponse.
    events = []
    async for e in stream():
        events.append(e)
    # Cleanup after scan
    from time import time
    stats = cleanup_graph(int(time()))
    # Telegram notify
    total = len(events)
    msg = (
        f"Scan completed\\n"
        f"Targets: {', '.join(req.targets) if req.targets else '-'}\\n"
        f"Events: {total}\\n"
        f"Cleanup: events={stats.get('deleted_events',0)}, offline_hosts={stats.get('deleted_offline_hosts',0)}, orphans={stats.get('deleted_orphans',0)}"
    )
    try:
        await notify_telegram(msg)
    except Exception:
        pass
    _scan_semaphore.release()
    # Sleep to avoid blocking
    if getattr(req, "sleep_after_scan_seconds", 0) and req.sleep_after_scan_seconds > 0:
        await asyncio.sleep(min(req.sleep_after_scan_seconds, 3600))
    return {"count": len(events), "cleanup": stats}


@app.post("/query", dependencies=[Depends(require_token)])
def query(req: QueryRequest, request: Request):
    # best-effort rate limit (sync route)
    # Using same helper via background could be done; keep minimal overhead.
    rows = list(query_subdomains(req.domain, req.host, req.online_only, req.limit))
    return {"results": rows, "count": len(rows)}


# Mount MCP server under /mcp with token requirement
mcp_app = get_mcp_app()
app.mount("/mcp", mcp_app)


@app.post("/upsert", dependencies=[Depends(require_token)])
def upsert(record: SubdomainRecord, request: Request):
    upsert_subdomain(record)
    return {"ok": True}


@app.post("/events/query", dependencies=[Depends(require_token)])
def events_query(req: EventsQueryRequest, request: Request):
    rows = list(query_events(req.types, req.modules, req.domain, req.host, req.since_ts, req.until_ts, req.limit))
    return {"results": rows, "count": len(rows)}


@app.on_event("startup")
async def _on_startup():
    apply_init_config()
    ensure_constraints()



