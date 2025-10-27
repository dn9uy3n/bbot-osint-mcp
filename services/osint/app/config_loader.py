import json
from pathlib import Path
from typing import Any, Dict
from .config import settings


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
    # BBOT API keys: write into mounted bbot.yml if provided via init config
    bbot_modules = cfg.get("bbot_modules")
    if isinstance(bbot_modules, dict):
        # Merge into existing file path (mounted path). We avoid write if no mount.
        try:
            from pathlib import Path
            import yaml
            bbot_path = Path("/root/.config/bbot/bbot.yml")
            bbot_path.parent.mkdir(parents=True, exist_ok=True)
            current = {}
            if bbot_path.exists():
                current = yaml.safe_load(bbot_path.read_text(encoding="utf-8")) or {}
            if "modules" not in current:
                current["modules"] = {}
            # merge keys
            for mod, cfgval in bbot_modules.items():
                current["modules"][mod] = cfgval
            bbot_path.write_text(yaml.safe_dump(current, sort_keys=False, allow_unicode=True), encoding="utf-8")
        except Exception:
            pass


