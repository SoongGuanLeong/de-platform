#!/bin/sh
# Security evidence: Grafana TLS chain.
#
# Proves the deferred item "TLS chain verifiable: Grafana" from
# docs/security-evidence-plan.md, which is the Grafana row of the TLS matrix in
# docs/security-model.md section 4.1. The model makes two claims about that
# listener and this script asserts both, plus a third that stops the positive
# result from being an accident:
#
#   1. POSITIVE  the served chain verifies against the local CA, and terminates
#                at it: openssl s_client with -CAfile runtime/certs/ca.crt and
#                -verify_return_error exits 0 and reports "Verify return code: 0
#                (ok)", and the served leaf's issuer is the local CA's subject.
#   2. NEGATIVE  a client that does not trust the local CA is refused: the same
#                handshake against the system trust store exits non-zero and
#                reports a verification error. This is the model's "an untrusted
#                chain is rejected".
#   3. NEGATIVE  the local CA is load-bearing, not incidental: passing a
#                different trust store (the system bundle) fails, and the system
#                bundle is shown to be non-empty, so the refusal in 2 cannot be
#                an empty-trust-store artifact. -verify_return_error is what
#                makes a verification failure a non-zero exit rather than a line
#                printed under an exit of 0, which is exactly the silent success
#                this item exists to rule out.
#
# Tooling is openssl only, which is what the model commits to for the TLS
# matrix. No curl, no gnutls, no browser.
#
# A refusal assertion requires BOTH a non-zero exit AND the expected refusal
# message, so a container that is simply down cannot be mistaken for a control
# that refused. The positive assertions are the control that rules out "the
# service is dead" as an explanation for any refusal.
set -u

CTR=de-platform-security-grafana
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
CERTS="$REPO/runtime/certs"
HOST=127.0.0.1
PORT=53000
# The host's system trust store. Grafana's leaf is signed by the harness CA,
# which is deliberately absent from it.
SYS_CA=/etc/ssl/certs/ca-certificates.crt
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

assert_ok_contains() {
  # Success is a zero exit AND the expected line, so a bare exit code cannot
  # stand in for the property being asserted.
  desc="$1"; pattern="$2"; shift 2
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -Eq "$pattern"; then
    printf 'PASS  %s\n      saw: %s\n' "$desc" "$(printf '%s' "$out" | grep -Eo "$pattern" | head -1)"
  else
    printf 'FAIL  %s\n      expected /%s/, exit=%s output=%s\n' "$desc" "$pattern" "$rc" "$(printf '%s' "$out" | head -3 | tr '\n' ' ')"
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
    printf 'FAIL  %s\n      expected refusal matching /%s/, exit=%s output=%s\n' "$desc" "$pattern" "$rc" "$(printf '%s' "$out" | head -3 | tr '\n' ' ')"
    failures=$((failures + 1))
  fi
}

assert_equal() {
  desc="$1"; expected="$2"; actual="$3"
  if [ "$expected" = "$actual" ]; then
    printf 'PASS  %s\n' "$desc"
  else
    printf 'FAIL  %s\n      expected=%s actual=%s\n' "$desc" "$expected" "$actual"
    failures=$((failures + 1))
  fi
}

# sclient_trust <cafile> : the handshake, verified against <cafile>, failing
# non-zero on a verification error.
sclient_trust() {
  openssl s_client -connect "$HOST:$PORT" -CAfile "$1" -verify_return_error -verify 5 </dev/null 2>&1
}

# sclient_system : the handshake verified against the host's default trust
# store, which does not contain the harness CA.
sclient_system() {
  openssl s_client -connect "$HOST:$PORT" -verify_return_error -verify 5 </dev/null 2>&1
}

# served_leaf : print only the first certificate the server presents, so it can
# be read by openssl x509 or openssl verify.
served_leaf() {
  openssl s_client -connect "$HOST:$PORT" -CAfile "$CERTS/ca.crt" -showcerts </dev/null 2>/dev/null \
    | awk '/BEGIN CERTIFICATE/{n++} n==1{print} n==1 && /END CERTIFICATE/{exit}'
}

# served_leaf_san : the subjectAltName extension of the certificate actually
# served over the wire.
served_leaf_san() {
  served_leaf | openssl x509 -noout -ext subjectAltName
}

echo "== precondition: the service is running =="
if ! podman exec "$CTR" true >/dev/null 2>&1; then
  echo "FAIL  the container $CTR is not running; no assertion below is meaningful"
  exit 1
fi
echo "PASS  the container $CTR is running"

