#!/bin/sh
# Security evidence: the two deferred items that need no running service.
#
# Proves two rows of docs/security-evidence-plan.md:
#   - secrets are absent from tracked files
#   - every secret the harness declares resolves to a file that exists
#
# The decisive control for the first row is structural rather than detective, as
# docs/security-model.md section 2.4 argues: gitignore correctness, plus a
# bootstrap path that cannot write outside runtime/. So this script checks the
# ignore rules and then checks the tracked tree for the values themselves, and it
# reports how many values it was actually able to check rather than implying that
# a check that read nothing proved something.
set -u

failures=0
checked=0
skipped=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n      %s\n' "$1" "$2"; failures=$((failures + 1)); }

assert_ok() {
  desc="$1"; shift
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ]; then
    pass "$desc"
  else
    fail "$desc" "exit=$rc output=$(printf '%s' "$out" | head -3 | tr '\n' ' ')"
  fi
}

echo "== precondition: this is a git checkout =="
if ! REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || [ -z "$REPO" ]; then
  echo "FAIL  not inside a git checkout; no assertion below is meaningful"
  exit 1
fi
cd "$REPO" || exit 1
pass "running in $REPO"

echo
echo "== the runtime directory and every secret-shaped path is gitignored =="
for p in runtime/ .env runtime/secrets/probe_password runtime/certs/probe.key probe.key probe.pem probe.jks probe.p12 probe.bak; do
  assert_ok "$p is ignored" git check-ignore -q "$p"
done
assert_ok ".env.example is NOT ignored" sh -c '! git check-ignore -q .env.example'
assert_ok ".env.example is tracked" git ls-files --error-unmatch .env.example

echo
echo "== no tracked file contains a value from runtime/secrets =="
for path in runtime/secrets/*; do
  [ -f "$path" ] || continue
  name="$(basename "$path")"
  # A file remapped to a container uid with podman unshare chown is unreadable by
  # this host user, so the value is read from inside the user namespace instead.
  # Only if both routes fail is the file skipped, and a skip is reported.
  value="$(cat "$path" 2>/dev/null || podman unshare cat "$path" 2>/dev/null || true)"
  if [ -z "$value" ]; then
    skipped=$((skipped + 1))
    printf 'SKIP  %s is unreadable by both routes, so its value was not checked\n' "$name"
    continue
  fi
  checked=$((checked + 1))
  # --untracked so that a new file is checked before it is committed, not only
  # after; ignored paths stay excluded, which is what keeps runtime/ out of scope.
  if git grep -qF --untracked -- "$value" -- . 2>/dev/null; then
    fail "$name does not appear in any tracked file" "the value was found in the tracked tree"
  else
    pass "$name does not appear in any tracked file"
  fi
done
if [ "$checked" -eq 0 ]; then
  fail "at least one secret value was actually checked" "no value could be read, so this check proved nothing"
else
  printf 'INFO  %s value(s) checked against the tracked tree, %s skipped\n' "$checked" "$skipped"
fi

echo
echo "== every secret the harness declares resolves to a file that exists =="
declared=0
for cf in deployment/security-harness/compose.yml deployment/security-harness/profiles/*.yml; do
  [ -f "$cf" ] || continue
  dir="$(dirname "$cf")"
  for rel in $(grep -E '^[[:space:]]+file:[[:space:]]' "$cf" | sed 's/^[[:space:]]*file:[[:space:]]*//'); do
    declared=$((declared + 1))
    if [ -f "$dir/$rel" ]; then
      pass "$(basename "$cf") declares $(basename "$rel"), which exists"
    else
      fail "$(basename "$cf") declares $(basename "$rel")" "no such file: $dir/$rel"
    fi
  done
done
if [ "$declared" -eq 0 ]; then
  fail "at least one secret declaration was found" "no 'file:' declarations were read, so this check proved nothing"
fi

echo
echo "== every *_FILE value in .env.example points under /run/secrets =="
for line in $(grep -E '^[A-Z_][A-Z0-9_]*_FILE=' .env.example); do
  var="${line%%=*}"; val="${line#*=}"
  case "$val" in
    /run/secrets/*) pass "$var points under /run/secrets" ;;
    *) fail "$var points under /run/secrets" "value is $val" ;;
  esac
done

echo
if [ "$failures" -eq 0 ]; then
  echo "RESULT: all static assertions passed"
else
  echo "RESULT: $failures assertion(s) failed"
fi
exit "$failures"
