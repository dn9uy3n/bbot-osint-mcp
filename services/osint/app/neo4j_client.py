from neo4j import GraphDatabase, Driver
from typing import Any, Iterable
from .config import settings
import time
from neo4j.exceptions import ServiceUnavailable


class Neo4jClient:
    def __init__(self) -> None:
        # Try multiple hostnames in case Docker DNS not ready yet
        candidate_hosts = [
            str(settings.neo4j_host or "neo4j"),
            "neo4j",
            "bbot_neo4j",
        ]
        auth = (settings.neo4j_username, settings.neo4j_password)
        last_exc: Exception | None = None
        connected = False
        for host in candidate_hosts:
            uri = f"{settings.neo4j_scheme}://{host}:{settings.neo4j_port}"
            for _ in range(120):  # up to ~120s
                try:
                    self._driver: Driver = GraphDatabase.driver(uri, auth=auth)
                    with self._driver.session() as session:
                        session.run("RETURN 1").consume()
                    connected = True
                    last_exc = None
                    break
                except (ServiceUnavailable, Exception) as exc:
                    last_exc = exc
                    time.sleep(1)
            if connected:
                break
        if not connected and last_exc:
            raise last_exc

    def close(self) -> None:
        self._driver.close()

    def run(self, cypher: str, parameters: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(cypher, parameters or {})
            for record in result:
                yield record.data()


neo4j_client = Neo4jClient()


