from pydantic import BaseModel, Field
from typing import Literal, Optional


class ScanRequest(BaseModel):
    targets: list[str] = Field(default_factory=list)
    presets: list[str] = Field(default_factory=lambda: ["subdomain-enum"])  # see bbot presets
    flags: list[str] = Field(default_factory=list)
    max_workers: int = 2
    spider_depth: int = 2
    spider_distance: int = 1
    spider_links_per_page: int = 10
    allow_deadly: bool = False
    # sleep between scans (seconds); if >0 will sleep before returning result
    sleep_after_scan_seconds: int = 0


class SubdomainRecord(BaseModel):
    domain: str
    host: str
    status: Literal["online", "offline", "unknown"] = "unknown"
    last_seen_ts: int  # epoch seconds
    sources: list[str] = Field(default_factory=list)
    ports: list[int] = Field(default_factory=list)


class QueryRequest(BaseModel):
    domain: Optional[str] = None
    host: Optional[str] = None
    online_only: bool = False
    limit: int = 100


class EventsQueryRequest(BaseModel):
    types: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)
    domain: Optional[str] = None
    host: Optional[str] = None
    since_ts: Optional[int] = None
    until_ts: Optional[int] = None
    limit: int = 200


class OutputIngestRequest(BaseModel):
    scan_name: Optional[str] = None
    default_domain: Optional[str] = None
    encoding: Literal["plain", "gzip"] = "plain"
    payload_b64: str


