#!/usr/bin/env bash
#
# Generates the local secret values the platform's compose profiles mount.
#
# Every value is written under runtime/secrets/, which is gitignored, and never
# outside it (ADR-0028). An existing value is never overwritten, so a re-run
# cannot silently invalidate evidence that cited it, and re-running the
# documented smoke command is idempotent.
#
# The list is exactly what deployment/compose/*.yml mounts. A secret that no
# compose file mounts is not generated here: the security evidence harness has
# its own generator for its own wider set, and the two are deliberately separate
# so neither silently provisions for the other.
set -euo pipefail

# So a secret is never briefly group- or world-readable between the write and the
# chmod below.
umask 077

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
secrets_dir="${repo_root}/runtime/secrets"

mkdir -p "${secrets_dir}"
chmod 700 "${secrets_dir}"

for name in postgres_superuser_password polaris_db_password polaris_bootstrap_secret grafana_admin_password seaweedfs_s3_secret_key; do
  path="${secrets_dir}/${name}"
  if [ -f "${path}" ]; then
    printf 'kept    %s\n' "${path}"
  else
    openssl rand -hex 24 > "${path}"
    chmod 600 "${path}"
    printf 'created %s\n' "${path}"
  fi
done

printf '\nSecrets live only under runtime/, which is gitignored.\n'
