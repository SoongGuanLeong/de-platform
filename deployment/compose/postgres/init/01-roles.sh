#!/bin/sh
# Creates the application principal named in docs/governance-and-data-quality.md.
# Its password arrives as a file at /run/secrets, per ADR-0028.
set -eu

# The compose secret mount is readable by container root only, and podman-compose
# ignores a secret's mode and owner, so the entrypoint re-materialises this file
# with postgres ownership before the init scripts run as postgres.
svc_password="$(cat /tmp/postgres_svc_password)"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c \
  "CREATE ROLE svc_platform LOGIN PASSWORD '${svc_password}';"
