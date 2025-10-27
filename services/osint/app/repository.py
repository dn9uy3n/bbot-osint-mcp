from typing import Iterable, Any
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
    neo4j_client.run(query, record.model_dump())


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
    ]:
        list(neo4j_client.run(stmt))


def ingest_event(event: dict[str, Any], default_domain: str | None = None) -> None:
    # Normalize
    etype = event.get("type") or "UNKNOWN"
    emodule = event.get("module") or "unknown"
    ts = event.get("ts") or event.get("time") or 0
    evid = event.get("id") or f"{etype}:{emodule}:{ts}:{hash(str(event))}"
    data = event.get("data") or {}

    params: dict[str, Any] = {
        "etype": etype,
        "module": emodule,
        "ts": int(ts) if ts else 0,
        "evid": evid,
        "raw": event,
        "host": data.get("host") or data.get("name") or data.get("fqdn"),
        "domain": data.get("domain") or default_domain,
        "ip": data.get("ip") or data.get("addr"),
        "url": data.get("url") or data.get("value") if etype == "URL" else data.get("url"),
        "email": data.get("email") or data.get("value") if etype == "EMAIL_ADDRESS" else data.get("email"),
        "port": data.get("port"),
        "status": data.get("status") or "online",
        "sources": [emodule],
        "dns_name": None,
        "open_port_endpoint": None,
        "technology": None,
    }

    # Extract DNS_NAME specific fields
    if etype == "DNS_NAME":
        params["dns_name"] = data.get("name") or data.get("host")
    
    # Extract OPEN_TCP_PORT specific fields
    if etype == "OPEN_TCP_PORT":
        host_val = data.get("host") or ""
        port_val = data.get("port") or 0
        params["open_port_endpoint"] = f"{host_val}:{port_val}"
        params["port"] = port_val
    
    # Extract TECHNOLOGY specific fields
    if etype == "TECHNOLOGY":
        params["technology"] = data.get("technology") or data.get("name")

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

    cypher += [
        "MERGE (ev)-[:EMITTED_BY]->(m)",
        # Connect host to domain when both exist
        "WITH * WHERE $domain IS NOT NULL AND $host IS NOT NULL",
        "MERGE (h)-[:PART_OF]->(d)",
    ]

    neo4j_client.run("\n".join(cypher), params)


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
            "MATCH (n) WHERE size((n)--()) = 0 WITH n LIMIT 10000 DETACH DELETE n RETURN 1"
        ):
            stats["deleted_orphans"] += 1

    return stats


