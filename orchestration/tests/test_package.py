"""The orchestration distribution resolves and imports."""

import de_orchestration


def test_imports() -> None:
    assert de_orchestration.__name__ == "de_orchestration"
