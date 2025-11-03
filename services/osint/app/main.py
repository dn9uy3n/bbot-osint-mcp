import base64
import gzip

from fastapi import FastAPI, Depends, Request, Header, HTTPException
from fastapi.responses import ORJSONResponse
from loguru import logger

from .auth import require_token
from .models import QueryRequest, EventsQueryRequest, OutputIngestRequest
from .repository import (
    query_subdomains,
    ensure_constraints,
    query_events,
    ingest_output_json_bytes,
)
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
    role = (settings.deployment_role or "central").lower()
    if role == "central":
        # Ensure constraints, but don't crash if DB not ready yet
        try:
            ensure_constraints()
        except Exception as exc:
            logger.warning("Failed to ensure Neo4j constraints during startup: {}", exc)
    else:
        logger.info("deployment_role='{}' – skipping Neo4j constraint bootstrap", role)
    # Start continuous scanner in background
    import asyncio
    asyncio.create_task(scanner.run_forever())


@app.on_event("shutdown")
async def _on_shutdown():
    await scanner.stop()


def require_worker(
    worker_id: str | None = Header(default=None, alias="X-Worker-Id"),
    worker_token: str | None = Header(default=None, alias="X-Worker-Token"),
):
    tokens = settings.worker_tokens or {}
    if not worker_id or not worker_token or tokens.get(worker_id) != worker_token:
        raise HTTPException(status_code=401, detail="Unauthorized worker")
    return worker_id


@app.post("/ingest/output")
async def ingest_output(req: OutputIngestRequest, worker_id: str = Depends(require_worker)):
    data = base64.b64decode(req.payload_b64)
    if req.encoding == "gzip":
        data = gzip.decompress(data)
    imported = ingest_output_json_bytes(data, default_domain=req.default_domain)
    return {"imported": imported, "worker": worker_id}



