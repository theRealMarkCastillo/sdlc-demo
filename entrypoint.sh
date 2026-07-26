#!/bin/sh
set -e

# Run database migrations (skip if alembic fails gracefully in fresh DB)
alembic upgrade head 2>/dev/null || echo "Alembic migration skipped (fresh DB or config issue)"

# Start the application
echo "Starting Flask app..."
exec python app.py
