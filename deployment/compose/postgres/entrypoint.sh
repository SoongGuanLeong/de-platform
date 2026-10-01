#!/bin/sh
# PostgreSQL entrypoint for the platform's profiles.
#
# One job before the server starts: re-materialise the catalog's metastore
# password with postgres ownership. A bind mount under rootless podman presents
# the file as owned by container root, and the init scripts run as the postgres
# user, so the file has to be re-materialised with an owner they can read. This
# is the same rootless cost deployment/scripts/fix-secret-ownership.sh records,
# paid here in the entrypoint instead because PostgreSQL can read it as root
# before it drops privileges.
set -eu

install -m 600 -o postgres -g postgres /run/secrets/polaris_db_password /tmp/polaris_db_password

exec docker-entrypoint.sh postgres
