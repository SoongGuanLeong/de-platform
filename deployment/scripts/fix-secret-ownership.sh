#!/usr/bin/env bash
#
# Maps the host ownership of a secret file to the uid the container that reads
# it runs as.
#
# Why this exists: a bind mount under rootless podman presents the file as owned
# by container root, so a container running as a non-root user cannot read its
# own secret. podman unshare chown maps the host owner to the container uid,
# which is the rootless equivalent of chowning the file for the container. This
# is a real cost of the file-based secret mechanism, recorded in
# docs/security-model.md section 2.4, and it is why deployment/smoke provisions
# before it preflights.
#
# The mapping makes the file unreadable from the host, so a check that needs the
# value reads it from inside the container. Safe to run repeatedly.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${repo_root}"

map_owner() {
  uid="$1"; gid="$2"; path="$3"
  [ -e "${path}" ] || { printf 'missing %s\n' "${path}"; return 0; }
  podman unshare chown "${uid}:${gid}" "${path}"
  printf 'mapped  %s to %s:%s\n' "${path}" "${uid}" "${gid}"
}

# Polaris runs as uid 10000, gid 10001.
map_owner 10000 10001 runtime/secrets/polaris_db_password
map_owner 10000 10001 runtime/secrets/polaris_bootstrap_secret

# Grafana runs as uid 472, gid 0.
map_owner 472 0 runtime/secrets/grafana_admin_password

# postgres_superuser_password and seaweedfs_s3_secret_key are deliberately
# absent: the PostgreSQL image's entrypoint reads POSTGRES_PASSWORD_FILE as root
# before it drops privileges, and the SeaweedFS entrypoint reads the S3 key as
# root and renders /tmp/s3-config.json, which it then chowns to the seaweed user.
# A service that can read its secret as root avoids this step entirely, which is
# the pattern the harness also uses.
