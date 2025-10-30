from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.models import QueryRequest, EventsQueryRequest
from app.repository import query_subdomains, query_events
from app.config import settings
from typing import Any


"""
Temporary shim FastAPI app under /mcp to provide query-only MCP-like tools.
This avoids importing the external mcp SDK until compatibility is resolved.
"""
mcp_app = FastAPI()


# Enforce token via middleware
@mcp_app.middleware("http")
async def token_middleware(request: Request, call_next):
    expected = settings.api_token
    provided = request.headers.get("X-API-Token")
    if expected and provided != expected:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


@mcp_app.get("/")
async def mcp_root() -> dict[str, Any]:
    """Root endpoint so HTTP-based MCP clients can perform a quick handshake."""
    return {
        "name": "bbot-osint-mcp",
        "description": "HTTP MCP shim exposing read-only BBOT OSINT queries",
        "tools_endpoint": "/mcp/tools",
        "requires_token": bool(settings.api_token),
    }


@mcp_app.get("/tools/osint.query")
async def mcp_query(domain: str | None = None, host: str | None = None, online_only: bool = False, limit: int = 50) -> dict[str, Any]:
    """Query hosts from Neo4j database"""
    req = QueryRequest(domain=domain, host=host, online_only=online_only, limit=limit)
    rows = list(query_subdomains(req.domain, req.host, req.online_only, req.limit))
    return {"results": rows}


@mcp_app.get("/tools")
async def mcp_tools_index() -> dict[str, Any]:
    """List available MCP-like tools (query-only)."""
    return {
        "tools": [
            {"name": "osint.status", "method": "GET", "path": "/mcp/tools/osint.status"},
            {"name": "osint.query", "method": "GET", "path": "/mcp/tools/osint.query?domain=<domain>&online_only=true&limit=50"},
            {"name": "osint.events.query", "method": "GET", "path": "/mcp/tools/osint.events.query?types=DNS_NAME&domain=<domain>&limit=100"},
        ]
    }


@mcp_app.get("/tools/osint.events.query")
async def mcp_events_query(
    types: list[str] | None = None, 
    modules: list[str] | None = None, 
    domain: str | None = None, 
    host: str | None = None, 
    since_ts: int | None = None, 
    until_ts: int | None = None, 
    limit: int = 200
) -> dict[str, Any]:
    """Query events from Neo4j database"""
    req = EventsQueryRequest(
        types=types or [], 
        modules=modules or [], 
        domain=domain, 
        host=host, 
        since_ts=since_ts, 
        until_ts=until_ts, 
        limit=limit
    )
    rows = list(query_events(req.types, req.modules, req.domain, req.host, req.since_ts, req.until_ts, req.limit))
    return {"results": rows}


@mcp_app.get("/tools/osint.status")
async def mcp_status() -> dict[str, Any]:
    """Get scanner status and configuration"""
    from app.scheduler import scanner
    return {
        "scanner_running": scanner.running,
        "targets": settings.default_targets,
        "scan_config": settings.scan_defaults,
        "cleanup_enabled": settings.cleanup_enabled,
    }


def get_app():
    return mcp_app
