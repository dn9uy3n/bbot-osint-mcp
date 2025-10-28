from neo4j import GraphDatabase, Driver
from typing import Any, Iterable
from .config import settings
import time
from neo4j.exceptions import ServiceUnavailable


class Neo4jClient:
    def __init__(self) -> None:
        uri = f"{settings.neo4j_scheme}://{settings.neo4j_host}:{settings.neo4j_port}"
        # Retry connect to allow containerized Neo4j to come up
        last_exc: Exception | None = None
        for _ in range(60):  # up to ~60s
            try:
                self._driver: Driver = GraphDatabase.driver(
                    uri, auth=(settings.neo4j_username, settings.neo4j_password)
                )
                # perform a lightweight check
                with self._driver.session() as session:
                    session.run("RETURN 1").consume()
                last_exc = None
                break
            except ServiceUnavailable as exc:
                last_exc = exc
                time.sleep(1)
        if last_exc:
            raise last_exc

    def close(self) -> None:
        self._driver.close()

    def run(self, cypher: str, parameters: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(cypher, parameters or {})
            for record in result:
                yield record.data()


neo4j_client = Neo4jClient()


