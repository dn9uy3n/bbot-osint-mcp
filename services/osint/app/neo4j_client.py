from neo4j import GraphDatabase, Driver
from typing import Any, Iterable
from .config import settings
import time
from neo4j.exceptions import ServiceUnavailable


class Neo4jClient:
    def __init__(self) -> None:
        self._driver: Driver | None = None

    def _ensure_connected(self) -> None:
        if self._driver is not None:
            return
        candidate_hosts = [
            str(settings.neo4j_host or "neo4j"),
            "neo4j",
            "bbot_neo4j",
        ]
        auth = (settings.neo4j_username, settings.neo4j_password)
        last_exc: Exception | None = None
        for host in candidate_hosts:
            uri = f"{settings.neo4j_scheme}://{host}:{settings.neo4j_port}"
            for _ in range(120):
                try:
                    drv: Driver = GraphDatabase.driver(uri, auth=auth)
                    with drv.session() as session:
                        session.run("RETURN 1").consume()
                    self._driver = drv
                    return
                except (ServiceUnavailable, Exception) as exc:
                    last_exc = exc
                    time.sleep(1)
        if last_exc:
            raise last_exc

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def run(self, cypher: str, parameters: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
        self._ensure_connected()
        assert self._driver is not None
        with self._driver.session() as session:
            result = session.run(cypher, parameters or {})
            for record in result:
                yield record.data()


neo4j_client = Neo4jClient()


