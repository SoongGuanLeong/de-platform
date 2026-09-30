"""The ingestion distribution resolves and its two spine packages import."""

import de_ingestion.commerce
import de_ingestion.network


def test_imports() -> None:
    assert de_ingestion.commerce.__name__ == "de_ingestion.commerce"
    assert de_ingestion.network.__name__ == "de_ingestion.network"
