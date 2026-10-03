"""TPC-H generation and the bronze load (ticket #34).

One source table per module concern:

- spec is the catalogue: the eight TPC-H tables, their dbgen flat-file names,
  their columns and their bronze Iceberg names.
- dbgen builds the generator from a pinned source and runs it.
- flatfiles reads the row counts back from dbgen's own output, independently
  of the engine that loads them.
- volume holds the declared volume, the reduction label and the throughput
  label.
- load is the plan and the row-count assertion.
- spark_bronze is the Spark job that writes the bronze tables through the
  Polaris Iceberg REST catalog.

Bronze holds the source's own records as they arrived, and silver is where they
are typed (docs/data-architecture.md section 3), so a bronze table lands every
source column as a string and adds a source-file column. No cleansing, no dedup
and no business logic happen here.
"""

from __future__ import annotations

from de_batch.commerce.tpch import dbgen, flatfiles, load, spec, volume

__all__ = ["dbgen", "flatfiles", "load", "spec", "volume"]
