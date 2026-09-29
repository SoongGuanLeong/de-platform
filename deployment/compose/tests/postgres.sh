#!/bin/sh
# Security evidence: PostgreSQL.
#
# Proves three deferred items from docs/security-evidence-plan.md:
#   - secrets arrive as a file at /run/secrets, not as an environment value
#   - the data plane refuses bad credentials and accepts good ones
#   - TLS is enforced, so a plaintext client is refused rather than unprotected
#
# A refusal assertion requires BOTH a non-zero exit AND the expected refusal
# message, so a container that is simply down cannot be mistaken for a control
# that refused. Every assertion prints PASS or FAIL with the observed output.
set -u

CTR=de-platform-security-postgres
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
  # For a check whose success condition is finding nothing.
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

super_pw="$(cat "$SECRETS/postgres_superuser_password")"
svc_pw="$(cat "$SECRETS/postgres_svc_password")"

echo
echo "== secrets: the value arrives as a file, not an environment value =="
assert_ok "the secret is mounted at /run/secrets" \
  podman exec "$CTR" test -f /run/secrets/postgres_superuser_password
assert_ok "the mounted file matches the runtime file byte for byte" \
  sh -c "podman exec $CTR cat /run/secrets/postgres_superuser_password | diff -q - '$SECRETS/postgres_superuser_password'"
assert_absent "no plaintext password variable is present in the environment" \
  sh -c "podman exec $CTR env | grep -q '^POSTGRES_PASSWORD='"
assert_ok "the file-intake variable is present instead" \
  sh -c "podman exec $CTR env | grep -q '^POSTGRES_PASSWORD_FILE=/run/secrets/'"

echo
echo "== authentication: good credentials accepted, bad refused =="
assert_ok "the superuser authenticates with the file-provided password" \
  podman exec -e PGPASSWORD="$super_pw" "$CTR" psql -h 127.0.0.1 -U deplatform -d deplatform -tAc 'select 1'
assert_refused "a wrong password is refused" 'password authentication failed' \
  podman exec -e PGPASSWORD="not-the-password" "$CTR" psql -h 127.0.0.1 -U deplatform -d deplatform -tAc 'select 1'
assert_ok "the application principal authenticates with its own file-provided password" \
  sh -c "podman exec -e PGPASSWORD='$svc_pw' $CTR psql -h 127.0.0.1 -U svc_platform -d deplatform -tAc 'select current_user' | grep -qx svc_platform"

echo
echo "== TLS: enforced, not merely available =="
assert_ok "SHOW ssl reports on" \
  sh -c "podman exec -e PGPASSWORD='$super_pw' $CTR psql -h 127.0.0.1 -U deplatform -d deplatform -tAc 'show ssl' | grep -qx on"
assert_refused "a plaintext client is refused" 'pg_hba.conf rejects connection|no encryption|SSL off' \
  podman exec -e PGPASSWORD="$super_pw" "$CTR" psql "host=127.0.0.1 user=deplatform dbname=deplatform sslmode=disable" -tAc 'select 1'
assert_ok "a TLS client is accepted" \
  podman exec -e PGPASSWORD="$super_pw" "$CTR" psql "host=127.0.0.1 user=deplatform dbname=deplatform sslmode=require" -tAc 'select 1'

echo
if [ "$failures" -eq 0 ]; then
  echo "RESULT: all PostgreSQL assertions passed"
else
  echo "RESULT: $failures assertion(s) failed"
fi
exit "$failures"
