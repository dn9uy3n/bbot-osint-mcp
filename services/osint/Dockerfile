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
# Provide example config by default; mount real init_config.json in production
COPY init_config.json.example /app/init_config.json

# Non-root user (optional)
RUN useradd -ms /bin/bash appuser
USER appuser

EXPOSE 8000

ENTRYPOINT ["bash", "-lc"]
CMD ["uvicorn app.main:app --host 0.0.0.0 --port 8000"]


