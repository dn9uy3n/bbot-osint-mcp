from pydantic import BaseModel
import os


class Settings(BaseModel):
    api_token: str = os.getenv("API_TOKEN", "")

    neo4j_scheme: str = os.getenv("NEO4J_SCHEME", "bolt")
    neo4j_host: str = os.getenv("NEO4J_HOST", "neo4j")
    neo4j_port: int = int(os.getenv("NEO4J_PORT", "7687"))
    neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")

    # Uvicorn TLS (optional; recommended to terminate TLS at reverse proxy)
    ssl_certfile: str | None = os.getenv("SSL_CERTFILE")
    ssl_keyfile: str | None = os.getenv("SSL_KEYFILE")

    # Public base URL (optional)
    public_base_url: str | None = os.getenv("PUBLIC_BASE_URL")

    # App security
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    max_concurrent_scans: int = int(os.getenv("MAX_CONCURRENT_SCANS", "2"))

    # Cleanup policy
    cleanup_enabled: bool = os.getenv("CLEANUP_ENABLED", "true").lower() == "true"
    event_retention_days: int = int(os.getenv("EVENT_RETENTION_DAYS", "30"))
    offline_host_retention_days: int = int(os.getenv("OFFLINE_HOST_RETENTION_DAYS", "30"))
    orphan_cleanup_enabled: bool = os.getenv("ORPHAN_CLEANUP_ENABLED", "true").lower() == "true"

    # Telegram notifications
    telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID")

    # Init config
    init_config_path: str = os.getenv("INIT_CONFIG_PATH", "/app/init_config.json")
    default_targets: list[str] = []
    scan_defaults: dict = {}


settings = Settings()


