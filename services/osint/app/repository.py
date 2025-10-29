from typing import Iterable, Any
import json
import os
from pathlib import Path
import csv
from .neo4j_client import neo4j_client
from .models import SubdomainRecord
from .config import settings


def upsert_subdomain(record: SubdomainRecord) -> None:
    query = (
        "MERGE (d:Domain {name: $domain}) "
        "MERGE (h:Host {fqdn: $host})-[:PART_OF]->(d) "
        "SET h.status = $status, "
        "    h.last_seen_ts = $last_seen_ts, "
        "    h.sources = $sources, "
        "    h.ports = $ports"
    )
    # Ensure the write executes by consuming the generator
    list(neo4j_client.run(query, record.model_dump()))


def query_subdomains(domain: str | None = None, host: str | None = None, online_only: bool = False, limit: int = 100) -> Iterable[dict]:
    where = []
    params: dict[str, object] = {"limit": limit}
    if domain:
        where.append("d.name CONTAINS $domain")
        params["domain"] = domain
    if host:
        where.append("h.fqdn CONTAINS $host")
        params["host"] = host
    if online_only:
        where.append("h.status = 'online'")

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    query = (
        "MATCH (h:Host)-[:PART_OF]->(d:Domain) "
        f"{where_clause} "
        "RETURN d.name AS domain, h.fqdn AS host, h.status AS status, h.last_seen_ts AS last_seen_ts, h.sources AS sources, h.ports AS ports "
        "ORDER BY h.last_seen_ts DESC NULLS LAST "
        "LIMIT $limit"
    )
    return neo4j_client.run(query, params)


def ensure_constraints() -> None:
    # Unique constraints for fast MERGE operations
    for stmt in [
        "CREATE CONSTRAINT domain_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE",
        "CREATE CONSTRAINT host_unique IF NOT EXISTS FOR (h:Host) REQUIRE h.fqdn IS UNIQUE",
        "CREATE CONSTRAINT ip_unique IF NOT EXISTS FOR (i:IP) REQUIRE i.addr IS UNIQUE",
        "CREATE CONSTRAINT url_unique IF NOT EXISTS FOR (u:URL) REQUIRE u.value IS UNIQUE",
        "CREATE CONSTRAINT email_unique IF NOT EXISTS FOR (e:Email) REQUIRE e.value IS UNIQUE",
        "CREATE CONSTRAINT module_unique IF NOT EXISTS FOR (m:Module) REQUIRE m.name IS UNIQUE",
        "CREATE CONSTRAINT event_unique IF NOT EXISTS FOR (ev:Event) REQUIRE ev.id IS UNIQUE",
        "CREATE CONSTRAINT dns_name_unique IF NOT EXISTS FOR (dn:DNS_NAME) REQUIRE dn.name IS UNIQUE",
        "CREATE CONSTRAINT open_port_unique IF NOT EXISTS FOR (op:OPEN_TCP_PORT) REQUIRE op.endpoint IS UNIQUE",
        "CREATE CONSTRAINT technology_unique IF NOT EXISTS FOR (t:TECHNOLOGY) REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT asn_unique IF NOT EXISTS FOR (a:ASN) REQUIRE a.number IS UNIQUE",
        "CREATE CONSTRAINT protocol_unique IF NOT EXISTS FOR (p:PROTOCOL) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT finding_unique IF NOT EXISTS FOR (f:FINDING) REQUIRE f.id IS UNIQUE",
        "CREATE CONSTRAINT mobile_app_unique IF NOT EXISTS FOR (ma:MOBILE_APP) REQUIRE ma.name IS UNIQUE",
        "CREATE CONSTRAINT social_unique IF NOT EXISTS FOR (s:SOCIAL) REQUIRE s.handle IS UNIQUE",
        "CREATE CONSTRAINT org_stub_unique IF NOT EXISTS FOR (og:ORG_STUB) REQUIRE og.name IS UNIQUE",
        "CREATE CONSTRAINT azure_tenant_unique IF NOT EXISTS FOR (az:AZURE_TENANT) REQUIRE az.id IS UNIQUE",
    ]:
        list(neo4j_client.run(stmt))


