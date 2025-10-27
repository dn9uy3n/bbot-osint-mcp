from neo4j import GraphDatabase, Driver
from typing import Any, Iterable
from .config import settings


class Neo4jClient:
    def __init__(self) -> None:
        uri = f"{settings.neo4j_scheme}://{settings.neo4j_host}:{settings.neo4j_port}"
        self._driver: Driver = GraphDatabase.driver(uri, auth=(settings.neo4j_username, settings.neo4j_password))

    def close(self) -> None:
        self._driver.close()

    def run(self, cypher: str, parameters: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(cypher, parameters or {})
            for record in result:
                yield record.data()


neo4j_client = Neo4jClient()


