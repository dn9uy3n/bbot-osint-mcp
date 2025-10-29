import asyncio
from typing import List
import time
from .config import settings
from .bbot_runner import async_start_scan, _event_to_dict
from .models import ScanRequest
from .repository import ingest_event, cleanup_graph, ingest_latest_scan_dirs
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
                    
                    # Run scan
                    event_count = 0
                    async for event in async_start_scan(req):
                        ingest_event(_event_to_dict(event), default_domain=target)
                        event_count += 1
                    
                    total_events += event_count
                    logger.info(f"✓ Target {target} completed: {event_count} events")
                    # Post-scan: schedule import after short delay to ensure files are flushed
                    async def _import_after_delay(domain: str, delay: int = 12):
                        try:
                            await asyncio.sleep(delay)
                            extra = ingest_latest_scan_dirs(default_domain=domain, max_dirs=1, max_age_seconds=1800)
                            logger.info(f"Imported {extra} additional records from scan directory for {domain}")
                        except Exception as _e:
                            logger.debug(f"Scan dir import skipped/failed for {domain}: {_e}")
                    asyncio.create_task(_import_after_delay(target, 12))
                    
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

