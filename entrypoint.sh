#!/bin/sh
set -e

# Run database migrations. If the DB isn't ready yet, retry a few times
# before giving up. On success, the schema is guaranteed current.
for i in $(seq 1 5); do
    if alembic upgrade head; then
        echo "Migrations applied successfully"
        break
    fi
    echo "Migration attempt $i failed, retrying in 2s..." >&2
    sleep 2
done

# Start the application
echo "Starting Flask app..."
exec python app.py
