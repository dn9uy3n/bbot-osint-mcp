import json
from pathlib import Path
from typing import Any, Dict
from .config import settings
from loguru import logger


def load_init_config() -> Dict[str, Any]:
    p = Path(settings.init_config_path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def apply_init_config():
    cfg = load_init_config()
    # Telegram
    if not settings.telegram_bot_token and isinstance(cfg.get("TELEGRAM_BOT_TOKEN"), str):
        settings.telegram_bot_token = cfg.get("TELEGRAM_BOT_TOKEN")
    if not settings.telegram_chat_id and isinstance(cfg.get("TELEGRAM_CHAT_ID"), str):
        settings.telegram_chat_id = cfg.get("TELEGRAM_CHAT_ID")
    # Default targets
    targets = cfg.get("targets")
    if isinstance(targets, list):
        settings.default_targets = [str(t) for t in targets]
    
    # Scan defaults - store in settings for use in scan endpoint
    scan_defaults = cfg.get("scan_defaults")
    if isinstance(scan_defaults, dict):
        settings.scan_defaults = scan_defaults
    
    # BBOT modules config: API keys and per-module settings (e.g., enabled:false)
    bbot_modules = cfg.get("bbot_modules")
    bbot_disable = cfg.get("bbot_disable_modules")
    if isinstance(bbot_modules, dict):
        settings.bbot_modules = bbot_modules
    if isinstance(bbot_disable, list):
        settings.bbot_disable_modules = [str(m) for m in bbot_disable]

    if isinstance(bbot_modules, dict) or isinstance(bbot_disable, list):
        try:
            import yaml
            home = Path.home()
            bbot_path = home / ".config" / "bbot" / "bbot.yml"
            bbot_path.parent.mkdir(parents=True, exist_ok=True)
            current = {}
            if bbot_path.exists():
                current = yaml.safe_load(bbot_path.read_text(encoding="utf-8")) or {}
            if "modules" not in current:
                current["modules"] = {}
            # merge module configs
            if isinstance(bbot_modules, dict):
                for mod, cfgval in bbot_modules.items():
                    current["modules"][mod] = cfgval
            # disable listed modules
            if isinstance(bbot_disable, list):
                for mod in bbot_disable:
                    mod_name = str(mod)
                    if mod_name not in current["modules"]:
                        current["modules"][mod_name] = {}
                    current["modules"][mod_name]["enabled"] = False
            bbot_path.write_text(yaml.safe_dump(current, sort_keys=False, allow_unicode=True), encoding="utf-8")
            logger.info(f"Applied BBOT module config at {bbot_path}; disabled={settings.bbot_disable_modules}")
        except Exception as e:
            logger.warning(f"Failed to write BBOT config: {e}")