def ingest_event(event: dict[str, Any], default_domain: str | None = None) -> None:
    # Normalize
    etype = event.get("type") or "UNKNOWN"
    emodule = event.get("module") or "unknown"
    ts = event.get("ts") or event.get("time") or 0
    evid = event.get("id") or f"{etype}:{emodule}:{ts}:{hash(str(event))}"
    data = event.get("data") or {}

    # Common normalized values
    value = (event.get("data") or {}).get("value")

    params: dict[str, Any] = {
        "etype": etype,
        "module": emodule,
        "ts": int(ts) if ts else 0,
        "evid": evid,
        # Store event payload as JSON string to satisfy Neo4j property types
        "raw": json.dumps(event, ensure_ascii=False, default=str),
        "host": data.get("host") or data.get("name") or data.get("fqdn"),
        "domain": data.get("domain") or default_domain,
        "ip": data.get("ip") or data.get("addr"),
        # Treat URL_UNVERIFIED like URL for storage visibility
        "url": data.get("url") or (value if etype in ("URL", "URL_UNVERIFIED") else data.get("url")),
        "email": data.get("email") or (value if etype == "EMAIL_ADDRESS" else data.get("email")),
        "port": data.get("port"),
        "status": data.get("status") or "online",
        "sources": [emodule],
        "dns_name": None,
        "open_port_endpoint": None,
        "technology": None,
        # Optional typed extras
        "asn_number": None,
        "asn_name": None,
        "protocol_name": None,
        "finding_id": None,
        "finding_severity": None,
        "mobile_app_name": None,
        "social_handle": None,
        "org_stub_name": None,
        "azure_tenant_id": None,
    }

    # Extract DNS_NAME specific fields
    if etype == "DNS_NAME":
        params["dns_name"] = data.get("name") or data.get("host") or value
    
    # Extract OPEN_TCP_PORT specific fields
    if etype == "OPEN_TCP_PORT":
        host_val = data.get("host") or ""
        port_val = data.get("port") or 0
        params["open_port_endpoint"] = f"{host_val}:{port_val}"
        params["port"] = port_val
    
    # Extract TECHNOLOGY specific fields
    if etype == "TECHNOLOGY":
        params["technology"] = data.get("technology") or data.get("name")

    # IP_ADDRESS events sometimes provide only value
    if etype == "IP_ADDRESS" and not params["ip"]:
        params["ip"] = value

    # ASN mapping
    if etype == "ASN":
        asn_raw = data.get("asn") or data.get("number") or value
        if asn_raw is not None:
            try:
                # Normalize to integer-like string (strip leading 'AS')
                asn_str = str(asn_raw).upper().lstrip("AS")
            except Exception:
                asn_str = str(asn_raw)
            params["asn_number"] = asn_str
        params["asn_name"] = data.get("name") or data.get("holder")

    # PROTOCOL mapping
    if etype == "PROTOCOL":
        params["protocol_name"] = data.get("name") or value

    # FINDING mapping
    if etype == "FINDING":
        params["finding_id"] = data.get("id") or value
        params["finding_severity"] = data.get("severity")

    # MOBILE_APP
    if etype == "MOBILE_APP":
        params["mobile_app_name"] = data.get("name") or value

    # SOCIAL
    if etype == "SOCIAL":
        params["social_handle"] = data.get("handle") or data.get("url") or value


    # ORG_STUB
    if etype == "ORG_STUB":
        params["org_stub_name"] = data.get("name") or value

    # AZURE_TENANT
    if etype == "AZURE_TENANT":
        params["azure_tenant_id"] = data.get("tenant_id") or value

    cypher = [
        "MERGE (m:Module {name: $module})",
        "MERGE (ev:Event {id: $evid})",
        "SET ev.type = $etype, ev.ts = $ts, ev.raw = $raw",
    ]

    if params["domain"]:
        cypher += [
            "MERGE (d:Domain {name: $domain})",
            "MERGE (ev)-[:ABOUT]->(d)",
        ]
    if params["host"]:
        cypher += [
            "MERGE (h:Host {fqdn: $host})",
            "SET h.status = coalesce($status, h.status), h.last_seen_ts = $ts, h.sources = coalesce(h.sources, []) + $sources",
            "MERGE (ev)-[:ABOUT]->(h)",
        ]
    if params["ip"]:
        cypher += [
            "MERGE (i:IP {addr: $ip})",
            "MERGE (ev)-[:ABOUT]->(i)",
        ]
    if params["url"]:
        cypher += [
            "MERGE (u:URL {value: $url})",
            "MERGE (ev)-[:ABOUT]->(u)",
        ]
    if params["email"]:
        cypher += [
            "MERGE (e:Email {value: $email})",
            "MERGE (ev)-[:ABOUT]->(e)",
        ]
    
    # DNS_NAME node
    if params["dns_name"]:
        cypher += [
            "MERGE (dn:DNS_NAME {name: $dns_name})",
            "SET dn.last_seen_ts = $ts",
            "MERGE (ev)-[:ABOUT]->(dn)",
        ]
    
    # OPEN_TCP_PORT node
    if params["open_port_endpoint"]:
        cypher += [
            "MERGE (op:OPEN_TCP_PORT {endpoint: $open_port_endpoint})",
            "SET op.port = $port, op.host = $host, op.last_seen_ts = $ts",
            "MERGE (ev)-[:ABOUT]->(op)",
        ]
        if params["host"]:
            cypher += ["MERGE (op)-[:ON_HOST]->(h)"]
    
    # TECHNOLOGY node
    if params["technology"]:
        cypher += [
            "MERGE (t:TECHNOLOGY {name: $technology})",
            "MERGE (ev)-[:ABOUT]->(t)",
        ]
        if params["host"]:
            cypher += ["MERGE (h)-[:USES_TECH]->(t)"]
    
    if params["port"] and params["host"]:
        cypher += [
            "SET h.ports = apoc.coll.toSet(coalesce(h.ports, []) + [$port])",
        ]

    # ASN node
    if params["asn_number"]:
        cypher += [
            "MERGE (a:ASN {number: $asn_number})",
            "SET a.name = coalesce($asn_name, a.name)",
            "MERGE (ev)-[:ABOUT]->(a)",
        ]
        if params["ip"]:
            cypher += [
                "MERGE (i:IP {addr: $ip})",
                "MERGE (i)-[:IN_ASN]->(a)",
            ]

    # PROTOCOL node
    if params["protocol_name"]:
        cypher += [
            "MERGE (pr:PROTOCOL {name: $protocol_name})",
            "MERGE (ev)-[:ABOUT]->(pr)",
        ]

    # FINDING node
    if params["finding_id"]:
        cypher += [
            "MERGE (f:FINDING {id: $finding_id})",
            "SET f.severity = coalesce($finding_severity, f.severity)",
            "MERGE (ev)-[:ABOUT]->(f)",
        ]
        if params["host"]:
            cypher += ["MERGE (f)-[:ON_HOST]->(h)"]

    # MOBILE_APP node
    if params["mobile_app_name"]:
        cypher += [
            "MERGE (ma:MOBILE_APP {name: $mobile_app_name})",
            "MERGE (ev)-[:ABOUT]->(ma)",
        ]

    # SOCIAL node
    if params["social_handle"]:
        cypher += [
            "MERGE (s:SOCIAL {handle: $social_handle})",
            "MERGE (ev)-[:ABOUT]->(s)",
        ]


    # ORG_STUB node
    if params["org_stub_name"]:
        cypher += [
            "MERGE (og:ORG_STUB {name: $org_stub_name})",
            "MERGE (ev)-[:ABOUT]->(og)",
        ]
        if params["domain"]:
            cypher += ["MERGE (og)-[:OWNS]->(d)"]

    # AZURE_TENANT node
    if params["azure_tenant_id"]:
        cypher += [
            "MERGE (az:AZURE_TENANT {id: $azure_tenant_id})",
            "MERGE (ev)-[:ABOUT]->(az)",
        ]

    cypher += [
        "MERGE (ev)-[:EMITTED_BY]->(m)",
        # Connect host to domain when both exist
        "WITH * WHERE $domain IS NOT NULL AND $host IS NOT NULL",
        "MERGE (h)-[:PART_OF]->(d)",
    ]

    # Ensure the write executes by consuming the generator
    list(neo4j_client.run("\n".join(cypher), params))


