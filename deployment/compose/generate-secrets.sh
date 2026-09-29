#!/bin/sh
# Generates the local secret values used by the security evidence harness.
#
# Every value is written under runtime/secrets/, which is gitignored, and never
# outside it (ADR-0028). An existing value is never overwritten, so a re-run
# cannot silently invalidate evidence that cited it.
set -eu

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
secrets_dir="$repo_root/runtime/secrets"

mkdir -p "$secrets_dir"
chmod 700 "$secrets_dir"

for name in postgres_superuser_password postgres_svc_password clickhouse_default_password clickhouse_svc_password kafka_svc_password grafana_admin_password seaweedfs_s3_secret_key; do
  path="$secrets_dir/$name"
  if [ -f "$path" ]; then
    printf 'kept    %s\n' "$path"
  else
    openssl rand -hex 24 > "$path"
    chmod 600 "$path"
    printf 'created %s\n' "$path"
  fi
done

printf '\nSecrets live only under runtime/, which is gitignored.\n'
