#!/bin/sh
# Maps the host ownership of the Polaris profile's secret files to the uid the
# Polaris container runs as.
#
# Why this exists: podman-compose ignores a compose secret's mode, uid and gid,
# so under rootless podman a bind mount presents the file as owned by container
# root. Polaris runs as the image's non-root user (polaris, uid 10000, gid
# 10001), so without this it cannot read its own secrets. This is the same
# mapping deployment/compose/fix-secret-ownership.sh applies to the two Polaris
# secrets; this profile-local script adds the metastore password and is safe to
# run repeatedly.
#
# The mapping makes the files unreadable from the host, which is why
# tests/polaris.sh reads the bootstrap secret from inside the container.
set -eu

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$repo_root"

map_owner() {
  uid="$1"; gid="$2"; path="$3"
  [ -e "$path" ] || { printf 'missing %s\n' "$path"; return 0; }
  podman unshare chown "$uid:$gid" "$path"
  printf 'mapped %s to %s:%s\n' "$path" "$uid" "$gid"
}

map_owner 10000 10001 runtime/secrets/polaris_db_password
map_owner 10000 10001 runtime/secrets/polaris_bootstrap_secret
map_owner 10000 10001 runtime/secrets/polaris_client_secret
