from typing import AsyncIterator, Iterator
from bbot.scanner import Scanner
from .models import ScanRequest


def build_scanner(req: ScanRequest) -> Scanner:
    config = {
        "engine": {"max_workers": req.max_workers},
        "web": {
            "spider_depth": req.spider_depth,
            "spider_distance": req.spider_distance,
            "spider_links_per_page": req.spider_links_per_page,
        },
    }
    flags = req.flags.copy()
    if req.allow_deadly:
        flags.append("allow-deadly")
    return Scanner(*req.targets, presets=req.presets, flags=flags, config=config)


def start_scan(req: ScanRequest) -> Iterator[dict]:
    scan = build_scanner(req)
    for event in scan.start():
        yield event.asdict()


async def async_start_scan(req: ScanRequest) -> AsyncIterator[dict]:
    scan = build_scanner(req)
    async for event in scan.async_start():
        yield event.asdict()


