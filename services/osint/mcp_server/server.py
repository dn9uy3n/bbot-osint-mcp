import json
from typing import Any, Callable, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from app.models import EventsQueryRequest, QueryRequest
from app.repository import query_events, query_subdomains
from app.config import settings


"""
Temporary shim FastAPI app under /mcp to provide query-only MCP-like tools.
This avoids importing the external mcp SDK until compatibility is resolved.
"""
mcp_app = FastAPI(title="BBOT OSINT MCP Shim", version="0.2.0")


# Enforce token via middleware
@mcp_app.middleware("http")
async def token_middleware(request: Request, call_next):
    expected = settings.api_token
    provided = request.headers.get("X-API-Token")
    if expected and provided != expected:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


class MCPInvokeRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


def _schema_for(model: type[BaseModel]) -> Dict[str, Any]:
    schema = model.model_json_schema()
    # FastAPI already uses JSON-serializable dict; ensure defaults set where missing
    return schema


def _run_osint_query(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        req = QueryRequest(**payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc
    rows = list(
        query_subdomains(req.domain, req.host, req.online_only, req.limit)
    )
    return {"results": rows}


def _run_osint_events_query(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        req = EventsQueryRequest(**payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc
    rows = list(
        query_events(
            req.types,
            req.modules,
            req.domain,
            req.host,
            req.since_ts,
            req.until_ts,
            req.limit,
        )
    )
    return {"results": rows}


def _run_osint_status(_payload: Dict[str, Any]) -> Dict[str, Any]:
    from app.scheduler import scanner

    return {
        "scanner_running": scanner.running,
        "targets": settings.default_targets,
        "scan_config": settings.scan_defaults,
        "cleanup_enabled": settings.cleanup_enabled,
    }


TOOL_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "osint.query": {
        "name": "osint.query",
        "label": "Query Hosts",
        "description": "Return hosts discovered for a domain/host filter from Neo4j.",
        "input_schema": _schema_for(QueryRequest),
    },
    "osint.events.query": {
        "name": "osint.events.query",
        "label": "Query Events",
        "description": "Return raw event records filtered by type, module, or scope.",
        "input_schema": _schema_for(EventsQueryRequest),
    },
    "osint.status": {
        "name": "osint.status",
        "label": "Scanner Status",
        "description": "Provide scheduler runtime state and active targets.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


TOOL_EXECUTORS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "osint.query": _run_osint_query,
    "osint.events.query": _run_osint_events_query,
    "osint.status": _run_osint_status,
}


@mcp_app.get("/")
async def mcp_root() -> dict[str, Any]:
    """Root endpoint so HTTP-based MCP clients can perform a quick handshake."""
    return {
        "name": "bbot-osint-mcp",
        "description": "HTTP MCP shim exposing read-only BBOT OSINT queries",
        "protocol": "mcp-http",
        "version": mcp_app.version,
        "endpoints": {
            "tools": "/mcp/tools",
            "invoke": "/mcp/invoke",
            "health": "/mcp/healthz",
        },
        "capabilities": {
            "tools": ["list", "invoke"],
            "streaming": False,
        },
        "requires_token": bool(settings.api_token),
    }


@mcp_app.get("/healthz")
async def mcp_health() -> dict[str, str]:
    return {"status": "ok"}


@mcp_app.get("/tools/osint.query")
async def mcp_query(
    domain: str | None = None,
    host: str | None = None,
    online_only: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    """Query hosts from Neo4j database (GET compatibility)."""
    payload = {
        "domain": domain,
        "host": host,
        "online_only": online_only,
        "limit": limit,
    }
    return _run_osint_query(payload)


@mcp_app.post("/tools/osint.query")
async def mcp_query_post(body: Dict[str, Any]) -> dict[str, Any]:
    return _run_osint_query(body)


@mcp_app.get("/tools")
async def mcp_tools_index() -> dict[str, Any]:
    """List available MCP tools with JSON Schema metadata."""
    tools = [
        {
            "name": meta["name"],
            "label": meta.get("label", meta["name"]),
            "description": meta.get("description", ""),
            "input_schema": meta.get("input_schema", {}),
            "invoke": f"/mcp/tools/{meta['name']}",
        }
        for meta in TOOL_DEFINITIONS.values()
    ]
    return {"tools": tools}


@mcp_app.get("/tools/{tool_name}")
async def mcp_tool_detail(tool_name: str) -> dict[str, Any]:
    meta = TOOL_DEFINITIONS.get(tool_name)
    if not meta:
        raise HTTPException(status_code=404, detail="Unknown tool")
    return {
        "name": meta["name"],
        "label": meta.get("label", meta["name"]),
        "description": meta.get("description", ""),
        "input_schema": meta.get("input_schema", {}),
        "invoke": f"/mcp/tools/{meta['name']}",
    }


@mcp_app.get("/tools/osint.events.query")
async def mcp_events_query(
    types: list[str] | None = None,
    modules: list[str] | None = None,
    domain: str | None = None,
    host: str | None = None,
    since_ts: int | None = None,
    until_ts: int | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Query events from Neo4j database (GET compatibility)."""
    payload = {
        "types": types or [],
        "modules": modules or [],
        "domain": domain,
        "host": host,
        "since_ts": since_ts,
        "until_ts": until_ts,
        "limit": limit,
    }
    return _run_osint_events_query(payload)


@mcp_app.post("/tools/osint.events.query")
async def mcp_events_query_post(body: Dict[str, Any]) -> dict[str, Any]:
    return _run_osint_events_query(body)


@mcp_app.get("/tools/osint.status")
async def mcp_status() -> dict[str, Any]:
    """Get scanner status and configuration (GET compatibility)."""
    return _run_osint_status({})


@mcp_app.post("/tools/osint.status")
async def mcp_status_post(body: Dict[str, Any] | None = None) -> dict[str, Any]:
    if body not in (None, {}):
        raise HTTPException(status_code=422, detail="osint.status does not accept arguments")
    return _run_osint_status({})


@mcp_app.post("/invoke")
async def mcp_invoke(req: MCPInvokeRequest) -> dict[str, Any]:
    handler = TOOL_EXECUTORS.get(req.tool)
    if not handler:
        raise HTTPException(status_code=404, detail="Unknown tool")
    return {"tool": req.tool, "output": handler(req.arguments)}


def get_app():
    return mcp_app