def query_events(
    types: list[str] | None = None,
    modules: list[str] | None = None,
    domain: str | None = None,
    host: str | None = None,
    since_ts: int | None = None,
    until_ts: int | None = None,
    limit: int = 200,
) -> Iterable[dict]:
    where = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if types:
        where.append("ev.type IN $types")
        params["types"] = types
    if modules:
        where.append("m.name IN $modules")
        params["modules"] = modules
    if since_ts:
        where.append("ev.ts >= $since_ts")
        params["since_ts"] = since_ts
    if until_ts:
        where.append("ev.ts <= $until_ts")
        params["until_ts"] = until_ts

    match = ["MATCH (ev:Event)-[:EMITTED_BY]->(m:Module)"]
    if domain:
        match.append("MATCH (ev)-[:ABOUT]->(d:Domain)")
        where.append("d.name CONTAINS $domain")
        params["domain"] = domain
    if host:
        match.append("MATCH (ev)-[:ABOUT]->(h:Host)")
        where.append("h.fqdn CONTAINS $host")
        params["host"] = host

    query = (
        "\n".join(match)
        + "\nWHERE "
        + " AND ".join(where)
        + "\nRETURN ev.id AS id, ev.type AS type, ev.ts AS ts, m.name AS module, ev.raw AS raw\n"
        + "ORDER BY ev.ts DESC LIMIT $limit"
    )
    return neo4j_client.run(query, params)


