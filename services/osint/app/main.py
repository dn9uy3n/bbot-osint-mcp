from fastapi import FastAPI, Depends, Request
from fastapi.responses import ORJSONResponse
from .auth import require_token
from .models import QueryRequest, EventsQueryRequest
from .repository import query_subdomains, ensure_constraints, query_events
from .config import settings
from .config_loader import apply_init_config
from .scheduler import scanner
from mcp_server.server import get_app as get_mcp_app

app = FastAPI(title="BBOT OSINT Monitoring API", default_response_class=ORJSONResponse)


# Simple token-protected health
@app.get("/healthz", dependencies=[Depends(require_token)])
def healthz():
    return {
        "status": "ok",
        "scanner_running": scanner.running,
        "targets": settings.default_targets,
    }


@app.get("/status", dependencies=[Depends(require_token)])
def status():
    """Get scanner status and configuration"""
    return {
        "scanner_running": scanner.running,
        "targets": settings.default_targets,
        "scan_config": settings.scan_defaults,
        "cleanup_enabled": settings.cleanup_enabled,
    }


@app.post("/query", dependencies=[Depends(require_token)])
def query(req: QueryRequest):
    """Query hosts from Neo4j"""
    rows = list(query_subdomains(req.domain, req.host, req.online_only, req.limit))
    return {"results": rows, "count": len(rows)}


@app.post("/events/query", dependencies=[Depends(require_token)])
def events_query(req: EventsQueryRequest):
    """Query events from Neo4j"""
    rows = list(query_events(req.types, req.modules, req.domain, req.host, req.since_ts, req.until_ts, req.limit))
    return {"results": rows, "count": len(rows)}


# Mount MCP shim app (query-only)
mcp_app = get_mcp_app()
app.mount("/mcp", mcp_app)


@app.on_event("startup")
async def _on_startup():
    apply_init_config()
    # Ensure constraints, but don't crash if DB not ready yet
    try:
        ensure_constraints()
    except Exception:
        pass
    # Start continuous scanner in background
    import asyncio
    asyncio.create_task(scanner.run_forever())


@app.on_event("shutdown")
async def _on_shutdown():
    await scanner.stop()



