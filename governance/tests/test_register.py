"""The completion-bar register and budget validator (docs/completion-bar.md section 12)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from de_governance import register

REPO_ROOT = Path(register.repository_root())
REGISTER = Path("docs") / "completion-bar.yaml"

# A valid evidence item, so a test that is not about the evidence schema can cite
# one. Its command is inert; nothing in the validator executes it.
EVIDENCE_ITEM = {
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


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    """A throwaway copy of docs/, so a mutation never touches the repository."""
    shutil.copytree(REPO_ROOT / "docs", tmp_path / "docs")
    return tmp_path


def load(tree: Path) -> dict:
    return yaml.safe_load((tree / REGISTER).read_text(encoding="utf-8"))


def save(tree: Path, document: dict) -> None:
    (tree / REGISTER).write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def write_evidence(tree: Path, item: dict, name: str = "item.md") -> None:
    directory = tree / "docs" / "evidence" / "infrastructure-as-code" / "compose-and-profile-layer"
    directory.mkdir(parents=True, exist_ok=True)
    body = "---\n" + yaml.safe_dump(item, sort_keys=False) + "---\n\nprose\n"
    (directory / name).write_text(body, encoding="utf-8")


def cite(tree: Path, item: dict) -> None:
    write_evidence(tree, item)
    document = load(tree)
    document["instances"][0]["evidence"].append(item["id"])
    save(tree, document)


def test_the_shipped_register_validates() -> None:
    assert register.validate(str(REPO_ROOT)) == []


def test_the_vocabulary_is_closed(tree: Path) -> None:
    document = load(tree)
    document["classes"].pop()
    save(tree, document)
    assert any(
        "closed vocabulary is missing" in message for message in register.validate(str(tree))
    )

    document = load(tree)
    document["classes"].append(
        {"id": "not-a-class", "representative": None, "assigned_in_phase": 1}
    )
    save(tree, document)
    assert any("outside the vocabulary" in message for message in register.validate(str(tree)))


def test_a_populated_class_needs_a_representative_or_a_recorded_phase(tree: Path) -> None:
    document = load(tree)
    document["classes"][-1].pop("assigned_in_phase")
    save(tree, document)
    assert any(
        "has instances but no representative instance" in message
        for message in register.validate(str(tree))
    )


def test_a_complete_instance_needs_a_behaviour_item(tree: Path) -> None:
    document = load(tree)
    document["instances"][0]["status"] = "complete"
    save(tree, document)
    assert any(
        "has no behaviour evidence item" in message for message in register.validate(str(tree))
    )


def test_a_representative_carries_the_classs_mutation_note(tree: Path) -> None:
    document = load(tree)
    document["classes"][-1]["representative"] = "compose-and-profile-layer"
    document["instances"][0]["representative"] = True
    save(tree, document)
    assert any("carrying a mutation note" in message for message in register.validate(str(tree)))

    item = dict(EVIDENCE_ITEM, mutation_note="removed the readiness assertion and it failed")
    cite(tree, item)
    assert register.validate(str(tree)) == []


def test_a_dangling_evidence_link_fails_in_both_directions(tree: Path) -> None:
    document = load(tree)
    document["instances"][0]["evidence"].append("no-such-item")
    save(tree, document)
    assert any("does not resolve" in message for message in register.validate(str(tree)))

    document = load(tree)
    save(tree, document)
    write_evidence(tree, EVIDENCE_ITEM)
    assert any(
        "is not cited by its capability" in message for message in register.validate(str(tree))
    )


def test_an_unresolved_deferral_fails(tree: Path) -> None:
    document = load(tree)
    document["instances"][0]["not_applicable"][0]["reason"] = "  "
    save(tree, document)
    assert any(
        "unresolved not_applicable deferral" in message for message in register.validate(str(tree))
    )


def test_a_budget_reference_must_resolve_to_a_committed_budget(tree: Path) -> None:
    cite(tree, dict(EVIDENCE_ITEM, budget_ref="no-such-budget"))
    assert any("does not resolve" in message for message in register.validate(str(tree)))

    shutil.rmtree(tree / "docs" / "evidence")
    cite(tree, dict(EVIDENCE_ITEM, budget_ref="m4-batch-wallclock"))
    assert any(
        "pending rather than committed" in message for message in register.validate(str(tree))
    )

    shutil.rmtree(tree / "docs" / "evidence")
    cite(tree, dict(EVIDENCE_ITEM, budget_ref="m4-cross-path-tolerance"))
    assert register.validate(str(tree)) == []


def test_an_instance_module_must_resolve(tree: Path) -> None:
    document = load(tree)
    document["instances"][0]["module"] = "no_such_module"
    save(tree, document)
    assert any("does not resolve" in message for message in register.validate(str(tree)))


def test_an_evidence_command_is_never_executed(tree: Path, tmp_path: Path) -> None:
    sentinel = tmp_path / "executed"
    cite(tree, dict(EVIDENCE_ITEM, command="touch " + str(sentinel)))
    assert register.validate(str(tree)) == []
    assert not sentinel.exists()


def test_the_only_process_started_is_git(tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def record(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(register.subprocess, "run", record)
    cite(tree, dict(EVIDENCE_ITEM, budget_ref="m4-cross-path-tolerance"))
    assert register.validate(str(tree)) == []
    assert calls, "a cited budget must resolve its declared commit"
    assert {argv[0] for argv in calls} == {"git"}
