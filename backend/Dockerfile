# backend/Dockerfile
FROM python:3.13-slim

# Set environment variables
# Adding /opt/venv/bin to PATH ensures all commands (uvicorn, alembic, python) use the venv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# 1. Create virtual environment
RUN python -m venv /opt/venv

# 2. Install Python dependencies into the virtual environment
COPY requirements.txt .
RUN /opt/venv/bin/pip install --upgrade pip && /opt/venv/bin/pip install -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run application (overridden by docker-compose for migrations/seed)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]