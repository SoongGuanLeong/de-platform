#!/usr/bin/env python3
"""The completion-bar register and budget validator.

The gate is deliberately cheap (ADR-0007): it validates fields and links, and it
never re-runs an evidence item. It reads four kinds of committed artefact and
nothing else:

1. `docs/completion-bar.yaml` - the register: the closed vocabulary of the eleven
   capability classes, each with its representative-instance slot, and one entry
   per capability instance.
2. `docs/budgets.yaml` - the threshold register every `budget_ref` must resolve
   to, with a committed (non-`pending`) value.
3. `docs/evidence/<class>/<instance>/<item>.md` - the evidence items, whose front
   matter carries the schema in [the completion bar](completion-bar.md) section 7.
4. the repository tree, for the module each instance names and for the commit each
   cited budget was declared in.

It executes no command from any artefact. An evidence item's `command` field is
recorded, never run: the required set contains no evidence re-run
(docs/ci-cd-strategy.md section 6). The only subprocess this module starts is
`git cat-file`, which resolves a commit sha and touches no evidence.

The class rule is scoped to classes that have instances (docs/completion-bar.md
section 12). The representative obligation is discharged phase by phase, so a
class whose instances have landed before its representative has been assigned
records the phase that will assign it (assigned_in_phase); a class with instances
and neither a representative nor a recorded phase is the failure this validator
exists to catch. That reading keeps docs/implementation-roadmap.md section 5,
which assigns each class's representative to a named phase, as the authority, and
the scoping is stated in the completion bar's own section 12.

It validates the threshold register against the contract in its own header
(docs/ci-cd-strategy.md section 4 calls this half the budget validator): unique
ids, the required fields, the fixed-versus-derived commitment rule, and that a
superseded entry is named by an entry that exists and is never cited.

Run: deployment/scripts/check-governance.sh
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys

import yaml

# The closed vocabulary. A class id outside this tuple, or a missing one, is a
# register failure: the vocabulary is closed and the obligation is not.
CANONICAL_CLASSES = (
    "kafka-ingestion",
    "cdc-ingestion",
    "flink-streaming",
    "spark-batch",
    "iceberg-table-management",
    "clickhouse-serving",
    "orchestration",
    "data-quality",
    "governance-and-lineage",
    "observability",
    "infrastructure-as-code",
)

INSTANCE_STATUSES = ("declared", "in-progress", "complete", "deferred")
PROVES_VALUES = ("signal", "behaviour")
PROFILES = ("smoke", "batch", "streaming", "observability", "benchmark")

# docs/completion-bar.md section 7: the evidence-item schema.
EVIDENCE_REQUIRED = (
    "id",
    "capability",
    "matrix_rows",
    "claim",
    "proves",
    "command",
    "profile",
    "commit",
    "date",
    "artifact",
)
EVIDENCE_OPTIONAL = ("budget_ref", "mutation_note", "observed_once")

# docs/budgets.yaml: the threshold-register entry schema.
BUDGET_REQUIRED = (
    "id",
    "metric",
    "unit",
    "threshold",
    "direction",
    "path",
    "commitment",
    "rationale",
    "declared_on",
    "declared_commit",
)

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
HEX_SHA = re.compile(r"[0-9a-f]{7,40}\Z")


def repository_root() -> str:
    """The repository this module ships in, for module and commit resolution."""
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )


def load_yaml(path: str, failures: list[str], label: str):
    if not os.path.isfile(path):
        failures.append(label + ": " + os.path.basename(path) + " does not exist")
        return None
    with open(path, encoding="utf-8") as handle:
        try:
            return yaml.safe_load(handle)
        except yaml.YAMLError as error:
            failures.append(
                label + ": " + os.path.basename(path) + " is not valid YAML: " + str(error)
            )
            return None


def valid_id(value, noun: str, seen: set[str], failures: list[str]) -> bool:
    """An identifier is a non-empty string, unique within its collection."""
    if not isinstance(value, str) or not value:
        failures.append(noun + " has no id")
        return False
    if value in seen:
        failures.append(noun + " " + repr(value) + " is declared twice")
        return False
    seen.add(value)
    return True


def as_list(value) -> list:
    """A register field that should be a list, or an empty one when it is not."""
    return value if isinstance(value, list) else []


def load_evidence(evidence_dir: str, failures: list[str]) -> dict[str, dict]:
    """Every evidence item under docs/evidence/, keyed by its id."""
    items: dict[str, dict] = {}
    seen: set[str] = set()
    if not os.path.isdir(evidence_dir):
        return items
    for directory, _subdirs, names in os.walk(evidence_dir):
        for name in sorted(names):
            if not name.endswith(".md") or name == "INDEX.md":
                continue
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, os.path.dirname(evidence_dir))
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            match = FRONT_MATTER.match(text)
            if not match:
                failures.append(relative + ": no YAML front matter")
                continue
            try:
                item = yaml.safe_load(match.group(1))
            except yaml.YAMLError as error:
                failures.append(relative + ": front matter is not valid YAML: " + str(error))
                continue
            if not isinstance(item, dict):
                failures.append(relative + ": front matter is not a mapping")
                continue
            item_id = item.get("id")
            if not valid_id(item_id, relative + ": evidence item", seen, failures):
                continue
            items[item_id] = {"item": item, "path": relative}
    return items


def check_classes(classes, failures: list[str]) -> dict[str, dict]:
    if not isinstance(classes, list):
        failures.append("register: classes is not a list")
        return {}
    declared: dict[str, dict] = {}
    for entry in classes:
        if not isinstance(entry, dict):
            failures.append("register: a class entry is not a mapping")
            continue
        class_id = entry.get("id")
        if not valid_id(class_id, "register: a class entry", set(declared), failures):
            continue
        declared[class_id] = entry
        representative = entry.get("representative")
        if representative is not None and not isinstance(representative, str):
            failures.append(
                "register: class " + class_id + " representative slot is neither an id nor null"
            )
        # Optional: a class whose representative is already assigned does not need
        # it, and a class with no instances needs neither. It is required only of a
        # populated class with no representative, which check_representatives reads.
        phase = entry.get("assigned_in_phase")
        if phase is not None and (
            not isinstance(phase, int) or isinstance(phase, bool) or phase < 0
        ):
            failures.append("register: class " + class_id + " assigned_in_phase is " + repr(phase))
    missing = [name for name in CANONICAL_CLASSES if name not in declared]
    extra = [name for name in declared if name not in CANONICAL_CLASSES]
    if missing:
        failures.append(
            "register: the closed vocabulary is missing class(es): " + ", ".join(missing)
        )
    if extra:
        failures.append("register: unknown class(es) outside the vocabulary: " + ", ".join(extra))
    return declared


def check_instances(instances, declared: dict[str, dict], failures: list[str]) -> dict[str, dict]:
    if not isinstance(instances, list):
        failures.append("register: instances is not a list")
        return {}
    by_id: dict[str, dict] = {}
    for entry in instances:
        if not isinstance(entry, dict):
            failures.append("register: an instance entry is not a mapping")
            continue
        instance_id = entry.get("id")
        if not valid_id(instance_id, "register: an instance entry", set(by_id), failures):
            continue
        by_id[instance_id] = entry

        class_id = entry.get("class")
        if class_id not in declared:
            failures.append(
                "register: instance "
                + instance_id
                + " names class "
                + repr(class_id)
                + ", which is not in the vocabulary"
            )
        for field in ("instance", "module"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                failures.append("register: instance " + instance_id + " has no " + field)
        status = entry.get("status")
        if status not in INSTANCE_STATUSES:
            failures.append("register: instance " + instance_id + " has status " + repr(status))
        if not isinstance(entry.get("representative"), bool):
            failures.append(
                "register: instance " + instance_id + " representative is not a boolean"
            )
        modes = entry.get("failure_modes")
        if (
            not isinstance(modes, list)
            or not modes
            or not all(isinstance(mode, str) and mode for mode in modes)
        ):
            failures.append(
                "register: instance " + instance_id + " has no enumerated failure modes"
            )
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not all(
            isinstance(item, str) and item for item in evidence
        ):
            failures.append("register: instance " + instance_id + " evidence is not a list of ids")
        deferrals = entry.get("not_applicable")
        if not isinstance(deferrals, list):
            failures.append("register: instance " + instance_id + " not_applicable is not a list")
        else:
            for deferral in deferrals:
                if not isinstance(deferral, dict):
                    failures.append(
                        "register: instance " + instance_id + " has a not_applicable entry "
                        "that is not a mapping"
                    )
                    continue
                for field in ("field", "reason"):
                    if not isinstance(deferral.get(field), str) or not deferral[field].strip():
                        failures.append(
                            "register: instance "
                            + instance_id
                            + " has an unresolved not_applicable deferral (no "
                            + field
                            + ")"
                        )
    return by_id


def check_representatives(
    declared: dict[str, dict], instances: dict[str, dict], failures: list[str]
) -> None:
    """One representative instance per populated class, or a recorded phase.

    docs/completion-bar.md section 12: every class that has at least one instance
    has exactly one instance flagged representative, and that instance's evidence
    carries the class's mutation note. The obligation is discharged at the phase
    docs/implementation-roadmap.md section 5 names, so a class whose representative
    is not yet assigned must record the phase that will assign it.
    """
    by_class: dict[str, list[dict]] = {name: [] for name in declared}
    for entry in instances.values():
        if entry.get("class") in by_class:
            by_class[entry["class"]].append(entry)

    for class_id, members in by_class.items():
        if not members:
            continue
        slot = declared[class_id].get("representative")
        flagged = [entry for entry in members if entry.get("representative") is True]
        if len(flagged) > 1:
            failures.append(
                "register: class " + class_id + " has " + str(len(flagged)) + " representative "
                "instances; exactly one is allowed"
            )
            continue
        if slot is None:
            if flagged:
                failures.append(
                    "register: class " + class_id + " has a representative instance but no "
                    "representative slot"
                )
            elif declared[class_id].get("assigned_in_phase") is None:
                failures.append(
                    "register: class " + class_id + " has instances but no representative "
                    "instance and no assigned_in_phase"
                )
            continue
        if slot not in instances:
            failures.append(
                "register: class "
                + class_id
                + " representative slot names "
                + repr(slot)
                + ", which is not a register instance"
            )
            continue
        if not flagged:
            failures.append(
                "register: class "
                + class_id
                + " representative slot names "
                + repr(slot)
                + " but no instance is flagged representative"
            )
            continue
        if flagged[0].get("id") != slot:
            failures.append(
                "register: class " + class_id + " representative slot and flagged instance disagree"
            )


def check_evidence_links(
    instances: dict[str, dict], evidence: dict[str, dict], failures: list[str]
) -> None:
    """Every evidence link resolves, in both directions."""
    for instance_id, entry in instances.items():
        for item_id in as_list(entry.get("evidence")):
            if item_id not in evidence:
                failures.append(
                    "register: instance "
                    + instance_id
                    + " cites evidence "
                    + repr(item_id)
                    + ", which does not resolve"
                )
                continue
            capability = evidence[item_id]["item"].get("capability")
            if capability != instance_id:
                failures.append(
                    "evidence: "
                    + evidence[item_id]["path"]
                    + " declares capability "
                    + repr(capability)
                    + " but is cited by "
                    + instance_id
                )
    for item_id, record in evidence.items():
        capability = record["item"].get("capability")
        if capability not in instances:
            failures.append(
                "evidence: "
                + record["path"]
                + " names capability "
                + repr(capability)
                + ", which is not a register instance"
            )
            continue
        if item_id not in as_list(instances[capability].get("evidence")):
            failures.append(
                "evidence: " + record["path"] + " is not cited by its capability " + capability
            )


def superseded_budgets(budgets: dict[str, dict]) -> set[str]:
    """The entries a later entry replaces. Evidence citing one is invalid.

    docs/completion-bar.md section 9: changing a budget creates a new entry, and
    evidence citing a superseded budget is invalid.
    """
    return {
        entry["supersedes"]
        for entry in budgets.values()
        if isinstance(entry.get("supersedes"), str) and entry["supersedes"]
    }


def check_evidence_fields(
    evidence: dict[str, dict],
    budgets: dict[str, dict],
    failures: list[str],
) -> None:
    for record in evidence.values():
        item = record["item"]
        path = record["path"]
        for field in EVIDENCE_REQUIRED:
            value = item.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                failures.append("evidence: " + path + " is missing required field " + field)
        if item.get("proves") not in PROVES_VALUES:
            failures.append("evidence: " + path + " proves " + repr(item.get("proves")))
        if item.get("profile") not in PROFILES:
            failures.append("evidence: " + path + " names profile " + repr(item.get("profile")))
        rows = item.get("matrix_rows")
        if (
            not isinstance(rows, list)
            or not rows
            or not all(isinstance(row, str) and row for row in rows)
        ):
            failures.append("evidence: " + path + " has no matrix_rows")
        if not ISO_DATE.match(str(item.get("date", ""))):
            failures.append("evidence: " + path + " date is not ISO (YYYY-MM-DD)")
        if not HEX_SHA.match(str(item.get("commit", ""))):
            failures.append("evidence: " + path + " commit is not a commit sha")
        for field in EVIDENCE_OPTIONAL:
            if field in item and item[field] is None:
                failures.append("evidence: " + path + " has an empty " + field)
        if "observed_once" in item and not isinstance(item["observed_once"], bool):
            failures.append("evidence: " + path + " observed_once is not a boolean")
        budget_ref = item.get("budget_ref")
        if budget_ref is not None:
            superseded = superseded_budgets(budgets)
            if not isinstance(budget_ref, str) or not budget_ref:
                failures.append("evidence: " + path + " budget_ref is not a budget id")
            elif budget_ref not in budgets:
                failures.append(
                    "evidence: "
                    + path
                    + " cites budget "
                    + repr(budget_ref)
                    + ", which does not resolve to docs/budgets.yaml"
                )
            elif budgets[budget_ref].get("threshold") == "pending":
                failures.append(
                    "evidence: "
                    + path
                    + " cites budget "
                    + budget_ref
                    + ", whose threshold is pending rather than committed"
                )
            elif budget_ref in superseded:
                failures.append(
                    "evidence: "
                    + path
                    + " cites budget "
                    + budget_ref
                    + ", which a later entry supersedes"
                )


def check_complete_instances(
    instances: dict[str, dict],
    evidence: dict[str, dict],
    failures: list[str],
) -> None:
    """A complete instance carries a behaviour item and defers no failure mode.

    docs/completion-bar.md section 12: every complete instance has at least one
    behaviour evidence item, and no complete instance has an unresolved deferral.
    A core checklist item may stay not-applicable for good, but a failure mode may
    not: completion asserts the modes were demonstrated end to end, and the CI can
    check only that the deferral is gone. Without that, a complete instance could
    defer every mode and pass, which is the premature-completion claim the rule
    exists to catch.
    """
    for instance_id, entry in instances.items():
        if entry.get("status") != "complete":
            continue
        items = [
            evidence[item_id]["item"]
            for item_id in as_list(entry.get("evidence"))
            if item_id in evidence
        ]
        if not any(item.get("proves") == "behaviour" for item in items):
            failures.append(
                "register: complete instance " + instance_id + " has no behaviour evidence item"
            )
        modes = {"failure mode: " + mode for mode in as_list(entry.get("failure_modes"))}
        for deferral in as_list(entry.get("not_applicable")):
            if isinstance(deferral, dict) and deferral.get("field") in modes:
                failures.append(
                    "register: complete instance "
                    + instance_id
                    + " still defers the failure mode "
                    + repr(deferral["field"])
                )


def check_representative_notes(
    declared: dict[str, dict],
    instances: dict[str, dict],
    evidence: dict[str, dict],
    failures: list[str],
) -> None:
    """The representative instance of each assigned class carries the mutation note."""
    for class_id, class_entry in declared.items():
        slot = class_entry.get("representative")
        if not slot or slot not in instances:
            continue
        items = [
            evidence[item_id]["item"]
            for item_id in as_list(instances[slot].get("evidence"))
            if item_id in evidence
        ]
        if not any(
            isinstance(item.get("mutation_note"), str) and item["mutation_note"].strip()
            for item in items
        ):
            failures.append(
                "register: the representative instance of class "
                + class_id
                + " has no evidence item carrying a mutation note"
            )


def check_budgets(budgets_document, failures: list[str]) -> dict[str, dict]:
    if not isinstance(budgets_document, dict):
        failures.append("budgets: docs/budgets.yaml is not a mapping")
        return {}
    entries = budgets_document.get("budgets")
    if not isinstance(entries, list):
        failures.append("budgets: budgets is not a list")
        return {}
    by_id: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            failures.append("budgets: an entry is not a mapping")
            continue
        budget_id = entry.get("id")
        if not valid_id(budget_id, "budgets: an entry", set(by_id), failures):
            continue
        by_id[budget_id] = entry
        for field in BUDGET_REQUIRED:
            if entry.get(field) is None or (
                isinstance(entry.get(field), str) and not entry[field].strip()
            ):
                failures.append("budgets: " + budget_id + " is missing required field " + field)
        commitment = entry.get("commitment")
        if commitment not in ("fixed", "derived"):
            failures.append("budgets: " + budget_id + " commitment is " + repr(commitment))
        threshold = entry.get("threshold")
        if threshold == "pending":
            if commitment != "derived":
                failures.append(
                    "budgets: " + budget_id + " has a pending threshold but is not derived"
                )
            if not isinstance(entry.get("derivation"), str) or not entry["derivation"].strip():
                failures.append(
                    "budgets: " + budget_id + " has a pending threshold with no derivation rule"
                )
        elif not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
            failures.append("budgets: " + budget_id + " threshold is " + repr(threshold))
        supersedes = entry.get("supersedes")
        if (
            supersedes is not None
            and supersedes not in by_id
            and supersedes
            not in {candidate.get("id") for candidate in entries if isinstance(candidate, dict)}
        ):
            failures.append("budgets: " + budget_id + " supersedes unknown " + repr(supersedes))
    return by_id


def check_modules(instances: dict[str, dict], repo_root: str, failures: list[str]) -> None:
    """The module an instance names resolves, imports, and lives in this repository.

    docs/repository-decomposition.md: each entry carries a module field naming the
    distribution that implements it, and CI asserts it resolves and is importable.
    The repository half of that is what makes the assertion mean the implementing
    module rather than any importable name: a stdlib or third-party module resolves
    and imports and implements nothing here.
    """
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    root = os.path.realpath(repo_root)
    for instance_id, entry in instances.items():
        module = entry.get("module")
        if not isinstance(module, str) or not module:
            continue
        try:
            spec = importlib.util.find_spec(module)
        except (ImportError, ValueError):
            spec = None
        locations = list(getattr(spec, "submodule_search_locations", None) or [])
        if spec is not None and spec.origin:
            locations.append(spec.origin)
        # The repository's own virtual environment lives under .venv, so a
        # location whose first segment under the root is a dot-directory is an
        # installed dependency rather than the module that implements the
        # instance. That is the difference between naming deployment/ and naming
        # yaml.
        inside = [
            os.path.relpath(os.path.realpath(location), root).split(os.sep)[0]
            for location in locations
        ]
        if (
            spec is None
            or not locations
            or not all(segment != os.pardir and not segment.startswith(".") for segment in inside)
        ):
            failures.append(
                "register: instance "
                + instance_id
                + " names module "
                + repr(module)
                + ", which does not resolve to a module in this repository"
            )


def check_commit(sha, repo_root: str, failures: list[str], where: str) -> None:
    if not isinstance(sha, str) or not HEX_SHA.match(sha):
        failures.append(where + " declares no commit sha in declared_commit")
        return
    try:
        result = subprocess.run(
            ["git", "-C", repo_root, "cat-file", "-e", sha + "^{commit}"],
            capture_output=True,
            check=False,
        )
    except OSError:
        return
    if result.returncode != 0:
        failures.append(where + " declares commit " + sha + ", which is not in this repository")


def cited_budgets(evidence: dict[str, dict]) -> set[str]:
    """The budget ids evidence items cite, which are the ones the CI resolves."""
    cited: set[str] = set()
    for record in evidence.values():
        budget_ref = record["item"].get("budget_ref")
        if isinstance(budget_ref, str) and budget_ref:
            cited.add(budget_ref)
    return cited


def validate(root: str, repo_root: str | None = None) -> list[str]:
    repo_root = repo_root or repository_root()
    failures: list[str] = []
    register = load_yaml(os.path.join(root, "docs", "completion-bar.yaml"), failures, "register")
    budgets_document = load_yaml(os.path.join(root, "docs", "budgets.yaml"), failures, "budgets")
    if register is None or budgets_document is None:
        return failures
    if not isinstance(register, dict):
        failures.append("register: docs/completion-bar.yaml is not a mapping")
        return failures
    if not isinstance(register.get("version"), int):
        failures.append("register: no integer version")

    budgets = check_budgets(budgets_document, failures)
    declared = check_classes(register.get("classes"), failures)
    instances = check_instances(register.get("instances"), declared, failures)
    evidence = load_evidence(os.path.join(root, "docs", "evidence"), failures)
    check_representatives(declared, instances, failures)
    check_evidence_links(instances, evidence, failures)
    check_evidence_fields(evidence, budgets, failures)
    check_complete_instances(instances, evidence, failures)
    check_representative_notes(declared, instances, evidence, failures)
    check_modules(instances, repo_root, failures)
    # Only a cited budget is resolved to its commit: docs/budgets.yaml is
    # committed with a placeholder in declared_commit and the sha written in the
    # follow-up commit, so an uncited entry is legitimately mid-sequence.
    for budget_id in sorted(cited_budgets(evidence)):
        entry = budgets.get(budget_id)
        if entry is not None:
            check_commit(entry.get("declared_commit"), repo_root, failures, "budgets: " + budget_id)
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the completion-bar register and budgets."
    )
    parser.add_argument(
        "--root", default=None, help="the tree holding docs/ (default: this repository)"
    )
    parser.add_argument(
        "--repo-root", default=None, help="the repository, for module and commit resolution"
    )
    arguments = parser.parse_args(argv)
    repo_root = arguments.repo_root or repository_root()
    root = arguments.root or repo_root
    failures = validate(root, repo_root)
    if failures:
        for message in failures:
            print("FAIL " + message, file=sys.stderr)
        print(str(len(failures)) + " governance failure(s)", file=sys.stderr)
        return 1
    print("governance: the register, its evidence links and the budgets validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
