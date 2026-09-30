"""The batch distribution resolves and its two spine packages import."""

import de_batch.commerce
import de_batch.network


def test_imports() -> None:
    assert de_batch.commerce.__name__ == "de_batch.commerce"
    assert de_batch.network.__name__ == "de_batch.network"
