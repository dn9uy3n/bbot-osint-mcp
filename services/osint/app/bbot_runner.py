from typing import AsyncIterator, Iterator
from bbot.scanner import Scanner
from .models import ScanRequest
from loguru import logger

ALLOWED_PRESETS = {
    # Common presets known to be available in BBOT
    "subdomain-enum",
    "spider",
    "email-enum",
    "web-basic",
    "cloud-enum",
}

ALLOWED_FLAGS = {
    # Subset of BBOT runtime flags we allow to pass through
    "safe",
    "active",
}


def build_scanner(req: ScanRequest) -> Scanner:
    config = {
        "engine": {"max_workers": req.max_workers},
        "web": {
            "spider_depth": req.spider_depth,
            "spider_distance": req.spider_distance,
            "spider_links_per_page": req.spider_links_per_page,
        },
    }
    # Sanitize presets: drop unknown, default to subdomain-enum if empty
    presets = [p for p in (req.presets or []) if p in ALLOWED_PRESETS]
    if not presets:
        if req.presets:
            logger.warning(
                f"Invalid presets {req.presets}; defaulting to ['subdomain-enum']"
            )
        presets = ["subdomain-enum"]

    # Sanitize flags: drop unknown ones (e.g., presets mistakenly set as flags)
    flags = [f for f in (req.flags or []) if f in ALLOWED_FLAGS]
    # Enforce safe mode to avoid root installs
    if "safe" not in flags:
        flags.append("safe")
    if req.allow_deadly:
        flags.append("allow-deadly")
    # Blacklist some heavy/ansible modules by passing flags if available
    # Note: BBOT CLI supports --skip-modules; as Python API, we filter presets instead by not enabling those presets
    return Scanner(*req.targets, presets=presets, flags=flags, config=config)


def start_scan(req: ScanRequest) -> Iterator[dict]:
    scan = build_scanner(req)
    for event in scan.start():
        yield event.asdict()


async def async_start_scan(req: ScanRequest) -> AsyncIterator[dict]:
    scan = build_scanner(req)
    async for event in scan.async_start():
        yield event.asdict()


