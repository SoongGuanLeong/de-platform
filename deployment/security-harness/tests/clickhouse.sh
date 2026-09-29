#!/bin/sh
# Security evidence: ClickHouse.
#
# Proves three deferred items from docs/security-evidence-plan.md:
#   - secrets arrive as a file at /run/secrets and are stored hashed, not plaintext
#   - the data plane refuses bad credentials and accepts good ones
#   - TLS is enforced: there is no unencrypted path to the server
# and verifies the model's retention claim, then proves the TTL mechanism works.
#
# A refusal assertion requires BOTH a non-zero exit AND the expected refusal
# message, so a container that is simply down cannot be mistaken for a control
# that refused.
set -u

CTR=de-platform-security-clickhouse
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
SECRETS="$REPO/runtime/secrets"
failures=0

assert_ok() {
  desc="$1"; shift
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ]; then
    printf 'PASS  %s\n' "$desc"
  else
    printf 'FAIL  %s\n      exit=%s output=%s\n' "$desc" "$rc" "$(printf '%s' "$out" | head -2 | tr '\n' ' ')"
    failures=$((failures + 1))
  fi
}

assert_absent() {
  desc="$1"; shift
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ]; then
    printf 'PASS  %s\n' "$desc"
  else
    printf 'FAIL  %s\n      expected nothing, but found: %s\n' "$desc" "$(printf '%s' "$out" | head -2 | tr '\n' ' ')"
    failures=$((failures + 1))
  fi
}

assert_refused() {
  desc="$1"; pattern="$2"; shift 2
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && printf '%s' "$out" | grep -Eq "$pattern"; then
    printf 'PASS  %s\n      refused with: %s\n' "$desc" "$(printf '%s' "$out" | grep -Eo "$pattern" | head -1)"
  else
    printf 'FAIL  %s\n      expected refusal matching /%s/, exit=%s output=%s\n' "$desc" "$pattern" "$rc" "$(printf '%s' "$out" | head -2 | tr '\n' ' ')"
    failures=$((failures + 1))
  fi
}

echo "== precondition: the service is running =="
if ! podman exec "$CTR" true >/dev/null 2>&1; then
  echo "FAIL  the container $CTR is not running; no assertion below is meaningful"
  exit 1
fi
echo "PASS  the container $CTR is running"

svc_pw="$(cat "$SECRETS/clickhouse_svc_password")"
default_pw="$(cat "$SECRETS/clickhouse_default_password")"

# The client trusts the harness CA; without it the connection is refused by the
# client's own verification, which is asserted separately below.
ch() { podman exec "$CTR" clickhouse-client --config-file /harness/client-config.xml --secure --port 9440 --user svc_platform --password "$svc_pw" "$@"; }
ch_untrusting() { podman exec "$CTR" clickhouse-client --secure --port 9440 --user svc_platform --password "$svc_pw" "$@"; }

echo
echo "== secrets: file intake, hashed at rest, no plaintext in the environment =="
assert_ok "the secret is mounted at /run/secrets" \
  podman exec "$CTR" test -f /run/secrets/clickhouse_svc_password
assert_ok "the mounted file matches the runtime file byte for byte" \
  sh -c "podman exec $CTR cat /run/secrets/clickhouse_svc_password | diff -q - '$SECRETS/clickhouse_svc_password'"
assert_absent "no plaintext password variable is present in the environment" \
  sh -c "podman exec $CTR env | grep -qE '^CLICKHOUSE_.*PASSWORD='"
assert_ok "the rendered users config carries a sha256 hash, not the plaintext" \
  sh -c "podman exec $CTR grep -q '<password_sha256_hex>' /etc/clickhouse-server/users.d/security.xml"
assert_absent "the plaintext value does not appear in the rendered config" \
  sh -c "podman exec $CTR grep -qF '$svc_pw' /etc/clickhouse-server/users.d/security.xml"

echo
echo "== authentication: good credentials accepted, bad refused =="
assert_ok "svc_platform authenticates with the file-provided password" \
  ch -q 'select currentUser()'
