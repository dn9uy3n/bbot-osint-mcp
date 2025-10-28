FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BBOT_NO_INSTALL_DEPS=1

WORKDIR /app

# System dependencies for building and runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    gnupg \
    apt-transport-https \
    git \
    openssl \
    p7zip-full \
    unzip \
    zip \
    sudo \
    default-jre-headless \
    chromium \
    fonts-liberation \
    libasound2 \
    libnss3 \
    libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 libgbm1 \
  && rm -rf /var/lib/apt/lists/*

# Install Node.js (for retirejs and related tools)
RUN set -eux; \
  ARCH="$(dpkg --print-architecture)"; \
  case "$ARCH" in \
    amd64) NODE_ARCH="x64" ;; \
    arm64) NODE_ARCH="arm64" ;; \
    *) NODE_ARCH="x64" ;; \
  esac; \
  curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
  apt-get update && apt-get install -y --no-install-recommends nodejs && \
  npm -v && node -v && \
  rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Pre-install common heavy Python deps used by BBOT modules to reduce runtime installs
RUN pip install --no-cache-dir \
    python-Wappalyzer==0.3.1 \
    aiohttp==3.9.5 \
    setuptools

# Hint for gowitness headless chromium
ENV CHROME_PATH=/usr/bin/chromium

COPY app /app/app
COPY mcp_server /app/mcp_server

# init_config.json will be mounted from host via docker-compose volumes
# If not mounted, create empty template
RUN echo '{"targets":[],"bbot_modules":{},"TELEGRAM_BOT_TOKEN":"","TELEGRAM_CHAT_ID":"","scan_defaults":{"presets":["subdomain-enum"],"flags":[],"max_workers":2,"spider_depth":2,"spider_distance":1,"spider_links_per_page":10,"allow_deadly":false,"target_sleep_seconds":300,"cycle_sleep_seconds":3600}}' > /app/init_config.json.default

# Non-root user (optional)
RUN useradd -ms /bin/bash appuser \
  && mkdir -p /home/appuser/.bbot/logs \
  && mkdir -p /home/appuser/.bbot/cache \
  && mkdir -p /home/appuser/.bbot/scans \
  && chown -R appuser:appuser /home/appuser/.bbot
USER appuser

EXPOSE 8000

ENTRYPOINT ["bash", "-lc"]
CMD ["uvicorn app.main:app --host 0.0.0.0 --port 8000"]


