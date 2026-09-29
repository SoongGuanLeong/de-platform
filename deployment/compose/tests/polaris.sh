#!/bin/sh
# Security evidence: Polaris.
#
# Proves the three Polaris items from docs/security-evidence-plan.md:
#   - rotation end to end
#   - successful events audited (read back from the metastore with SQL)
#   - a denial is attributable
#
# A refusal assertion requires BOTH the expected HTTP status AND the expected
# refusal message, so a container that is simply down cannot be mistaken for a
# control that refused. Each item also carries a positive control, so a refusal
# cannot be blamed on a dead service.
#
# Rotation behaviour, recorded in the output rather than hidden: Polaris's
# /rotate is two-phase. It issues a new secret and demotes the previous one to
# a "secondary" that keeps authenticating until the next rotation; at that
# second rotation the middle secret becomes the secondary in turn and the
# secret from two rotations back is refused. A root /reset, by contrast,
# refuses the immediately previous secret at once. The rotation section asserts
# this sequence, and the mechanism behind it is asserted from the metastore: a
# row in polaris_schema.principal_authentication_data carrying a main and a
# secondary secret hash, with rotateSecrets demoting main to secondary.
#
# Event evidence, and its limit: the event framework emits BEFORE_* for every
# bracketed operation and AFTER_* only on success, so a request that does not
# complete leaves an unmatched BEFORE_* row. An unmatched BEFORE_* row means
# "attempted and did not complete", not specifically "denied": a 404 leaves one
# too. The denial itself is the HTTP 403 and the PolarisAuthorizerImpl line,
# and there is no denial event type anywhere in the events table.
set -u

CTR=de-platform-security-polaris
PG=de-platform-security-polaris-postgres
BASE=http://127.0.0.1:58181
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
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

assert_ok_code() {
  desc="$1"; want="$2"; shift 2
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && [ "$out" = "$want" ]; then
    printf 'PASS  %s\n      HTTP %s\n' "$desc" "$out"
  else
    printf 'FAIL  %s\n      expected HTTP %s, got exit=%s output=%s\n' "$desc" "$want" "$rc" "$(printf '%s' "$out" | head -2 | tr '\n' ' ')"
    failures=$((failures + 1))
  fi
}

assert_refused_code() {
  desc="$1"; want="$2"; pattern="$3"; shift 3
  out="$("$@" 2>&1)"; rc=$?
  body="$(cat /tmp/polaris-token-body 2>/dev/null)"
  if [ "$rc" -eq 0 ] && [ "$out" = "$want" ] && printf '%s' "$body" | grep -Eq "$pattern"; then
    printf 'PASS  %s\n      refused with HTTP %s: %s\n' "$desc" "$out" "$(printf '%s' "$body" | head -c 200 | tr '\n' ' ')"
  else
    printf 'FAIL  %s\n      expected HTTP %s matching /%s/, got exit=%s HTTP=%s body=%s\n' "$desc" "$want" "$pattern" "$rc" "$out" "$(printf '%s' "$body" | head -c 200 | tr '\n' ' ')"
    failures=$((failures + 1))
  fi
}

token_code() {
  curl -s -o /tmp/polaris-token-body -w "%{http_code}" -X POST "$BASE/api/catalog/v1/oauth/tokens" -d grant_type=client_credentials -d "client_id=$1" --data-urlencode "client_secret=$2" -d scope=PRINCIPAL_ROLE:ALL
}

sql() {
  podman exec "$PG" psql -U deplatform -d deplatform -tAc "$1"
}

access_log_count() {
  podman logs "$CTR" 2>&1 | grep -ac 'io.qua.htt.access-log'
}

authorizer_count() {
  podman logs "$CTR" 2>&1 | grep -ac 'PolarisAuthorizerImpl'
}

auth_hashes() {
  sql "select coalesce(main_secret_hash, '') || '|' || coalesce(secondary_secret_hash, '') from polaris_schema.principal_authentication_data where principal_client_id = '$1'"
}

create_ns_code() {
  curl -s -o /tmp/polaris-ns-body -w "%{http_code}" -X POST "$BASE/api/catalog/v1/evidence/namespaces" -H "Authorization: Bearer $1" -H "Content-Type: application/json" -d "{\"namespace\":[\"$2\"],\"properties\":{}}"
}

load_ns_code() {
  curl -s -o /tmp/polaris-load-body -w "%{http_code}" "$BASE/api/catalog/v1/evidence/namespaces/$1" -H "Authorization: Bearer $2"
}

persist_secret() {
  printf '%s\n' "$1" | podman unshare sh -c "cat > $REPO/runtime/secrets/polaris_client_secret"
}

echo "== precondition: the services are running =="
if ! podman exec "$CTR" true >/dev/null 2>&1; then
  echo "FAIL  the container $CTR is not running; no assertion below is meaningful"
  exit 1
