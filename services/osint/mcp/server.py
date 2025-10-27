import asyncio
from typing import Any
from mcp.server.fastapi import MCPFAPIApp
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from ..app.auth import require_token
from ..app.models import QueryRequest, ScanRequest, EventsQueryRequest
from ..app.repository import query_subdomains, query_events
from ..app.bbot_runner import async_start_scan
from ..app.config import settings


mcp_app = MCPFAPIApp()


# Enforce token via middleware
@mcp_app.app.middleware("http")
async def token_middleware(request: Request, call_next):
    expected = settings.api_token
    provided = request.headers.get("X-API-Token")
    if expected and provided != expected:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


@mcp_app.tool("osint.query")
async def mcp_query(domain: str | None = None, host: str | None = None, online_only: bool = False, limit: int = 50) -> dict[str, Any]:
    req = QueryRequest(domain=domain, host=host, online_only=online_only, limit=limit)
    rows = list(query_subdomains(req.domain, req.host, req.online_only, req.limit))
    return {"results": rows}


@mcp_app.tool("osint.scan")
async def mcp_scan(targets: list[str], presets: list[str] | None = None, allow_deadly: bool = False) -> dict[str, Any]:
    req = ScanRequest(targets=targets, presets=presets or ["subdomain-enum"], allow_deadly=allow_deadly)
    count = 0
    async for _ in async_start_scan(req):
        count += 1
    return {"events": count}


@mcp_app.tool("osint.events.query")
async def mcp_events_query(types: list[str] | None = None, modules: list[str] | None = None, domain: str | None = None, host: str | None = None, since_ts: int | None = None, until_ts: int | None = None, limit: int = 200) -> dict[str, Any]:
    req = EventsQueryRequest(types=types or [], modules=modules or [], domain=domain, host=host, since_ts=since_ts, until_ts=until_ts, limit=limit)
    rows = list(query_events(req.types, req.modules, req.domain, req.host, req.since_ts, req.until_ts, req.limit))
    return {"results": rows}


def get_app():
    # Wrap with FastAPI dependency for token at root mount site
    # When mounted in FastAPI, add Depends(require_token) to route
    return mcp_app.app


