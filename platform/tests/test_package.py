"""The shared core resolves and imports, which is what the packaging graph asserts."""

import de_platform


def test_imports() -> None:
    assert de_platform.__name__ == "de_platform"
