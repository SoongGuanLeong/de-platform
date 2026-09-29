#!/bin/sh
# ClickHouse entrypoint for the security evidence harness.
#
# Two jobs before the server starts, both because of how secrets reach a
# container:
#   1. The compose secret mount is readable by container root only, and
#      podman-compose ignores a secret's mode and owner, so the TLS key is
#      re-materialised with clickhouse ownership.
#   2. ClickHouse has no file intake for a password: users.d takes a literal or
#      from_env, so the hashes are rendered from the mounted files here. This is
#      the same entrypoint exception the model records for Flink's keystore
#      password, and it is evidence that the exception is wider than Flink.
set -eu

mkdir -p /etc/clickhouse-server/certs /etc/clickhouse-server/users.d

install -m 640 -o clickhouse -g clickhouse /certs/clickhouse.key /etc/clickhouse-server/certs/clickhouse.key
install -m 644 -o clickhouse -g clickhouse /certs/clickhouse.crt /etc/clickhouse-server/certs/clickhouse.crt
install -m 644 -o clickhouse -g clickhouse /certs/ca.crt /etc/clickhouse-server/certs/ca.crt

hash_of() { printf '%s' "$1" | sha256sum | cut -d' ' -f1; }

default_hash="$(hash_of "$(cat /run/secrets/clickhouse_default_password)")"
svc_hash="$(hash_of "$(cat /run/secrets/clickhouse_svc_password)")"

# The shipped default user has an empty password. It is closed here rather than
# left as shipped, which is what docs/security-model.md section 5 claims.
cat > /etc/clickhouse-server/users.d/security.xml <<XML
<clickhouse>
  <users>
    <default>
      <!-- The image ships an empty plaintext password for default. It is
           removed rather than added to, because ClickHouse refuses two
           authentication methods on one user. -->
      <password remove="1"/>
      <password_sha256_hex>${default_hash}</password_sha256_hex>
      <networks><ip>::/0</ip></networks>
    </default>
    <svc_platform>
      <password_sha256_hex>${svc_hash}</password_sha256_hex>
      <networks><ip>::/0</ip></networks>
      <profile>default</profile>
      <quota>default</quota>
    </svc_platform>
  </users>
</clickhouse>
XML

exec /entrypoint.sh "$@"
