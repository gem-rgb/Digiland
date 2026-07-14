#!/usr/bin/env bash
set -euo pipefail

# Build the React frontend
echo "Installing frontend dependencies and building..."
cd Digiland/land_escrow/client
npm install
npm run build
cd ../../..

# Collect static files and migrate
echo "Collecting static files..."
python manage.py collectstatic --noinput
python manage.py migrate --noinput
