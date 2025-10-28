FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies for building and runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY mcp /app/mcp

# init_config.json will be mounted from host via docker-compose volumes
# If not mounted, create empty template
RUN echo '{"targets":[],"bbot_modules":{},"TELEGRAM_BOT_TOKEN":"","TELEGRAM_CHAT_ID":"","scan_defaults":{"presets":["subdomain-enum"],"flags":[],"max_workers":2,"spider_depth":2,"spider_distance":1,"spider_links_per_page":10,"allow_deadly":false,"target_sleep_seconds":300,"cycle_sleep_seconds":3600}}' > /app/init_config.json.default

# Non-root user (optional)
RUN useradd -ms /bin/bash appuser
USER appuser

EXPOSE 8000

ENTRYPOINT ["bash", "-lc"]
CMD ["uvicorn app.main:app --host 0.0.0.0 --port 8000"]


