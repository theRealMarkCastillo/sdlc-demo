#!/bin/sh
set -e

# Run database migrations
echo "Running Alembic migrations..."
alembic upgrade head

# Start the application
echo "Starting Flask app..."
exec python app.py
