# Multi-stage production Dockerfile for fersie-app
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.12/site-packages:$PYTHONPATH"

COPY --from=builder /install /install

# Create volume mount points for database, media, and static files
RUN mkdir -p /app/db /app/media /app/staticfiles

# Copy application source code
COPY . .
RUN chmod +x /app/entrypoint.sh

# Collect static files during image build
RUN python manage.py collectstatic --noinput || true

# Expose port 8000 for Django / Gunicorn
EXPOSE 8000

# Volume mount points for persistent storage
VOLUME ["/app/db", "/app/media"]

# Production entrypoint using entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
