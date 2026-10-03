"""The declared volume, the reduction label and the throughput label.

Two rules live here. A reduced run is labelled as reduced and names the volume
actually used, because Phase 1 permits a reduction and a claim must not read as
if it were made at the declared volume. And every throughput figure is a
TPC-derived result: the TPC-H tools are used under the TPC permission notice,
which does not license calling a figure a TPC Benchmark Result.
"""

from __future__ import annotations

from de_batch.commerce.tpch import volume


def test_the_declared_volume_is_sf100() -> None:
    assert volume.DECLARED_SCALE_FACTOR == 100


def test_a_reduced_volume_says_so_and_names_both_factors() -> None:
    reduced = volume.Volume(declared=100, used=10)
    assert reduced.is_reduced() is True
    label = reduced.label()
    assert "reduced" in label
    assert "SF10" in label
    assert "SF100" in label


def test_a_run_at_the_declared_volume_is_not_reduced() -> None:
    full = volume.Volume(declared=100, used=100)
    assert full.is_reduced() is False
    assert "reduced" not in full.label()


def test_a_throughput_figure_is_labelled_tpc_derived() -> None:
    figure = volume.throughput(rows=8_661_245, seconds=13.6)
    assert "TPC-derived" in figure
    assert "Benchmark" not in figure


def test_the_throughput_figure_carries_the_rate() -> None:
    figure = volume.throughput(rows=1000, seconds=2.0)
    assert "500" in figure


def test_the_forbidden_phrase_is_refused_wherever_a_throughput_figure_is_written() -> None:
    try:
        volume.assert_tpc_derived("1,000 rows/s (TPC Benchmark Result)")
    except ValueError as error:
        assert "TPC Benchmark Result" in str(error)
        return
    raise AssertionError("a TPC Benchmark Result label must be refused")