fi
echo "PASS  the container $CTR is running"
if ! podman exec "$PG" true >/dev/null 2>&1; then
  echo "FAIL  the container $PG is not running; the event audit needs the metastore"
  exit 1
fi
echo "PASS  the container $PG is running"

# The secrets are read from inside the container, not from runtime/secrets:
# profiles/polaris-fix-ownership.sh maps them to the container uid, which
# leaves them unreadable from the host. Reading them in the container is also
# the assertion that the value arrives as a file at /run/secrets.
boot="$(podman exec "$CTR" cat /run/secrets/polaris_bootstrap_secret)"
file_secret="$(podman exec "$CTR" cat /run/secrets/polaris_client_secret)"

root_token="$(curl -s -X POST "$BASE/api/catalog/v1/oauth/tokens" -d grant_type=client_credentials -d client_id=root --data-urlencode "client_secret=$boot" -d scope=PRINCIPAL_ROLE:ALL | jq -r .access_token)"
assert_ok "the bootstrap secret from /run/secrets authenticates as root" test -n "$root_token"

echo
echo "== setup: the catalog and the non-root service principal =="
cat_body="{\"catalog\":{\"type\":\"INTERNAL\",\"name\":\"evidence\",\"properties\":{\"default-base-location\":\"s3://warehouse/evidence\"},\"storageConfigInfo\":{\"storageType\":\"S3\",\"allowedLocations\":[\"s3://warehouse/evidence\"],\"roleArn\":\"arn:aws:iam::000000000000:role/polaris\",\"region\":\"us-east-1\"}}}"
cat_code="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/management/v1/catalogs" -H "Authorization: Bearer $root_token" -H "Content-Type: application/json" -d "$cat_body")"
assert_ok "the evidence catalog exists (created now or already present)" sh -c "test \"$cat_code\" = 201 -o \"$cat_code\" = 409"

pcode="$(curl -s -o /tmp/polaris-principal -w "%{http_code}" "$BASE/api/management/v1/principals/svc_engine" -H "Authorization: Bearer $root_token")"
current=""
if [ "$pcode" = 404 ]; then
  curl -s -o /tmp/polaris-principal -X POST "$BASE/api/management/v1/principals" -H "Authorization: Bearer $root_token" -H "Content-Type: application/json" -d '{"principal":{"name":"svc_engine"},"credentialRotationRequired":false}'
  cid="$(jq -r .credentials.clientId /tmp/polaris-principal)"
  current="$(jq -r .credentials.clientSecret /tmp/polaris-principal)"
  persist_secret "$current"
  printf '      created principal svc_engine with clientId %s\n' "$cid"
else
  cid="$(jq -r .clientId /tmp/polaris-principal)"
  current="$file_secret"
fi
assert_ok "the service principal exists with a client id" test -n "$cid"

# A principal role with no privileges. It lets svc_engine authenticate, and it
# is what makes the denial below a real authorisation decision rather than an
# authentication failure.
curl -s -o /dev/null -X POST "$BASE/api/management/v1/principal-roles" -H "Authorization: Bearer $root_token" -H "Content-Type: application/json" -d '{"principalRole":{"name":"svc_role"}}'
curl -s -o /dev/null -X PUT "$BASE/api/management/v1/principals/svc_engine/principal-roles" -H "Authorization: Bearer $root_token" -H "Content-Type: application/json" -d '{"principalRole":{"name":"svc_role"}}'
assert_ok "the service principal holds a role with no privileges" sh -c "curl -s -H \"Authorization: Bearer $root_token\" $BASE/api/management/v1/principals/svc_engine/principal-roles | grep -q svc_role"

# The runtime file may be stale (its value is only ever written by a previous
# run of this test). If it does not authenticate, establish a known secret with
# a root reset, which is the management-API path that invalidates all previous
# secrets at once.
if [ "$(token_code "$cid" "$current")" != 200 ]; then
  reset_body="$(curl -s -X POST "$BASE/api/management/v1/principals/svc_engine/reset" -H "Authorization: Bearer $root_token")"
  current="$(printf '%s' "$reset_body" | jq -r .credentials.clientSecret)"
  persist_secret "$current"
  printf '      the runtime secret was stale; established a new one via root reset\n'
fi

echo
echo "== event audit: a successful operation is recorded in the metastore =="
ns="evidence_ns_$(date +%s)"
assert_ok_code "root creates a namespace (positive control)" 200 create_ns_code "$root_token" "$ns"
sleep 2
row="$(sql "select event_type || '|' || principal_name || '|' || resource_type || '|' || resource_identifier from polaris_schema.events where event_type = 'AFTER_CREATE_NAMESPACE' and additional_properties->>'namespace' = '$ns' order by timestamp_ms desc limit 1")"
assert_ok "the successful operation is an AFTER event row in polaris_schema.events" test -n "$row"
printf '      raw row: %s\n' "$row"
assert_ok "the event names the authenticated principal and the resource" sh -c "printf '%s' '$row' | grep -q '^AFTER_CREATE_NAMESPACE|root|NAMESPACE|$ns$'"

