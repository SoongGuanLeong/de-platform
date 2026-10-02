#!/usr/bin/env bash
#
# Proves the register and budget validator is load-bearing rather than decorative.
#
# It builds a throwaway copy of docs/ under /tmp, asserts the clean copy passes,
# then mutates one thing at a time and asserts each mutation fails. A check that
# survives every mutation is a check that asserts nothing, which is the failure
# this script exists to catch.
#
# The copy is removed with rm and rmdir rather than a recursive delete.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

work="$(mktemp -d "${TMPDIR:-/tmp}/de-platform-governance-lint.XXXXXX")"

remove_tree() {
  find "$1" -type f 2>/dev/null | while IFS= read -r file; do rm -f "${file}"; done
  find "$1" -depth -type d 2>/dev/null | while IFS= read -r dir; do rmdir "${dir}" 2>/dev/null || true; done
}

cleanup() { remove_tree "${work}"; }
trap cleanup EXIT

run() {
  uv run --frozen python -m de_governance.register --root "${work}" >/dev/null 2>&1
}

reset() {
  if [ -d "${work}/docs" ]; then remove_tree "${work}/docs"; fi
  cp -r docs "${work}/docs"
}

expect_pass() {
  if ! run; then
    echo "::error::${1} did not pass the register validator" >&2
    exit 1
  fi
}

expect_fail() {
  if run; then
    echo "::error::${1} was mutated and the validator still passed" >&2
    exit 1
  fi
  printf 'mutation caught: %s\n' "${1}"
}

# One mutation per invocation, applied to the throwaway copy. The register is
# round-tripped through PyYAML, which drops the comments; that is fine for a copy
# that is deleted at the end of the run.
mutate() {
  uv run --frozen python - "$1" "${work}/docs/completion-bar.yaml" <<'PY'
import os
import sys

import yaml

name, register_path = sys.argv[1], sys.argv[2]
with open(register_path, encoding="utf-8") as handle:
    document = yaml.safe_load(handle)
instance = document["instances"][0]

ITEM = {
    "id": "compose-and-profile-layer-smoke",
    "capability": "compose-and-profile-layer",
    "matrix_rows": ["M17"],
    "claim": "the smoke profile's readiness assertion passes",
    "proves": "behaviour",
    "command": "bash deployment/scripts/preflight.sh smoke",
    "profile": "smoke",
    "commit": "6b9ce49",
    "date": "2026-10-02",
    "artifact": "raw/preflight.txt",
}


def write_evidence(item):
    directory = os.path.join(
        os.path.dirname(register_path), "evidence", "infrastructure-as-code", "compose-and-profile-layer"
    )
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "item.md"), "w", encoding="utf-8") as handle:
        handle.write("---\n" + yaml.safe_dump(item, sort_keys=False) + "---\n")
    instance["evidence"].append(item["id"])


if name == "no-assigned-phase":
    document["classes"][-1].pop("assigned_in_phase")
elif name == "vocabulary-missing-class":
    document["classes"].pop()
elif name == "class-outside-the-vocabulary":
    instance["class"] = "not-a-class"
elif name == "complete-without-behaviour":
    instance["status"] = "complete"
elif name == "dangling-evidence":
    instance["evidence"].append("no-such-item")
elif name == "unresolved-deferral":
    instance["not_applicable"][0]["reason"] = "  "
elif name == "no-failure-modes":
    instance["failure_modes"] = []
elif name == "module-does-not-resolve":
    instance["module"] = "no_such_module"
elif name == "representative-without-mutation-note":
    instance["representative"] = True
    document["classes"][-1]["representative"] = instance["id"]
elif name == "valid-budget-cited":
    write_evidence(dict(ITEM, budget_ref="m4-cross-path-tolerance"))
elif name == "unknown-budget-cited":
    write_evidence(dict(ITEM, budget_ref="no-such-budget"))
elif name == "pending-budget-cited":
    write_evidence(dict(ITEM, budget_ref="m4-batch-wallclock"))
else:
    raise SystemExit("unknown mutation: " + name)

with open(register_path, "w", encoding="utf-8") as handle:
    yaml.safe_dump(document, handle, sort_keys=False)
PY
}

reset
expect_pass "the clean copy"
printf 'clean copy passes\n'

for mutation in \
  no-assigned-phase \
  vocabulary-missing-class \
  class-outside-the-vocabulary \
  complete-without-behaviour \
  dangling-evidence \
  unresolved-deferral \
  no-failure-modes \
  module-does-not-resolve \
  representative-without-mutation-note \
  unknown-budget-cited \
  pending-budget-cited
do
  reset
  mutate "${mutation}"
  expect_fail "${mutation}"
done

# The positive path, so the failures above are the rule firing rather than the
# validator rejecting evidence or budgets wholesale.
reset
mutate valid-budget-cited
expect_pass "a valid evidence item citing a committed budget"
printf 'a valid citation passes\n'

printf 'the register and budget validator is load-bearing\n'
