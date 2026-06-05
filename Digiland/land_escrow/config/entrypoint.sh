#!/usr/bin/env bash
# =============================================================================
# Digiland - Docker Entrypoint Script
# =============================================================================
# This script runs before the main process (Gunicorn) starts.
# It handles:
#   1. Waiting for PostgreSQL to be ready
#   2. Running database migrations
#   3. Collecting static files
#   4. Creating default tiers / data
#   5. Starting the main process
# =============================================================================

set -e

# Color output helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
POSTGRES_HOST=${POSTGRES_HOST:-db}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_USER=${POSTGRES_USER:-digiland}
POSTGRES_DB=${POSTGRES_DB:-digiland}
MAX_WAIT_SECONDS=${DB_WAIT_TIMEOUT:-60}

# ---------------------------------------------------------------------------
# Step 1: Wait for PostgreSQL
# ---------------------------------------------------------------------------
log_info "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."

waited=0
until pg_isready \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    -q; do
    if [ $waited -ge $MAX_WAIT_SECONDS ]; then
        log_error "PostgreSQL is still not available after ${MAX_WAIT_SECONDS}s. Aborting."
        exit 1
    fi
    sleep 1
    waited=$((waited + 1))
done
log_ok "PostgreSQL is ready (${waited}s)"

# ---------------------------------------------------------------------------
# Step 2: Run Database Migrations
# ---------------------------------------------------------------------------
log_info "Running database migrations..."
python manage.py migrate --noinput
log_ok "Migrations completed"

# ---------------------------------------------------------------------------
# Step 3: Create Default Superuser (if env vars are set)
# ---------------------------------------------------------------------------
if [ -n "${DJANGO_SUPERUSER_EMAIL}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    log_info "Checking if superuser exists..."
    # SECURITY: Use Django management command instead of shell -c to prevent injection
    python manage.py shell -c "
import os
from core.models import User
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
if email and password and not User.objects.filter(email=email).exists():
    User.objects.create_superuser(
        email=email,
        password=password,
        role='Admin',
        id_number='00000000',
        phone_number='+254700000000',
        kra_pin='A000000000A'
    )
    print('Superuser created.')
else:
    print('Superuser already exists or credentials not provided.')
" 2>/dev/null || log_warn "Could not create superuser (may already exist or missing required fields)"
fi

# ---------------------------------------------------------------------------
# Step 4: Create Default Tiers / Seed Data
# ---------------------------------------------------------------------------
log_info "Creating default tiers and seed data..."
python manage.py shell -c "
from core.models import PlatformLegalDocument

# Create default legal documents if they don't exist
defaults = [
    ('Terms of Service', 'Digiland Terms of Service — please replace with actual content.'),
    ('Privacy Policy', 'Digiland Privacy Policy — please replace with actual content.'),
    ('Joint Purchase Agreement', 'Joint Purchase Agreement — please replace with actual content.'),
    ('Escrow Terms', 'Escrow Service Terms — please replace with actual content.'),
]

for title, content in defaults:
    obj, created = PlatformLegalDocument.objects.get_or_create(
        title=title,
        defaults={'content': content}
    )
    if created:
        print(f'  Created: {title}')
    else:
        print(f'  Exists: {title}')
" 2>/dev/null || log_warn "Could not create default legal documents"

# Create default site domain
python manage.py shell -c "
from django.contrib.sites.models import Site
site = Site.objects.get_current()
domain = '${DOMAIN:-localhost}'
if site.domain != domain:
    site.domain = domain
    site.name = 'Digiland'
    site.save()
    print(f'Site updated: {site.domain}')
else:
    print(f'Site already configured: {site.domain}')
" 2>/dev/null || log_warn "Could not update site domain"

# ---------------------------------------------------------------------------
# Step 5: Collect Static Files
# ---------------------------------------------------------------------------
if [ "${COLLECTSTATIC:-true}" = "true" ]; then
    log_info "Collecting static files..."
    python manage.py collectstatic --noinput 2>/dev/null || log_warn "collectstatic failed (may already be collected)"
    log_ok "Static files collected"
else
    log_info "Skipping collectstatic (COLLECTSTATIC=false)"
fi

# ---------------------------------------------------------------------------
# Step 6: Display Environment Info
# ---------------------------------------------------------------------------
log_info "========================================="
log_info "  Digiland Starting"
log_info "  Host: ${GUNICORN_BIND:-0.0.0.0:8000}"
log_info "  Workers: ${GUNICORN_WORKERS:-auto}"
log_info "  Debug: ${DEBUG:-False}"
log_info "========================================="

# ---------------------------------------------------------------------------
# Step 7: Execute Main Process
# ---------------------------------------------------------------------------
log_info "Starting: $@"
exec "$@"
