"""The governance distribution resolves and imports."""

import de_governance


def test_imports() -> None:
    assert de_governance.__name__ == "de_governance"
