import asyncio
from typing import List
import time
from .config import settings
from .bbot_runner import async_start_scan, _event_to_dict
from .models import ScanRequest
from .repository import (
    cleanup_graph,
    ingest_dirs_by_scan_name,
    list_scan_dirs,
    ingest_scan_dir,
)
from .notifications import notify_telegram
from loguru import logger


class ContinuousScanner:
    def __init__(self):
        self.running = False
        self.current_scan_task = None
    
    async def run_forever(self):
        """Main loop - scan targets continuously"""
        self.running = True
        logger.info("Continuous scanner started")
        
        # Wait for init config to load
        await asyncio.sleep(5)
        
        targets = settings.default_targets
        if not targets:
            logger.warning("No targets configured in init_config.json, scanner idle")
            while self.running:
                await asyncio.sleep(60)
            return
        
        scan_defaults = settings.scan_defaults or {}
        cycle_sleep = scan_defaults.get("cycle_sleep_seconds", 3600)  # Default 1 hour between cycles
        target_sleep = scan_defaults.get("target_sleep_seconds", 300)  # Default 5 min between targets
        
        logger.info(f"Targets: {targets}")
        logger.info(f"Cycle sleep (between full cycles): {cycle_sleep}s")
        logger.info(f"Target sleep (between each target): {target_sleep}s")
        if settings.bbot_disable_modules:
            logger.info(f"Disabled modules (from init_config): {settings.bbot_disable_modules}")
        
        while self.running:
            cycle_start = time.time()
            logger.info(f"=== Starting scan cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
            
            total_events = 0
            
            for idx, target in enumerate(targets):
                if not self.running:
                    break
                
                logger.info(f"[{idx+1}/{len(targets)}] Scanning target: {target}")
                
                try:
                    # Build scan request
                    req = ScanRequest(
                        targets=[target],
                        presets=scan_defaults.get("presets", ["subdomain-enum"]),
                        flags=scan_defaults.get("flags", []),
                        max_workers=scan_defaults.get("max_workers", 2),
                        spider_depth=scan_defaults.get("spider_depth", 2),
                        spider_distance=scan_defaults.get("spider_distance", 1),
                        spider_links_per_page=scan_defaults.get("spider_links_per_page", 10),
                        allow_deadly=scan_defaults.get("allow_deadly", False),
                    )
                    logger.info(f"Resolved presets={req.presets} flags={req.flags} for target={target}")
                    
                    # Run scan: do NOT ingest live stream; only detect new scan dirs
                    event_count = 0
                    scan_name: str | None = None
                    scan_start_ts = time.time()
                    before_dirs = {str(p) for p in list_scan_dirs()}
                    async for event in async_start_scan(req):
                        ev = _event_to_dict(event)
                        # Optionally capture scan name from first SCAN event (for fallback matching)
                        if not scan_name and isinstance(ev, dict):
                            try:
                                if (ev.get("type") or "").upper() == "SCAN":
                                    data = ev.get("data") or {}
                                    for k in ("scan_name","name","label","id","slug"):
                                        v = data.get(k) or ev.get(k)
                                        if isinstance(v, str) and v:
                                            scan_name = v
                                            break
                            except Exception:
                                pass
                        # Do not ingest here; rely on output.json importer
                        event_count += 1
                    
                    total_events += event_count
                    logger.info(f"✓ Target {target} completed: {event_count} events")
                    # Post-scan: schedule import after short delay to ensure files are flushed
                    async def _import_after_delay(domain: str, detect_delay: int = 1, read_delay: int = 15, sname: str | None = None, before: set[str] | None = None):
                        try:
                            # Phase 1: detect new dirs shortly after completion
                            await asyncio.sleep(detect_delay)
                            prev = before or set()
                            after_dirs = {str(p) for p in list_scan_dirs()}
                            new_dirs = sorted(set(after_dirs) - set(prev))
                            # Phase 2: give time for files to flush before reading
                            await asyncio.sleep(read_delay)
                            used_dirs: list[str] = []
                            total_ingested = 0
                            if new_dirs:
                                for d in new_dirs:
                                    try:
                                        total_ingested += ingest_scan_dir(d, default_domain=domain)
                                        used_dirs.append(d)
                                    except FileNotFoundError as fnf:
                                        logger.error(f"output.json missing in {d}: {fnf}")
                                    except Exception as e:
                                        logger.error(f"Import failed for {d}: {e}")
                                logger.info(f"Imported {total_ingested} records for {domain} from new scan dirs: {used_dirs}")
                                return
                            # If no new dirs, fall back: if we captured scan name, try by name
                            if sname:
                                extra_by_name, used_by_name = ingest_dirs_by_scan_name(sname, default_domain=domain, max_dirs=1, max_age_seconds=7200)
                                if used_by_name:
                                    logger.info(f"Imported {extra_by_name} records for {domain} from scan '{sname}': {used_by_name}")
                                    return
                            logger.warning(f"No new scan dirs detected for {domain}; skipping import")
                        except Exception as _e:
                            logger.error(f"Scan dir import failed for {domain}: {_e}")
                    asyncio.create_task(_import_after_delay(target, 1, 15, scan_name, before_dirs))
                    
                except Exception as e:
                    logger.error(f"✗ Error scanning {target}: {e}")
                
                # Sleep between targets (except after last target)
                if idx < len(targets) - 1 and target_sleep > 0:
                    logger.info(f"Sleeping {target_sleep}s before next target...")
                    await asyncio.sleep(target_sleep)
            
            # Cleanup after full cycle
            if settings.cleanup_enabled:
                logger.info("Running cleanup...")
                stats = cleanup_graph(int(time.time()))
                logger.info(f"Cleanup stats: {stats}")
            else:
                stats = {}
            
            cycle_elapsed = int(time.time() - cycle_start)
            logger.info(f"=== Cycle completed in {cycle_elapsed}s, total events: {total_events} ===")
            
            # Telegram notification
            msg = (
                f"Scan cycle completed\n"
                f"Duration: {cycle_elapsed}s\n"
                f"Targets: {len(targets)}\n"
                f"Events: {total_events}\n"
                f"Cleanup: {stats.get('deleted_events',0)} events, {stats.get('deleted_offline_hosts',0)} hosts, {stats.get('deleted_orphans',0)} orphans"
            )
            try:
                await notify_telegram(msg)
            except Exception:
                pass
            
            # Sleep until next cycle
            if cycle_sleep > 0:
                logger.info(f"Sleeping {cycle_sleep}s until next cycle...")
                await asyncio.sleep(cycle_sleep)
    
    async def stop(self):
        """Stop the scanner gracefully"""
        logger.info("Stopping continuous scanner...")
        self.running = False
        if self.current_scan_task:
            self.current_scan_task.cancel()


# Global scanner instance
scanner = ContinuousScanner()

