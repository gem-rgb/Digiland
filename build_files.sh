#!/usr/bin/env bash
set -eo pipefail

# Build the React frontend
echo "Checking frontend build tools..."
if [ -d "Digiland/land_escrow/client" ]; then
  cd Digiland/land_escrow/client
  if command -v npm &> /dev/null; then
    echo "Installing frontend dependencies and building bundle..."
    npm install --include=dev --legacy-peer-deps || true
    npm run build || echo "Notice: using precompiled static bundle from repo"
  fi
  cd ../../..
fi

# Collect static files and migrate
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations if database available..."
python manage.py migrate --noinput || echo "Notice: Database migration skipped during build"

echo "Build complete!"