echo
echo "== denial attribution: a denied operation names the principal =="
stok="$(curl -s -X POST "$BASE/api/catalog/v1/oauth/tokens" -d grant_type=client_credentials -d "client_id=$cid" --data-urlencode "client_secret=$current" -d scope=PRINCIPAL_ROLE:ALL | jq -r .access_token)"
assert_ok "the service principal authenticates (positive control before the denial)" test -n "$stok"
denied="denied_ns_$(date +%s)"
before="$(access_log_count)"
auth_before="$(authorizer_count)"
denied_code="$(create_ns_code "$stok" "$denied")"
assert_ok "the denied request returns 403 with the authorisation message" sh -c "test \"$denied_code\" = 403 && grep -q 'not authorized for op CREATE_NAMESPACE' /tmp/polaris-ns-body"
printf '      raw body: %s\n' "$(head -c 240 /tmp/polaris-ns-body)"
sleep 1
podman logs "$CTR" 2>&1 | grep -a 'io.qua.htt.access-log' | tail -n +$((before + 1)) > /tmp/polaris-denial-log
assert_ok "the denial is recorded in the access log with the authenticated principal and a 403" grep -Eq 'svc_engine.*"POST /api/catalog/v1/evidence/namespaces HTTP/1.1" 403' /tmp/polaris-denial-log
printf '      raw access-log line: %s\n' "$(grep -E 'svc_engine.*namespaces' /tmp/polaris-denial-log | head -1)"
podman logs "$CTR" 2>&1 | grep -a 'PolarisAuthorizerImpl' | tail -n +$((auth_before + 1)) > /tmp/polaris-authorizer-log
assert_ok "the denial is also recorded by PolarisAuthorizerImpl with the principal, the operation and the missing privilege" grep -Eq "Authorization denied for principal 'svc_engine' on operation 'CREATE_NAMESPACE': missing NAMESPACE_CREATE on CATALOG 'evidence'" /tmp/polaris-authorizer-log
printf '      raw authorizer line: %s\n' "$(head -1 /tmp/polaris-authorizer-log)"
brow="$(sql "select event_type || '|' || principal_name || '|' || (additional_properties->>'create_namespace_request') from polaris_schema.events where event_type = 'BEFORE_CREATE_NAMESPACE' and principal_name = 'svc_engine' and additional_properties->>'create_namespace_request' like '%namespace=$denied,%' order by timestamp_ms desc limit 1")"
assert_ok "the denied request also leaves an unmatched BEFORE event naming the principal" test -n "$brow"
printf '      raw row: %s\n' "$brow"

# An unmatched BEFORE_* row is not by itself a denial. The event framework
# emits BEFORE_* for every operation it brackets and AFTER_* only on success,
# so a request that fails for any reason leaves one. A 404 for a namespace that
# does not exist is the control: root is authorised, so it is not a denial, yet
# it leaves the same shape of row. What makes the row above a denial is the 403
# and the PolarisAuthorizerImpl line, not the BEFORE_* row.
missing_ns="missing_ns_$(date +%s)"
nf_code="$(load_ns_code "$missing_ns" "$root_token")"
assert_ok "positive control: loading a namespace that does not exist returns 404" test "$nf_code" = 404
sleep 2
nf_row="$(sql "select b.event_type || '|' || b.principal_name || '|' || b.resource_identifier from polaris_schema.events b where b.event_type = 'BEFORE_LOAD_NAMESPACE_METADATA' and b.resource_identifier = '$missing_ns' and not exists (select 1 from polaris_schema.events a where a.request_id = b.request_id and a.event_type = 'AFTER_LOAD_NAMESPACE_METADATA') order by b.timestamp_ms desc limit 1")"
assert_ok "a 404 also leaves an unmatched BEFORE row, so a BEFORE row alone cannot be called a denial" test "$nf_row" = "BEFORE_LOAD_NAMESPACE_METADATA|root|$missing_ns"
printf '      raw row: %s\n' "$nf_row"

denial_types="$(sql "select count(*) from polaris_schema.events where event_type ilike '%DENIED%' or event_type ilike '%FORBIDDEN%' or event_type ilike '%ERROR%' or event_type ilike '%FAILURE%'")"
assert_ok "no denial, forbidden, error or failure event type exists in polaris_schema.events" test "$denial_types" = 0
printf '      event types matching DENIED/FORBIDDEN/ERROR/FAILURE: %s\n' "$denial_types"

