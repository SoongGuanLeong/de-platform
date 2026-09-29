#!/bin/sh
# Security evidence: Kafka.
#
# Proves three deferred items from docs/security-evidence-plan.md:
#   - the data plane refuses bad credentials and accepts good ones
#   - TLS is enforced, so a plaintext client is refused
#   - an authorisation denial is logged, which is the audit item
#
# A refusal assertion requires BOTH a non-zero exit AND the expected refusal
# message, so a container that is simply down cannot be mistaken for a control
# that refused.
set -u

CTR=de-platform-security-kafka
KB=/opt/kafka/bin
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

echo "== precondition: the broker is running =="
if ! podman exec "$CTR" true >/dev/null 2>&1; then
  echo "FAIL  the container $CTR is not running; no assertion below is meaningful"
  exit 1
fi
echo "PASS  the container $CTR is running"

# Read from inside the container, not from runtime/secrets. The harness maps
# these files to the container's uid so that a non-root container user can read
# them, which leaves them unreadable from the host. Reading them in the
# container is also the assertion: the value arrives as a file at /run/secrets.
admin_pw="$(podman exec "$CTR" cat /run/secrets/kafka_admin_password)"
app_pw="$(podman exec "$CTR" cat /run/secrets/kafka_svc_password)"

render() {
  # render <template> <password> <dest>
  podman exec "$CTR" sh -c "sed 's|__PASSWORD__|$2|' /harness/templates/$1 > $3"
}
render client-admin.properties.tmpl "$admin_pw" /tmp/admin.properties
render client-svc.properties.tmpl "$app_pw" /tmp/svc.properties
podman exec "$CTR" sh -c "cp /harness/templates/client-plaintext.properties.tmpl /tmp/plain.properties"

admin() { podman exec "$CTR" "$KB/kafka-topics.sh" --bootstrap-server 127.0.0.1:9093 --command-config /tmp/admin.properties "$@"; }

echo
echo "== authentication: good credentials accepted, bad refused =="
assert_ok "the admin principal authenticates over SASL_SSL" \
  admin --list
assert_refused "a wrong password is refused" 'Authentication failed|SaslAuthenticationException|authentication failed' \
  podman exec "$CTR" sh -c "sed 's|__PASSWORD__|not-the-password|' /harness/templates/client-admin.properties.tmpl > /tmp/bad.properties && $KB/kafka-topics.sh --bootstrap-server 127.0.0.1:9093 --command-config /tmp/bad.properties --list"

echo
echo "== TLS: a plaintext client is refused =="
assert_refused "a plaintext client cannot complete a request against the SASL_SSL listener" \
  'TimeoutException|The AdminClient thread has exited' \
  podman exec "$CTR" "$KB/kafka-topics.sh" --bootstrap-server 127.0.0.1:9093 --command-config /tmp/plain.properties --list
# A client-side timeout alone does not show *why* the request failed, so the
# broker's own view is asserted as well: it refused the connection at TLS level.
assert_ok "the broker refused that connection at the TLS layer" \
  sh -c "podman exec $CTR grep -q 'SSL handshake failed' /opt/kafka/logs/server.log"

echo
echo "== authorisation: a denial is refused and logged =="
# The topic name is run-scoped, so the create below is a real create on every run
# rather than a no-op against a topic an earlier run left behind, and so the
# authorizer line asserted at the end can only have come from this run.
topic="security.evidence.$$.$(date +%s)"
# StandardAuthorizer writes denials to its own log file rather than to stdout,
# and that file is mode 0600 owned by the container user.
#
# Freshness comes from the run-scoped topic name, NOT from a line-count marker.
# An earlier version of this test recorded the file's line count before the
# denial and read only the lines after it. That silently broke at an hour
# boundary: Kafka rotates this log hourly, the marker was taken from the file
# that was then current, and the denial landed in the freshly rotated file, so
# the assertion failed while the control it was testing had worked. The search
# therefore spans the current log and any rotated sibling, and retries, because
# the appender flushes asynchronously.
authlog=/opt/kafka/logs/kafka-authorizer.log
assert_ok "the admin creates a topic" \
  admin --create --topic "$topic" --partitions 1 --replication-factor 1
assert_refused "an unprivileged principal is refused" 'TopicAuthorizationException|not authorized|Authorization failed' \
  podman exec "$CTR" "$KB/kafka-topics.sh" --bootstrap-server 127.0.0.1:9093 --command-config /tmp/svc.properties --create --topic "${topic}.denied" --partitions 1 --replication-factor 1
logged=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if podman exec "$CTR" sh -c "grep -hq 'Principal = User:svc_platform is Denied operation = CREATE from host = .* on resource = Topic:LITERAL:${topic}.denied' $authlog*"; then
    logged=1
    break
  fi
  sleep 1
done
if [ "$logged" -eq 1 ]; then
  printf 'PASS  the denial is recorded in the authorizer log naming principal, operation and resource\n'
else
  printf 'FAIL  the denial is recorded in the authorizer log naming principal, operation and resource\n      no line for ${topic}.denied in %s* within 10s\n' "$authlog"
  failures=$((failures + 1))
fi

echo
if [ "$failures" -eq 0 ]; then
  echo "RESULT: all Kafka assertions passed"
else
  echo "RESULT: $failures assertion(s) failed"
fi
exit "$failures"
