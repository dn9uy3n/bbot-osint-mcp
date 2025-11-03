from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

from .worker_uploader import upload_output_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload BBOT output.json to central OSINT API")
    parser.add_argument("--file", required=True, help="Path to output.json")
    parser.add_argument("--url", required=True, help="Central API endpoint, e.g. https://central/ingest/output")
    parser.add_argument("--worker-id", required=True, help="Worker identifier")
    parser.add_argument("--worker-token", required=True, help="Worker secret token")
    parser.add_argument("--domain", help="Default domain/target for this scan")
    parser.add_argument("--scan-name", help="Optional scan name", default=None)
    parser.add_argument("--no-gzip", action="store_true", help="Disable gzip compression")
    parser.add_argument("--timeout", type=int, default=120, help="Request timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    file_path = Path(args.file)
    if not file_path.exists() or not file_path.is_file():
        logger.error("File not found: {}", file_path)
        return 1

    try:
        imported = upload_output_json_file(
            file_path=file_path,
            default_domain=args.domain,
            scan_name=args.scan_name,
            url=args.url,
            worker_id=args.worker_id,
            worker_token=args.worker_token,
            compress=not args.no_gzip,
            verify_tls=True,
            timeout=args.timeout,
        )
        logger.info("Upload successful: imported={} scan={} domain={} url={}", imported, args.scan_name, args.domain, args.url)
    except Exception as exc:
        logger.error("Failed to upload output.json: {}", exc)
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())


