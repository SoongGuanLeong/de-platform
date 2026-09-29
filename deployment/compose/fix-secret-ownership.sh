#!/bin/sh
# Maps the host ownership of a secret or key to the uid a container runs as.
#
# Why this exists: the compose secret mechanism mounts a file with the host's
# mode and owner, and podman-compose ignores a secret's mode, uid and gid
# fields. Under rootless podman a bind mount therefore presents the file as
# owned by container root, so a container running as a non-root user cannot read
# its own secret. podman unshare chown maps the host owner to the container uid,
# which is the rootless equivalent of chowning the file for the container.
#
# This is a real cost of the file-based secret mechanism and is recorded as such
# in docs/security-model.md. A service that can run its entrypoint as root avoids
# it by re-materialising the file with the right owner, which is what the
# PostgreSQL and ClickHouse services here do instead.
set -eu

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo_root"

map_owner() {
  uid="$1"; gid="$2"; path="$3"
  [ -e "$path" ] || { printf 'missing %s\n' "$path"; return 0; }
  podman unshare chown "$uid:$gid" "$path"
  printf 'mapped %s to %s:%s\n' "$path" "$uid" "$gid"
}

# Kafka runs as appuser, uid 1000, gid 1000.
map_owner 1000 1000 runtime/secrets/kafka_admin_password
map_owner 1000 1000 runtime/secrets/kafka_svc_password
map_owner 1000 1000 runtime/certs/kafka.key

# Grafana runs as uid 472, gid 0.
map_owner 472 0 runtime/secrets/grafana_admin_password
map_owner 472 0 runtime/certs/grafana.key

# Polaris runs as uid 10000, gid 10001.
map_owner 10000 10001 runtime/secrets/polaris_bootstrap_secret
map_owner 10000 10001 runtime/secrets/polaris_client_secret
