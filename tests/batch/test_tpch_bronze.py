"""The TPC-H generation and the bronze load, end to end (ticket #34).

The real components on the path ran: dbgen built from source and generated the
flat files, Spark wrote one Iceberg table per TPC-H source table through the
Polaris Iceberg REST catalog to SeaweedFS, and the row counts were asserted
against the flat files counted independently.

Two acceptance criteria are checked here that the load's own assertion cannot:
that a second run leaves every count unchanged, and that the throughput figure
the run prints is labelled a TPC-derived result rather than a TPC Benchmark
Result.

The load fits the batch profile's declared SeaweedFS ceiling (256 MiB). The
store's in-memory needle index is what did not: it pushed the SF1 load to a
measured 514 MiB anonymous and 337 MiB page cache, and the store was OOM-killed
partway through. Two bounded settings in the profile's SeaweedFS entrypoint
carry it instead - the volume index is disk-backed (-volume.index=leveldb) and
the Go heap carries a soft limit (GOMEMLIMIT=192MiB) - and the same load then
completes with a 171.9 MiB anonymous peak, every row count matching the flat
files. The measurement is in docs/local-development.md section 11.
"""

from __future__ import annotations

import json

from de_batch.commerce.tpch import flatfiles, spec


def _parse_counts(output):
    for line in output.splitlines():
        if line.startswith("COUNTS "):
            return json.loads(line[len("COUNTS ") :])
    raise AssertionError("the load printed no COUNTS line:\n" + output[-4000:])


def _expected(host_flat_dir):
    counted = flatfiles.counts(host_flat_dir)
    return {spec.bronze_identifier(name): counted[name] for name in spec.source_table_names()}


def test_the_bronze_load_is_correct_and_idempotent(tpch_fixture, load_runner):
    scale = tpch_fixture["scale"]
    host_flat_dir = tpch_fixture["host_dir"]

    first = load_runner(scale, host_flat_dir)
    assert first.returncode == 0, first.stdout[-4000:] + first.stderr[-4000:]
    counts_first = _parse_counts(first.stdout + first.stderr)

    # The independent count: read from the flat files, not from Spark.
    assert counts_first == _expected(host_flat_dir)

    # A second run leaves every row count unchanged.
    second = load_runner(scale, host_flat_dir)
    assert second.returncode == 0, second.stdout[-4000:] + second.stderr[-4000:]
    counts_second = _parse_counts(second.stdout + second.stderr)
    assert counts_second == counts_first

    # Every throughput figure is a TPC-derived result, never a Benchmark Result.
    assert "TPC-derived" in first.stdout
    assert "Benchmark" not in first.stdout
    assert "Benchmark" not in first.stderr