def cleanup_graph(now_epoch: int) -> dict:
    stats: dict[str, int] = {
        "deleted_events": 0,
        "deleted_offline_hosts": 0,
        "deleted_orphans": 0,
    }
    if not settings.cleanup_enabled:
        return stats

    # Delete old events
    if settings.event_retention_days > 0:
        threshold = now_epoch - settings.event_retention_days * 86400
        for _ in neo4j_client.run(
            "MATCH (ev:Event) WHERE ev.ts IS NOT NULL AND ev.ts < $threshold WITH ev LIMIT 10000 DETACH DELETE ev RETURN 1",
            {"threshold": threshold},
        ):
            stats["deleted_events"] += 1

    # Delete offline hosts older than retention
    if settings.offline_host_retention_days > 0:
        threshold_h = now_epoch - settings.offline_host_retention_days * 86400
        for _ in neo4j_client.run(
            "MATCH (h:Host) WHERE h.status = 'offline' AND h.last_seen_ts IS NOT NULL AND h.last_seen_ts < $threshold WITH h LIMIT 10000 DETACH DELETE h RETURN 1",
            {"threshold": threshold_h},
        ):
            stats["deleted_offline_hosts"] += 1

    # Remove orphaned nodes (no relationships)
    if settings.orphan_cleanup_enabled:
        for _ in neo4j_client.run(
            "MATCH (n) WHERE NOT (n)--() WITH n LIMIT 10000 DETACH DELETE n RETURN 1"
        ):
            stats["deleted_orphans"] += 1

    return stats



# --- BBOT scan directory importer (post-scan detailed results) ---

