#!/bin/bash
# Apply database migration

echo "Applying database migration..."

docker-compose exec -T db psql -U postgres -d secret_santa < sql/migrations/001_add_user_profile_fields.sql

if [ $? -eq 0 ]; then
    echo "✅ Migration applied successfully!"
else
    echo "❌ Migration failed!"
    exit 1
fi