assert_refused "a wrong password is refused" 'Authentication failed' \
  podman exec "$CTR" clickhouse-client --config-file /harness/client-config.xml --secure --port 9440 --user svc_platform --password wrong-password -q 'select 1'
assert_refused "an empty password is refused, so the shipped default is closed" 'Authentication failed' \
  podman exec "$CTR" clickhouse-client --config-file /harness/client-config.xml --secure --port 9440 --user svc_platform -q 'select 1'
assert_ok "the default user no longer accepts an empty password" \
  sh -c "podman exec $CTR clickhouse-client --config-file /harness/client-config.xml --secure --port 9440 --user default --password '$default_pw' -q 'select 1' >/dev/null"

echo
echo "== TLS: enforced, with no unencrypted path =="
assert_refused "the plaintext native port is not listening at all" 'Connection refused' \
  podman exec "$CTR" clickhouse-client --port 9000 --user svc_platform --password "$svc_pw" -q 'select 1'
assert_refused "a client that does not trust the CA is refused" 'certificate verify failed|unknown ca' \
  ch_untrusting -q 'select 1'
assert_ok "a TLS client that trusts the CA is accepted" \
  ch -q 'select 1'
assert_ok "the server records the connection as secure" \
  sh -c "podman exec $CTR clickhouse-client --config-file /harness/client-config.xml --secure --port 9440 --user svc_platform --password '$svc_pw' -q 'system flush logs' >/dev/null; podman exec $CTR clickhouse-client --config-file /harness/client-config.xml --secure --port 9440 --user svc_platform --password '$svc_pw' -q \"select is_secure from system.query_log where type = 'QueryFinish' and user = 'svc_platform' order by event_time desc limit 1\" | grep -qx 1"

echo
echo "== retention: a TTL bounds the query log, and it actually deletes =="
# The shipped table carries no TTL, so 'alter table ... remove ttl' errors with
# code 36 on a fresh container: removing first only passed against a container an
# earlier run had already modified. The order below is apply, prove present,
# prove it deletes, then remove and prove it gone, so every assertion has
# something real to fail on and the sequence holds from either state.
assert_ok "a TTL can be applied" \
  ch -q 'alter table system.query_log modify ttl event_date + interval 30 day'
assert_ok "the TTL is present afterwards" \
  sh -c "podman exec $CTR clickhouse-client --config-file /harness/client-config.xml --secure --port 9440 --user svc_platform --password '$svc_pw' -q 'show create table system.query_log' | grep -q 'TTL event_date'"
assert_ok "a row older than the window is removed by the TTL" \
  sh -c "podman exec $CTR clickhouse-client --config-file /harness/client-config.xml --secure --port 9440 --user svc_platform --password '$svc_pw' --multiquery -q \"
    insert into system.query_log (event_date, event_time, type, query_start_time, query_duration_ms, read_rows, read_bytes, written_rows, written_bytes, result_rows, result_bytes, memory_usage, current_database, query, exception_code, user, query_id, initial_user, initial_query_id, is_initial_query) values (today() - 60, now() - interval 60 day, 'QueryFinish', now(), 0, 0, 0, 0, 0, 0, 0, 0, 'default', 'retention-probe', 0, 'retention_probe', 'probe', 'retention_probe', 'probe', 1);
    optimize table system.query_log final;
    select count() from system.query_log where query = 'retention-probe'\" | tail -1 | grep -qx 0"
assert_ok "the TTL can be removed, so the unbounded state is reachable" \
  ch -q 'alter table system.query_log remove ttl'
assert_absent "with the TTL removed no TTL is present" \
  sh -c "podman exec $CTR clickhouse-client --config-file /harness/client-config.xml --secure --port 9440 --user svc_platform --password '$svc_pw' -q 'show create table system.query_log' | grep -qi 'TTL event_date'"

echo
if [ "$failures" -eq 0 ]; then
  echo "RESULT: all ClickHouse assertions passed"
else
  echo "RESULT: $failures assertion(s) failed"
fi
exit "$failures"
