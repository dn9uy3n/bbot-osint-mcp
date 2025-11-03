from __future__ import annotations

import base64
import gzip
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from .config import settings


def _resolve(value: Any, fallback: Any) -> Any:
    return value if value is not None else fallback


def _build_endpoint(url: str | None) -> str:
    resolved = _resolve(url, settings.central_api_url)
    if not resolved:
        raise ValueError("central_api_url is not configured")
    resolved = resolved.strip().rstrip("/")
    if resolved.endswith("/ingest/output"):
        return resolved
    return f"{resolved}/ingest/output"


def _post_payload(
    endpoint: str,
    payload: dict[str, Any],
    *,
    worker_id: str | None,
    worker_token: str | None,
    verify_tls: bool,
    timeout: int,
) -> httpx.Response:
    if not worker_id or not worker_token:
        raise ValueError("Worker credentials are not configured")

    headers = {
        "X-Worker-Id": worker_id,
        "X-Worker-Token": worker_token,
        "Content-Type": "application/json",
    }

    with httpx.Client(verify=verify_tls, timeout=timeout) as client:
        resp = client.post(endpoint, headers=headers, json=payload)
        resp.raise_for_status()
        return resp


def upload_output_json_bytes(
    data: bytes,
    default_domain: str | None = None,
    scan_name: str | None = None,
    *,
    url: str | None = None,
    worker_id: str | None = None,
    worker_token: str | None = None,
    compress: bool | None = None,
    verify_tls: bool | None = None,
    timeout: int | None = None,
) -> int:
    """Upload BBOT output.json bytes to the central aggregator."""

    if not data:
        raise ValueError("Payload is empty")

    use_compress = _resolve(compress, settings.central_upload_compress)
    payload_bytes = gzip.compress(data) if use_compress else data
    encoding = "gzip" if use_compress else "plain"

    payload = {
        "scan_name": scan_name,
        "default_domain": default_domain,
        "encoding": encoding,
        "payload_b64": base64.b64encode(payload_bytes).decode("ascii"),
    }

    endpoint = _build_endpoint(url)
    resp = _post_payload(
        endpoint,
        payload,
        worker_id=_resolve(worker_id, settings.central_worker_id),
        worker_token=_resolve(worker_token, settings.central_worker_token),
        verify_tls=_resolve(verify_tls, settings.central_api_verify_tls),
        timeout=_resolve(timeout, settings.central_api_timeout),
    )

    try:
        body = resp.json()
        return int(body.get("imported", 0))
    except Exception:
        logger.warning("Upload response not JSON or missing 'imported': {}", resp.text)
        return 0


def upload_output_json_file(
    file_path: str | Path,
    default_domain: str | None = None,
    scan_name: str | None = None,
    **kwargs,
) -> int:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"output.json not found: {path}")
    data = path.read_bytes()
    return upload_output_json_bytes(data, default_domain, scan_name, **kwargs)


def upload_scan_dir(
    scan_dir: str | Path,
    default_domain: str | None = None,
    scan_name: str | None = None,
    **kwargs,
) -> int:
    path = Path(scan_dir)
    output_file = path / "output.json"
    if not output_file.exists():
        raise FileNotFoundError(f"output.json not found in scan dir: {path}")
    effective_scan = scan_name or path.name
    return upload_output_json_file(output_file, default_domain, effective_scan, **kwargs)

