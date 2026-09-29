#!/bin/sh
# Security evidence: SeaweedFS S3.
#
# Proves the deferred item "TLS refused when plaintext: SeaweedFS S3" from
# docs/security-evidence-plan.md:
#   - POSITIVE: a client that trusts the harness CA reaches the S3 endpoint,
#     so the refusal below cannot be blamed on a dead service
#   - NEGATIVE: a plaintext client pointed at the TLS port is refused, with both
#     a non-zero exit and the server's own refusal message
#   - SERVER-SIDE: the SeaweedFS log records the same refusal as a TLS handshake
#     error, because a client-side error alone does not show why the request
#     failed
#
# A refusal assertion requires BOTH a non-zero exit AND the expected refusal
# message, so a container that is simply down cannot be mistaken for a control
# that refused.
set -u

CTR=de-platform-security-seaweedfs
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
CA="$REPO/runtime/certs/ca.crt"
ACCESS_KEY=deplatform
PORT=58333
failures=0

assert_ok() {
  desc="$1"; shift
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ]; then
    printf 'PASS  %s\n' "$desc"
  else
    printf 'FAIL  %s\n      exit=%s output=%s\n' "$desc" "$rc" "$(printf '%s' "$out" | head -3 | tr '\n' ' ')"
    failures=$((failures + 1))
  fi
}

assert_refused() {
  desc="$1"; pattern="$2"; shift 2
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && printf '%s' "$out" | grep -Eq "$pattern"; then
    printf 'PASS  %s\n      refused with: %s\n' "$desc" "$(printf '%s' "$out" | grep -Eo "$pattern" | head -1)"
  else
    printf 'FAIL  %s\n      expected refusal matching /%s/, exit=%s output=%s\n' "$desc" "$pattern" "$rc" "$(printf '%s' "$out" | head -3 | tr '\n' ' ')"
    failures=$((failures + 1))
  fi
}

assert_eq() {
  desc="$1"; expected="$2"; actual="$3"
  if [ "$actual" = "$expected" ]; then
    printf 'PASS  %s\n' "$desc"
  else
    printf 'FAIL  %s\n      expected=%s actual=%s\n' "$desc" "$expected" "$actual"
    failures=$((failures + 1))
  fi
}

assert_absent() {
  desc="$1"; shift
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ]; then
    printf 'PASS  %s\n' "$desc"
  else
    printf 'FAIL  %s\n      expected nothing, but found: %s\n' "$desc" "$(printf '%s' "$out" | head -3 | tr '\n' ' ')"
    failures=$((failures + 1))
  fi
}

# Requires curl's exit 7 (CURLE_COULDNT_CONNECT) AND a connect-failure message,
# so a port that is open and answers 400 or 403 cannot satisfy it. curl 8.18 in
# this image words a refused connection "Could not connect to server" rather
# than "Connection refused", so both wordings are accepted.
assert_unreachable() {
  desc="$1"; shift
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -eq 7 ] && printf '%s' "$out" | grep -Eq 'Failed to connect|Connection refused|Could not connect'; then
    printf 'PASS  %s\n      not reachable: %s\n' "$desc" "$(printf '%s' "$out" | grep -Eo 'Failed to connect[^,]*|Connection refused|Could not connect to server' | head -1)"
  else
    printf 'FAIL  %s\n      expected a connection failure (curl exit 7), exit=%s output=%s\n' "$desc" "$rc" "$(printf '%s' "$out" | head -3 | tr '\n' ' ')"
    failures=$((failures + 1))
  fi
}

echo "== precondition: the service is running =="
if ! podman exec "$CTR" true >/dev/null 2>&1; then
  echo "FAIL  the container $CTR is not running; no assertion below is meaningful"
  exit 1
fi
echo "PASS  the container $CTR is running"

# Read the secret inside the container, not from runtime/secrets: the harness
# maps such files to the container's user, which can leave them unreadable from
# the host. Reading it in the container is also the assertion that it arrived as
# a file at /run/secrets.
secret="$(podman exec "$CTR" cat /run/secrets/seaweedfs_s3_secret_key)"