# Grafana downloads bundled plugins at startup, so the listener may not be up
# the instant the container is. Wait for it, but a timeout is a FAIL rather
# than a skip.
echo
echo "== precondition: the HTTPS listener answers =="
waited=0
while ! openssl s_client -connect "$HOST:$PORT" -CAfile "$CERTS/ca.crt" -verify_return_error -verify 5 </dev/null >/dev/null 2>&1; do
  waited=$((waited + 1))
  if [ "$waited" -ge 60 ]; then
    echo "FAIL  Grafana did not answer a verifiable HTTPS handshake on $HOST:$PORT within 60s"
    exit 1
  fi
  sleep 1
done
echo "PASS  Grafana answers a verifiable HTTPS handshake on $HOST:$PORT"

echo
echo "== positive: the served chain verifies against the local CA =="
assert_ok "openssl s_client verifies the served chain against runtime/certs/ca.crt" \
  sclient_trust "$CERTS/ca.crt"
assert_ok_contains "the handshake reports Verify return code 0 (ok)" \
  'Verify return code: 0 \(ok\)' sclient_trust "$CERTS/ca.crt"
assert_ok_contains "the handshake negotiated TLS, not a plaintext upgrade" \
  'Cipher is ' sclient_trust "$CERTS/ca.crt"

# The chain terminates at the local CA: the served leaf's issuer DN equals the
# local CA's subject DN, and the served leaf is the Grafana certificate. This is
# read from the live handshake, so it cannot be satisfied by a file on disk.
ca_subject="$(openssl x509 -in "$CERTS/ca.crt" -noout -subject | sed 's/^subject=//')"
leaf_subject="$(served_leaf | openssl x509 -noout -subject | sed 's/^subject=//')"
leaf_issuer="$(served_leaf | openssl x509 -noout -issuer | sed 's/^issuer=//')"
assert_equal "the served leaf's issuer is the local CA (the chain terminates there)" \
  "$ca_subject" "$leaf_issuer"
assert_equal "the served leaf is the Grafana certificate" \
  "CN=grafana" "$leaf_subject"
assert_ok_contains "the served leaf carries a 127.0.0.1 SAN, so an IP-connecting client can verify the hostname" \
  'IP Address:127\.0\.0\.1' served_leaf_san

echo
echo "== negative: a client that does not trust the local CA is refused =="
assert_refused "the handshake against the system trust store is refused" \
  'verify error|certificate verify failed|unable to get local issuer certificate' \
  sclient_system

echo
echo "== negative: the local CA is load-bearing, not incidental =="
# If verification succeeded no matter which CA was supplied, the positive result
# above would prove nothing. So a different CA must fail, and the system store
# must be non-empty, or the failure would just mean there was nothing to trust.
assert_ok "the system trust store is non-empty, so the refusal below is about our CA" \
  sh -c "test -s '$SYS_CA' && [ \"\$(grep -c 'BEGIN CERTIFICATE' '$SYS_CA')\" -gt 10 ]"
assert_refused "the same handshake with the system bundle as -CAfile is refused" \
  'verify error|certificate verify failed|unable to get local issuer certificate' \
  sclient_trust "$SYS_CA"

echo
echo "== secret: the admin password arrives as a file, not an environment value =="
assert_ok "the secret is mounted at /run/secrets/grafana_admin_password" \
  podman exec "$CTR" test -f /run/secrets/grafana_admin_password
assert_ok "the mounted file is readable by the Grafana user and non-empty" \
  podman exec "$CTR" sh -c '[ -s /run/secrets/grafana_admin_password ]'
assert_ok "the file-intake variable is present instead of a value" \
  podman exec "$CTR" sh -c "env | grep -q '^GF_SECURITY_ADMIN_PASSWORD__FILE=/run/secrets/grafana_admin_password$'"
assert_absent "no plaintext GF_SECURITY_ADMIN_PASSWORD variable is present" \
  podman exec "$CTR" sh -c "env | grep -q '^GF_SECURITY_ADMIN_PASSWORD='"
# The value is read inside the container because fix-secret-ownership.sh maps the
# host file to Grafana's uid, which leaves it unreadable from the host.
admin_pw="$(podman exec "$CTR" cat /run/secrets/grafana_admin_password)"
assert_absent "the secret value itself does not appear anywhere in the environment" \
  podman exec "$CTR" sh -c "env | grep -qF '$admin_pw'"

echo
if [ "$failures" -eq 0 ]; then
  echo "RESULT: all Grafana assertions passed"
else
  echo "RESULT: $failures assertion(s) failed"
fi
exit "$failures"