def _record_to_event_like(record: Any) -> dict | None:
    """Best-effort conversion of a BBOT record into our event shape.
    Returns None if the record cannot be interpreted.
    """
    try:
        if not isinstance(record, dict):
            return None
        # If it already looks like an event
        if record.get("type") and (isinstance(record.get("data"), dict) or record.get("data") is None):
            # Ensure data is dict
            data = record.get("data") or {}
            return {"type": record.get("type"), "module": record.get("module"), "ts": record.get("ts"), "id": record.get("id"), "data": data}

        # Common artifact patterns: flatten into event-like structure
        candidate: dict[str, Any] = {}
        data: dict[str, Any] = {}

        # Infer type from keys
        if "fqdn" in record or "host" in record or "name" in record:
            # DNS/Host-like
            t = "DNS_NAME" if "name" in record or "fqdn" in record else "HOST"
            data.update(record)
            candidate = {"type": t, "data": data}
        elif "ip" in record or "addr" in record:
            data.update(record)
            candidate = {"type": "IP_ADDRESS", "data": data}
        elif "url" in record or (record.get("value") and isinstance(record.get("value"), str) and record.get("value").startswith("http")):
            data.update(record)
            candidate = {"type": "URL", "data": data}
        elif "email" in record:
            data.update(record)
            candidate = {"type": "EMAIL_ADDRESS", "data": data}
        elif "port" in record and ("host" in record or "fqdn" in record):
            data.update(record)
            candidate = {"type": "OPEN_TCP_PORT", "data": data}
        elif "technology" in record or (record.get("type") == "technology"):
            data.update(record)
            tech_name = record.get("technology") or record.get("name")
            if tech_name:
                data["technology"] = tech_name
            candidate = {"type": "TECHNOLOGY", "data": data}
        elif "asn" in record or record.get("type") == "ASN":
            data.update(record)
            candidate = {"type": "ASN", "data": data}
        elif record.get("severity") and record.get("id"):
            # Likely a finding
            data.update(record)
            candidate = {"type": "FINDING", "data": data}
        else:
            return None

        # Pass through module/ts/id if present
        for k in ("module", "ts", "id"):
            if k in record:
                candidate[k] = record[k]
        return candidate
    except Exception:
        return None


