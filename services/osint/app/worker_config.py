from __future__ import annotations

from loguru import logger

from .config import settings


def load_worker_tokens_from_config(workers: object) -> None:
    """Populate worker tokens from init_config.json section.

    Expected list format:
    "workers": [
        {"id": "worker-1", "token": "..."},
        ...
    ]
    """

    tokens: dict[str, str] = {}

    if isinstance(workers, list):
        for entry in workers:
            if not isinstance(entry, dict):
                continue
            wid = str(entry.get("id") or "").strip()
            tok = str(entry.get("token") or "").strip()
            if wid and tok:
                tokens[wid] = tok

    settings.worker_tokens = tokens

    if tokens:
        logger.info("Loaded {} worker tokens from init_config", len(tokens))
    else:
        logger.info("No worker tokens configured in init_config – worker ingest disabled")


