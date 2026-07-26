#!/bin/sh
set -e

# Run database migrations. If the DB isn't ready yet, retry a few times
# before giving up. On success, the schema is guaranteed current.
MIGRATION_OK=0
for i in $(seq 1 5); do
    if alembic upgrade head; then
        echo "Migrations applied successfully"
        MIGRATION_OK=1
        break
    fi
    echo "Migration attempt $i failed, retrying in 2s..." >&2
    sleep 2
done

if [ "$MIGRATION_OK" -ne 1 ]; then
    echo "ERROR: database migrations failed after 5 attempts — refusing to start app with stale schema" >&2
    exit 1
fi

# Start the application
echo "Starting Flask app..."
exec python app.py
