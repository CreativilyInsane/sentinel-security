# backend/Dockerfile
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install system dependencies
#   - build-essential, libpq-dev: needed by asyncpg / cryptography
#   - whois: needed by python-whois (uses the system `whois` client for RDAP)
#   - Playwright runtime deps (libnss3, libatk1.0, libdrm, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    whois \
    # Playwright Chromium runtime dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# 1. Create virtual environment
RUN python -m venv /opt/venv

# 2. Install Python dependencies into the virtual environment
COPY requirements.txt .
RUN /opt/venv/bin/pip install --upgrade pip && /opt/venv/bin/pip install -r requirements.txt

# 3. Pre-install Chromium for Playwright so the worker doesn't need to
#    download it on first start.
RUN /opt/venv/bin/playwright install chromium

# Copy application code
COPY . .

# Storage directory for screenshots (also mounted as a volume in compose)
RUN mkdir -p /app/recon_storage/screenshots
ENV RECON_SCREENSHOT_STORAGE_PATH=/app/recon_storage/screenshots

# Expose port (backend only)
EXPOSE 8000

# Run application (overridden by docker-compose for migrations/seed/worker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