def ingest_scan_dir(scan_dir: str, default_domain: str | None = None) -> int:
    """Import events/artifacts from a BBOT scan directory.
    Returns number of records ingested.
    """
    base = Path(scan_dir)
    if not base.is_dir():
        return 0
    ingested = 0
    # Candidate files to parse
    candidates = [
        "events.jsonl",
        "events.json",
        "artifacts.jsonl",
        "artifacts.json",
        "results.json",
        "scan.json",
        "graph.json",
        # Common BBOT consolidated output
        "output.json",
        "output.csv",
        # Simple text artifacts
        "subdomains.txt",
        "emails.txt",
    ]
    for name in candidates:
        p = base / name
        if not p.exists():
            continue
        try:
            if p.name in ("subdomains.txt", "emails.txt"):
                with p.open("r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        val = line.strip()
                        if not val:
                            continue
                        if p.name == "subdomains.txt":
                            ev = {"type": "DNS_NAME", "data": {"name": val, "host": val, "domain": default_domain}}
                        else:
                            ev = {"type": "EMAIL_ADDRESS", "data": {"email": val, "value": val}}
                        ingest_event(ev, default_domain=default_domain)
                        ingested += 1
            elif p.name == "output.csv":
                with p.open("r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if not isinstance(row, dict):
                            continue
                        # Normalize row to event-like
                        etype = row.get("type") or row.get("Type") or "UNKNOWN"
                        data: dict[str, Any] = {}
                        # Pass through common fields if exist
                        for k in ("value","url","host","fqdn","domain","ip","addr","email","port","name","technology"):
                            if row.get(k):
                                data[k] = row[k]
                        ev = _record_to_event_like({
                            "type": etype,
                            "data": data,
                            "module": row.get("module") or row.get("Module"),
                            "ts": row.get("ts") or row.get("Timestamp"),
                            "id": row.get("id") or row.get("ID"),
                        })
                        if ev:
                            ingest_event(ev, default_domain=default_domain)
                            ingested += 1
            elif p.suffix == ".jsonl":
                with p.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except Exception:
                            continue
                        ev = _record_to_event_like(rec)
                        if ev:
                            ingest_event(ev, default_domain=default_domain)
                            ingested += 1
            else:
                obj = json.loads(p.read_text(encoding="utf-8"))
                items: list[Any] = []
                if isinstance(obj, list):
                    items = obj
                elif isinstance(obj, dict):
                    for key in ("events", "artifacts", "results", "items", "data"):
                        if isinstance(obj.get(key), list):
                            items = obj[key]
                            break
                    if not items:
                        # Sometimes single record
                        items = [obj]
                for rec in items:
                    ev = _record_to_event_like(rec)
                    if ev:
                        ingest_event(ev, default_domain=default_domain)
                        ingested += 1
        except Exception:
            # Ignore file-level errors, proceed to next
            continue
    # Parse simple table files (e.g., asns-table-*.txt)
    try:
        for table_file in base.glob("*asns-table-*.txt"):
            with table_file.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.lower().startswith("asn"):
                        # likely a header
                        continue
                    # Try formats: "AS12345, Name" or "AS12345\tName" or "12345 Name"
                    parts = [p for p in (line.replace("\t", ",").split(",")) if p.strip()]
                    if not parts:
                        continue
                    asn_part = parts[0].strip()
                    asn_num = asn_part.upper().lstrip("AS")
                    asn_name = parts[1].strip() if len(parts) > 1 else None
                    ev = _record_to_event_like({"type": "ASN", "data": {"asn": asn_num, "name": asn_name}})
                    if ev:
                        ingest_event(ev, default_domain=default_domain)
                        ingested += 1
    except Exception:
        pass
    return ingested


def ingest_latest_scan_dirs(default_domain: str | None = None, max_dirs: int = 2, max_age_seconds: int = 900) -> int:
    """Find the most recent BBOT scan directories and ingest from them.
    Returns total records ingested.
    """
    # Default BBOT scans location inside container
    candidate_roots = [
        os.path.expanduser("~/.bbot/scans"),
        "/root/.bbot/scans",
        "/home/appuser/.bbot/scans",
    ]
    dirs: list[Path] = []
    for r in candidate_roots:
        root = Path(r)
        if root.exists():
            dirs.extend([d for d in root.iterdir() if d.is_dir()])
    if not dirs:
        return 0
    # prefer dirs containing consolidated outputs
    dirs = [d for d in dirs if (d / "output.json").exists() or (d / "output.csv").exists() or (d / "subdomains.txt").exists()]
    dirs.sort(key=lambda d: max((d / "output.json").stat().st_mtime if (d / "output.json").exists() else d.stat().st_mtime,
                                (d / "output.csv").stat().st_mtime if (d / "output.csv").exists() else d.stat().st_mtime,
                                (d / "subdomains.txt").stat().st_mtime if (d / "subdomains.txt").exists() else d.stat().st_mtime),
              reverse=True)
    total = 0
    now = int(Path("/").stat().st_mtime)  # cheap current mtime proxy
    for d in dirs[:max_dirs]:
        # skip very old dirs
        try:
            m = max((d / "output.json").stat().st_mtime if (d / "output.json").exists() else d.stat().st_mtime,
                    (d / "output.csv").stat().st_mtime if (d / "output.csv").exists() else d.stat().st_mtime,
                    (d / "subdomains.txt").stat().st_mtime if (d / "subdomains.txt").exists() else d.stat().st_mtime)
        except Exception:
            m = d.stat().st_mtime
        if max_age_seconds > 0 and (now - m) > max_age_seconds:
            continue
        total += ingest_scan_dir(str(d), default_domain=default_domain)
    return total


def _get_scan_roots() -> list[Path]:
    roots = [
        Path(os.path.expanduser("~/.bbot/scans")),
        Path("/root/.bbot/scans"),
        Path("/home/appuser/.bbot/scans"),
    ]
    uniq: list[Path] = []
    for r in roots:
        if r.exists() and r not in uniq:
            uniq.append(r)
    return uniq
def list_scan_dirs() -> list[Path]:
    dirs: list[Path] = []
    for r in _get_scan_roots():
        try:
            for d in r.iterdir():
                if d.is_dir():
                    dirs.append(d)
        except Exception:
            continue
    return dirs




def _file_contains_text(p: Path, needle: str) -> bool:
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as f:
            for chunk in f:
                if needle in chunk:
                    return True
    except Exception:
        return False
    return False


def _is_sub_of_domain(domain: str, name: str) -> bool:
    d = domain.lower().strip()
    n = name.lower().strip()
    return n == d or n.endswith("." + d)


def find_scan_dirs_for_target(target: str, max_dirs: int = 2, max_age_seconds: int = 3600) -> list[Path]:
    """Score and return likely scan directories for the given target domain."""
    dirs: list[tuple[Path, int, float]] = []
    for root in _get_scan_roots():
        for d in root.iterdir():
            if not d.is_dir():
                continue
            try:
                # base recency
                mtime = d.stat().st_mtime
            except Exception:
                continue
            score = 0
            # Prefer consolidated outputs
            out_json = d / "output.json"
            out_csv = d / "output.csv"
            subs_txt = d / "subdomains.txt"
            emails_txt = d / "emails.txt"
            scan_log = d / "scan.log"
            # Search for target string
            if out_json.exists() and _file_contains_text(out_json, target):
                score += 100
                try:
                    mtime = max(mtime, out_json.stat().st_mtime)
                except Exception:
                    pass
            if scan_log.exists() and _file_contains_text(scan_log, target):
                score += 80
                try:
                    mtime = max(mtime, scan_log.stat().st_mtime)
                except Exception:
                    pass
            if out_csv.exists() and _file_contains_text(out_csv, target):
                score += 50
                try:
                    mtime = max(mtime, out_csv.stat().st_mtime)
                except Exception:
                    pass
            # subdomains: look for suffix match
            if subs_txt.exists():
                try:
                    with subs_txt.open("r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if _is_sub_of_domain(target, line.strip()):
                                score += 60
                                break
                except Exception:
                    pass
                try:
                    mtime = max(mtime, subs_txt.stat().st_mtime)
                except Exception:
                    pass
            if emails_txt.exists() and _file_contains_text(emails_txt, "@" + target):
                score += 20
                try:
                    mtime = max(mtime, emails_txt.stat().st_mtime)
                except Exception:
                    pass
            # Penalize dirs with no indicative files
            if score == 0 and not (out_json.exists() or out_csv.exists() or subs_txt.exists()):
                continue
            # Age filter
            if max_age_seconds > 0:
                try:
                    now_m = max(Path("/").stat().st_mtime, mtime)
                except Exception:
                    now_m = mtime
                if (now_m - mtime) > max_age_seconds:
                    continue
            dirs.append((d, score, mtime))
    # sort by score desc, then mtime desc
    dirs.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return [d for d, _, _ in dirs[:max_dirs]]


def find_scan_dirs_by_name(scan_name: str, max_dirs: int = 1, max_age_seconds: int = 7200) -> list[Path]:
    """Return scan directories matching the exact BBOT scan name.
    Matches directory name equals scan_name, or scan.log contains 'Scan <scan_name>'.
    """
    results: list[tuple[Path, float]] = []
    for root in _get_scan_roots():
        for d in root.iterdir():
            if not d.is_dir():
                continue
            try:
                mtime = d.stat().st_mtime
            except Exception:
                continue
            if d.name == scan_name:
                results.append((d, mtime))
                continue
            slog = d / "scan.log"
            if slog.exists() and _file_contains_text(slog, f"Scan {scan_name} "):
                try:
                    mtime = max(mtime, slog.stat().st_mtime)
                except Exception:
                    pass
                results.append((d, mtime))
    # filter by age if requested
    if max_age_seconds > 0 and results:
        try:
            now_m = max(Path("/").stat().st_mtime, max(m for _, m in results))
        except Exception:
            now_m = max(m for _, m in results)
        results = [(p, m) for (p, m) in results if (now_m - m) <= max_age_seconds]
    results.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in results[:max_dirs]]


def ingest_dirs_by_scan_name(scan_name: str, default_domain: str | None = None, max_dirs: int = 1, max_age_seconds: int = 7200) -> tuple[int, list[str]]:
    selected = find_scan_dirs_by_name(scan_name, max_dirs=max_dirs, max_age_seconds=max_age_seconds)
    total = 0
    used: list[str] = []
    for d in selected:
        used.append(str(d))
        total += ingest_scan_dir(str(d), default_domain=default_domain)
    return total, used


def ingest_dirs_for_target(target: str, default_domain: str | None = None, max_dirs: int = 1, max_age_seconds: int = 3600) -> tuple[int, list[str]]:
    """Find and ingest results from dirs most likely matching the given target.
    Returns (ingested_count, used_dir_names).
    """
    selected = find_scan_dirs_for_target(target, max_dirs=max_dirs, max_age_seconds=max_age_seconds)
    total = 0
    used: list[str] = []
    for d in selected:
        used.append(str(d))
        total += ingest_scan_dir(str(d), default_domain=default_domain)
    return total, used