echo
echo "== rotation: new secret works, and what happens to the old one =="
started_before="$(podman inspect -f '{{.State.StartedAt}}' "$CTR")"
self_tok="$(curl -s -X POST "$BASE/api/catalog/v1/oauth/tokens" -d grant_type=client_credentials -d "client_id=$cid" --data-urlencode "client_secret=$current" -d scope=PRINCIPAL_ROLE:ALL | jq -r .access_token)"
assert_ok "positive control: the current secret authenticates" test -n "$self_tok"

# The mechanism, from the metastore before any rotation: a principal's row
# carries a main and a secondary secret hash, and the two differ.
h_before="$(auth_hashes "$cid")"
bmain="${h_before%%|*}"
bsec="${h_before#*|}"
assert_ok "before rotating, the metastore row has a main and a secondary secret hash, and they differ" sh -c "test -n '$bmain' -a -n '$bsec' -a '$bmain' != '$bsec'"
printf '      raw row (clientId %s): main=%s secondary=%s\n' "$cid" "$bmain" "$bsec"

old="$current"
rot1="$(curl -s -X POST "$BASE/api/management/v1/principals/svc_engine/rotate" -H "Authorization: Bearer $self_tok")"
new="$(printf '%s' "$rot1" | jq -r .credentials.clientSecret)"
assert_ok "the rotate call issued a new secret" sh -c "test -n \"$new\" -a \"$new\" != null -a \"$new\" != \"$old\""
assert_ok_code "the NEW secret works" 200 token_code "$cid" "$new"
# Polaris /rotate is two-phase: the previous secret is demoted to the secondary
# and keeps authenticating until the next rotation.
assert_ok_code "after one /rotate the previous secret is still accepted, because Polaris keeps it as the secondary secret" 200 token_code "$cid" "$old"
h_after1="$(auth_hashes "$cid")"
amain="${h_after1%%|*}"
asec="${h_after1#*|}"
assert_ok "after the first rotate, the metastore row still has a main and a secondary hash, and they differ" sh -c "test -n '$amain' -a -n '$asec' -a '$amain' != '$asec'"
assert_ok "the rotate demoted the previous main hash to the secondary (the mechanism)" sh -c "test '$asec' = '$bmain'"
printf '      raw row (clientId %s): main=%s secondary=%s\n' "$cid" "$amain" "$asec"
self_tok2="$(curl -s -X POST "$BASE/api/catalog/v1/oauth/tokens" -d grant_type=client_credentials -d "client_id=$cid" --data-urlencode "client_secret=$new" -d scope=PRINCIPAL_ROLE:ALL | jq -r .access_token)"
rot2="$(curl -s -X POST "$BASE/api/management/v1/principals/svc_engine/rotate" -H "Authorization: Bearer $self_tok2")"
new2="$(printf '%s' "$rot2" | jq -r .credentials.clientSecret)"
# After the second rotate the secret from the first rotate is the secondary and
# still authenticates; the secret from before the first rotate (two rotations
# back) is refused.
assert_ok_code "after a second rotate the secret from the first rotate (now the secondary) is still accepted" 200 token_code "$cid" "$new"
assert_refused_code "after a second rotate the secret two rotations back is refused" 401 'unauthorized_client' token_code "$cid" "$old"
assert_ok_code "the newest secret works" 200 token_code "$cid" "$new2"
h_after2="$(auth_hashes "$cid")"
amain2="${h_after2%%|*}"
asec2="${h_after2#*|}"
assert_ok "after the second rotate, the metastore row still has a main and a secondary hash, and they differ" sh -c "test -n '$amain2' -a -n '$asec2' -a '$amain2' != '$asec2'"
assert_ok "the second rotate demoted the first rotate's main hash to the secondary" sh -c "test '$asec2' = '$amain'"
printf '      raw row (clientId %s): main=%s secondary=%s\n' "$cid" "$amain2" "$asec2"
reset2="$(curl -s -X POST "$BASE/api/management/v1/principals/svc_engine/reset" -H "Authorization: Bearer $root_token")"
rs="$(printf '%s' "$reset2" | jq -r .credentials.clientSecret)"
assert_refused_code "after a root /reset the immediately previous secret is refused at once" 401 'unauthorized_client' token_code "$cid" "$new2"
assert_ok_code "the reset secret works" 200 token_code "$cid" "$rs"
assert_ok "the rotation needed no restart (container start time unchanged)" sh -c "test \"$started_before\" = \"$(podman inspect -f '{{.State.StartedAt}}' "$CTR")\""
persist_secret "$rs"
printf '      the current valid secret is recorded under runtime/secrets/polaris_client_secret\n'

echo
if [ "$failures" -eq 0 ]; then
  echo "RESULT: all Polaris assertions passed"
else
  echo "RESULT: $failures assertion(s) failed"
fi
exit "$failures"
