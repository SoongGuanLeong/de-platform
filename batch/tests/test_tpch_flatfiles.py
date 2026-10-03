"""Row counts read independently from dbgen's own flat files.

The count must not come from the engine that loads the table, or the assertion
would compare an engine's count with itself. These are the reader that makes the
assertion independent.
"""

from __future__ import annotations

from de_batch.commerce.tpch import flatfiles


def _write(path, rows: int) -> None:
    path.write_text("".join("x\n" for _ in range(rows)), encoding="utf-8")


def test_count_rows_counts_data_lines(tmp_path) -> None:
    _write(tmp_path / "region.tbl", 5)
    assert flatfiles.count_rows(str(tmp_path / "region.tbl")) == 5


def test_a_file_without_a_trailing_newline_still_counts_its_last_row(tmp_path) -> None:
    (tmp_path / "nation.tbl").write_text("a\nb", encoding="utf-8")
    assert flatfiles.count_rows(str(tmp_path / "nation.tbl")) == 2


def test_an_empty_file_counts_zero(tmp_path) -> None:
    (tmp_path / "region.tbl").write_text("", encoding="utf-8")
    assert flatfiles.count_rows(str(tmp_path / "region.tbl")) == 0


def test_counts_reads_every_source_table(tmp_path) -> None:
    for index, name in enumerate(
        ("region", "nation", "part", "supplier", "partsupp", "customer", "orders", "lineitem")
    ):
        _write(tmp_path / (name + ".tbl"), index + 1)
    counted = flatfiles.counts(str(tmp_path))
    assert counted == {
        "region": 1,
        "nation": 2,
        "part": 3,
        "supplier": 4,
        "partsupp": 5,
        "customer": 6,
        "orders": 7,
        "lineitem": 8,
    }


def test_a_missing_flat_file_is_refused_rather_than_counted_as_zero(tmp_path) -> None:
    for name in ("region", "nation", "part", "supplier", "partsupp", "customer", "orders"):
        _write(tmp_path / (name + ".tbl"), 1)
    try:
        flatfiles.counts(str(tmp_path))
    except FileNotFoundError as error:
        assert "lineitem.tbl" in str(error)
        return
    raise AssertionError("a missing flat file must be refused")
