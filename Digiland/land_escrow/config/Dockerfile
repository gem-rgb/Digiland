# =============================================================================
# Digiland - Multi-Stage Dockerfile
# =============================================================================
# Stages:
#   1. builder   - Install Python & Node.js dependencies, build frontend assets
#   2. production - Minimal runtime image with compiled assets
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for PostGIS, Pillow, and building
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PostgreSQL client & dev headers
    libpq-dev \
    postgresql-client \
    # PostGIS / GDAL / GEOS / PROJ dependencies
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libsqlite3-mod-spatialite \
    # Image processing
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    libtiff-dev \
    # Crypto & XML
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    libssl-dev \
    # Build tools
    build-essential \
    gcc \
    g++ \
    cmake \
    # Node.js
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x for frontend builds
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python Dependencies ---
COPY config/requirements.txt ./config/requirements.txt
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r config/requirements.txt \
    && pip install \
    psycopg2-binary==2.9.9 \
    django-redis==5.4.0 \
    celery==5.3.6 \
    django-celery-beat==2.6.0 \
    django-celery-results==2.5.1 \
    gevent==24.2.1 \
    django-storages==1.14.3 \
    boto3==1.35.0

# --- Frontend Build ---
COPY client/package.json client/package-lock.json ./client/
WORKDIR /app/client
RUN npm ci --only=production
COPY client/ ./
RUN npm run build

# Back to app root
WORKDIR /app

# --- Copy Full Project ---
COPY . .

# --- Collect Static Files ---
# Set DJANGO_SETTINGS_MODULE so collectstatic works
ENV DJANGO_SETTINGS_MODULE=land_escrow.settings \
    SECRET_KEY=build-time-dummy-key-not-for-production \
    DEBUG=False \
    DATABASE_URL=sqlite:///tmp/dummy.db

RUN python manage.py collectstatic --noinput --clear 2>/dev/null || true

# ---------------------------------------------------------------------------
# Stage 2: Production
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=land_escrow.settings \
    # Gunicorn config
    GUNICORN_WORKERS=4 \
    GUNICORN_THREADS=2 \
    GUNICORN_TIMEOUT=120 \
    GUNICORN_BIND=0.0.0.0:8000 \
    # Path
    PATH="/app/.local/bin:${PATH}" \
    PYTHONPATH="/app:${PYTHONPATH}"

# Install only runtime system dependencies (no dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PostgreSQL client (for wait-for-db script)
    libpq5 \
    postgresql-client \
    # PostGIS runtime libraries
    gdal-bin \
    libgdal34 \
    libgeos-c1v5 \
    libproj25 \
    libsqlite3-mod-spatialite \
    # Image processing runtime
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    libtiff6 \
    # Crypto & XML runtime
    libffi8 \
    libxml2 \
    libxslt1.1 \
    # curl for healthchecks
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r digiland && useradd -r -g digiland -d /app -s /sbin/nologin digiland

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app /app

# Copy frontend build output
COPY --from=builder /app/client/dist /app/client/dist

# Copy static files collected in builder
COPY --from=builder /app/staticfiles /app/staticfiles

# Ensure media directory exists with correct permissions
RUN mkdir -p /app/media && chown -R digiland:digiland /app/media /app/staticfiles

# Copy entrypoint script
COPY config/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user
USER digiland

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -sf http://localhost:8000/admin/ || exit 1

# Entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command (can be overridden by docker-compose)
CMD ["gunicorn", "land_escrow.wsgi:application", "--config", "config/gunicorn.conf.py"]
