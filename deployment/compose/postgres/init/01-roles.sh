#!/bin/sh
# Creates the catalog's own role and database.
#
# The catalog does not connect as the cluster superuser: Polaris gets a role of
# its own and a database it owns, so a credential handed to the catalog cannot
# touch anything else. The password arrives as a file at /run/secrets, per
# ADR-0028, and is re-materialised for this user by the entrypoint beside this
# directory.
set -eu

polaris_password="$(cat /tmp/polaris_db_password)"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c \
  "CREATE ROLE polaris LOGIN PASSWORD '$polaris_password';"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c \
  "CREATE DATABASE polaris OWNER polaris;"
