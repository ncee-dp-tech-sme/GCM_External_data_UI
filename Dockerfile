# 2026-07-30T00:00:00Z - Initial Dockerfile for GCM Web UI (backend + frontend, single container)
#
# Build:  docker build -t gcm-webui .
# Run:    docker run -p 8000:8000 --env-file backend/.env gcm-webui
#
# The backend serves the frontend at / via StaticFiles, so no separate web server
# is needed.  The working directory is /app/backend so the app finds its .env
# (and SQLite DB) relative to CWD — persist /app/backend/gcm_webui.db via a volume.

FROM python:3.11-slim

# Install OS-level dependencies needed by Python packages (e.g. libffi for cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies first (layer cache friendly)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source
COPY backend/app ./backend/app

# Copy frontend assets (served as static files by the backend)
COPY frontend ./frontend

# Copy repo-root helper modules used by certificate/asset/scanner services
COPY common ./common
COPY certificates ./certificates
COPY it_assets ./it_assets
COPY disconnected-scanner ./disconnected-scanner

# Create logs directory
RUN mkdir -p backend/logs

# The app reads .env from CWD (backend/), so set the working directory
WORKDIR /app/backend

# Expose the default port
EXPOSE 8000

# Health-check so container orchestrators know when the app is ready
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start the server; HOST/PORT can be overridden via environment variables
CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