echo
echo "== positive control: a client that trusts the CA reaches the S3 endpoint =="
assert_ok "the server presents a certificate that verifies against the harness CA" \
  sh -c "openssl s_client -connect 127.0.0.1:$PORT -servername localhost -CAfile '$CA' </dev/null 2>/dev/null | grep -q 'Verify return code: 0 (ok)'"
assert_eq "an S3 client that trusts the CA and signs with the configured key is accepted" 200 \
  "$(curl -sS --max-time 15 --cacert "$CA" --aws-sigv4 'aws:amz:us-east-1:s3' -u "$ACCESS_KEY:$secret" -o /dev/null -w '%{http_code}' "https://127.0.0.1:$PORT/" 2>/dev/null)"
assert_eq "an unsigned request over TLS reaches the S3 API and is refused by authentication, not transport" 403 \
  "$(curl -sS --max-time 15 --cacert "$CA" -o /dev/null -w '%{http_code}' "https://127.0.0.1:$PORT/" 2>/dev/null)"

echo
echo "== negative: a plaintext client pointed at the TLS port is refused =="
# The TLS listener answers a plaintext HTTP request with a plaintext HTTP 400
# whose body names the cause, so --fail-with-body yields both a non-zero exit
# and the server's own message.
log_before="$(podman logs "$CTR" 2>&1 | wc -l)"
assert_refused "a plaintext HTTP client is refused" \
  'Client sent an HTTP request to an HTTPS server' \
  sh -c "curl -sS --fail-with-body --max-time 15 http://127.0.0.1:$PORT/"
# The 400 body is server-authored, but the server's own log is the independent
# confirmation that the refusal happened at the TLS layer rather than inside the
# S3 API. Only lines after the marker count, so an earlier run cannot satisfy it.
log_ok=0
for _ in 1 2 3 4 5; do
  if podman logs "$CTR" 2>&1 | tail -n +$((log_before + 1)) | grep -q 'TLS handshake error.*client sent an HTTP request to an HTTPS server'; then
    log_ok=1
    break
  fi
  sleep 1
done
assert_eq "the server records that refusal as a TLS handshake error" 1 "$log_ok"

echo
echo "== no other plaintext surface: Iceberg REST catalog, Lance and WebDAV are closed =="
# weed mini starts a plaintext Iceberg REST catalog on 8181, a plaintext Lance
# namespace server on 9101 and WebDAV on 7333 by default. None is published to
# the host, so the probes run inside the container; from the host they would
# prove nothing. The first assertion is the control for the probe mechanism
# itself: against the open S3 port the same probe gets a server-authored 400, so
# a connection refusal below is the port being closed rather than the probe
# being broken.
assert_refused "the in-container probe reaches the open S3 port (server-authored 400)" \
  'Client sent an HTTP request to an HTTPS server' \
  podman exec "$CTR" curl -sS --fail-with-body --max-time 5 http://127.0.0.1:8333/
assert_unreachable "the Iceberg REST catalog port 8181 is closed" \
  podman exec "$CTR" curl -sS --max-time 5 http://127.0.0.1:8181/v1/config
assert_unreachable "the Lance namespace port 9101 is closed" \
  podman exec "$CTR" curl -sS --max-time 5 http://127.0.0.1:9101/
assert_unreachable "the WebDAV port 7333 is closed" \
  podman exec "$CTR" curl -sS --max-time 5 http://127.0.0.1:7333/
# Independent of curl: no socket is listening on those ports at all.
assert_absent "no listener exists on 8181, 9101 or 7333" \
  sh -c "podman exec $CTR sh -c 'netstat -ltn 2>/dev/null || ss -ltn' | grep -Eq ':(8181|9101|7333)[[:space:]]'"

echo
if [ "$failures" -eq 0 ]; then
  echo "RESULT: all SeaweedFS S3 assertions passed"
else
  echo "RESULT: $failures assertion(s) failed"
fi
exit "$failures"
