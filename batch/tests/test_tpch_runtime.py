"""The Iceberg runtime jar pins follow ADR-0024.

The Spark image does not ship the Iceberg runtime, so the job supplies it. The
version is the ADR's, and a change to the engine pin must change this module
rather than a container image tag silently.
"""

from __future__ import annotations

from de_batch.commerce.tpch import runtime


def test_the_runtime_follows_the_iceberg_pin() -> None:
    assert runtime.ICEBERG_VERSION == "1.11.0"


def test_the_runtime_targets_spark_4_1_scala_2_13() -> None:
    assert runtime.SPARK_RUNTIME.name == "iceberg-spark-runtime-4.1_2.13-1.11.0.jar"
    assert "iceberg-spark-runtime-4.1_2.13/1.11.0" in runtime.SPARK_RUNTIME.url


def test_the_aws_bundle_is_the_same_version() -> None:
    assert runtime.AWS_BUNDLE.name == "iceberg-aws-bundle-1.11.0.jar"
    assert runtime.ICEBERG_VERSION in runtime.AWS_BUNDLE.url


def test_every_jar_carries_a_checksum() -> None:
    for jar in runtime.jars():
        assert len(jar.sha256) == 64
