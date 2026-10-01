#!/usr/bin/env bash
#
# Proves the compose-subset lint is load-bearing rather than decorative.
#
# It builds a throwaway copy of deployment/ under /tmp, asserts the clean copy
# passes, then mutates one thing at a time and asserts each mutation fails. A
# check that survives every mutation is a check that asserts nothing, which is
# the failure this script exists to catch.
#
# The copy is removed with rm and rmdir rather than a recursive delete.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

work="$(mktemp -d "${TMPDIR:-/tmp}/de-platform-compose-lint.XXXXXX")"

remove_tree() {
  find "$1" -type f 2>/dev/null | while IFS= read -r file; do rm -f "${file}"; done
  find "$1" -depth -type d 2>/dev/null | while IFS= read -r dir; do rmdir "${dir}" 2>/dev/null || true; done
}

cleanup() { remove_tree "${work}"; }
trap cleanup EXIT

cp -r deployment "${work}/deployment"

run() {
  uv run --frozen python "${work}/deployment/scripts/check_compose.py" --root "${work}" >/dev/null 2>&1
}

expect_pass() {
  if ! run; then
    echo "::error::the clean copy failed the compose-subset lint" >&2
    exit 1
  fi
}

restore() {
  cp -r deployment/compose "${work}/compose.restore"
  remove_tree "${work}/deployment/compose"
  cp -r "${work}/compose.restore" "${work}/deployment/compose"
  remove_tree "${work}/compose.restore"
  # The two files the mutations below edit outside compose/. Restoring them too
  # means a mutation can be added in any order without the next one reading a
  # tree an earlier one broke.
  cp deployment/tools.lock "${work}/deployment/tools.lock"
  cp deployment/budgets/profiles.yaml "${work}/deployment/budgets/profiles.yaml"
}

expect_fail() {
  if run; then
    echo "::error::$1 was mutated and the lint still passed" >&2
    exit 1
  fi
  printf 'mutation caught: %s\n' "$1"
  restore
}

expect_pass
printf 'clean copy passes\n'

# 1. A limit that matches no ceiling in the register.
python3 - "${work}/deployment/compose/smoke.yml" <<'PY'
import sys, pathlib
path = pathlib.Path(sys.argv[1])
path.write_text(path.read_text().replace("memory: 384M", "memory: 385M", 1))
PY
expect_fail "a limit that resolves to no ceiling"

# 2. A key outside the portable subset.
python3 - "${work}/deployment/compose/smoke.yml" <<'PY'
import sys, pathlib
path = pathlib.Path(sys.argv[1])
path.write_text(path.read_text().replace('    restart: "no"', '    restart: "no"\n    mem_limit: 384M', 1))
PY
expect_fail "a key outside the portable subset"

# 3. An image whose digest no longer matches tools.lock.
python3 - "${work}/deployment/compose/smoke.yml" <<'PY'
import sys, pathlib, re
path = pathlib.Path(sys.argv[1])
text = path.read_text()
path.write_text(re.sub(r"@sha256:[0-9a-f]{64}", "@sha256:" + "0" * 64, text, count=1))
PY
expect_fail "an image digest that disagrees with tools.lock"

# 4. A register peak that no longer matches its parts.
python3 - "${work}/deployment/budgets/profiles.yaml" <<'PY'
import sys, pathlib
path = pathlib.Path(sys.argv[1])
path.write_text(path.read_text().replace("peak: { memory_mib: 6976, cpus: 11.75 }",
                                         "peak: { memory_mib: 6977, cpus: 11.75 }", 1))
PY
expect_fail "a register peak that does not recompute"

# 5. A JVM service with no declared JDK.
python3 - "${work}/deployment/tools.lock" <<'PY'
import sys, pathlib
path = pathlib.Path(sys.argv[1])
path.write_text(path.read_text().replace('JVM_JDK_kafka="21"\n', "", 1))
PY
expect_fail "a JVM service with no declared JDK"

# 6. A ClickHouse ratio that clamps the declared ceiling below the register's.
python3 - "${work}/deployment/compose/clickhouse/limits-832m.xml" <<'PY'
import sys, pathlib
path = pathlib.Path(sys.argv[1])
path.write_text(path.read_text().replace(">1.0<", ">0.9<", 1))
PY
expect_fail "a ClickHouse ratio that clamps the declared ceiling"

# 7. A profile with no memory figure the preflight can resolve.
python3 - "${work}/deployment/budgets/profiles.yaml" <<'PY'
import sys, pathlib
path = pathlib.Path(sys.argv[1])
path.write_text(path.read_text().replace("    declared_per_run: true\n", "", 1))
PY
expect_fail "a profile the preflight cannot resolve a peak for"

# 8. A compose service that no runtime list classifies.
python3 - "${work}/deployment/tools.lock" <<'PY'
import sys, pathlib
path = pathlib.Path(sys.argv[1])
path.write_text(path.read_text().replace('NATIVE_SERVICES="postgres ', 'NATIVE_SERVICES="', 1))
PY
expect_fail "a compose service in no runtime list"

# 9. A shared service body that drifted in one profile only.
python3 - "${work}/deployment/compose/streaming.yml" <<'PY'
import sys, pathlib
path = pathlib.Path(sys.argv[1])
path.write_text(path.read_text().replace("interval: 2s", "interval: 3s", 1))
PY
expect_fail "a service body that drifted between two profiles"

printf 'the compose-subset lint is load-bearing\n'
