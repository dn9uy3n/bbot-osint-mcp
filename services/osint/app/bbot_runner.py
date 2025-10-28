from typing import AsyncIterator, Iterator, Any, Dict
from bbot.scanner import Scanner
from .models import ScanRequest
from .config import settings
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
    # Apply module-level config and disable list at runtime as a safety net
    # BBOT supports YAML config; here we also pass through known module settings when possible
    # and ensure disabled modules are not executed by forcing them disabled in config
    disabled = set(settings.bbot_disable_modules or [])
    if settings.bbot_modules:
        config_modules = config.setdefault("modules", {})
        for mod, mod_cfg in settings.bbot_modules.items():
            try:
                config_modules[mod] = mod_cfg
            except Exception:
                pass
    if disabled:
        config_modules = config.setdefault("modules", {})
        for mod in disabled:
            mod_cfg = config_modules.get(mod, {})
            # Do not re-enable if user explicitly enabled; we respect explicit disable
            mod_cfg["enabled"] = False
            config_modules[mod] = mod_cfg
        logger.info(f"Runtime-disabled modules: {sorted(disabled)}")
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


def _event_to_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    for attr in ("asdict", "to_dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                d = fn()
                if isinstance(d, dict):
                    return d
            except Exception:
                pass
    # Fallback: use __dict__ if present
    d2 = getattr(obj, "__dict__", None)
    if isinstance(d2, dict):
        return d2
    # Last resort: string representation
    return {"raw": str(obj)}


def start_scan(req: ScanRequest) -> Iterator[dict]:
    scan = build_scanner(req)
    for event in scan.start():
        yield _event_to_dict(event)


async def async_start_scan(req: ScanRequest) -> AsyncIterator[dict]:
    scan = build_scanner(req)
    async for event in scan.async_start():
        yield _event_to_dict(event)


