"""The pinned Iceberg runtime jars the Spark job needs.

ADR-0024 pins Iceberg 1.11.0 with Spark 4.1.3, and the Iceberg Spark runtime is
not in the upstream Spark image, so the job supplies it. The AWS bundle carries
the S3FileIO implementation and its shaded AWS SDK, which the runtime jar does
not include. Both are pinned by version and by the checksum of the artifact on
Maven Central, so a repushed or replaced artifact is visible.
"""

from __future__ import annotations

from dataclasses import dataclass

ICEBERG_VERSION = "1.11.0"
SPARK_MINOR = "4.1"
SCALA_MINOR = "2.13"

_MAVEN = "https://repo1.maven.org/maven2/org/apache/iceberg"


@dataclass(frozen=True)
class Jar:
    """A Maven artifact: its file name, its URL and its checksum."""

    name: str
    url: str
    sha256: str


SPARK_RUNTIME = Jar(
    name="iceberg-spark-runtime-"
    + SPARK_MINOR
    + "_"
    + SCALA_MINOR
    + "-"
    + ICEBERG_VERSION
    + ".jar",
    url=(
        _MAVEN
        + "/iceberg-spark-runtime-"
        + SPARK_MINOR
        + "_"
        + SCALA_MINOR
        + "/"
        + ICEBERG_VERSION
        + "/iceberg-spark-runtime-"
        + SPARK_MINOR
        + "_"
        + SCALA_MINOR
        + "-"
        + ICEBERG_VERSION
        + ".jar"
    ),
    sha256="d6ea6c5d099288daeb7d5a92061bd3d7d8f296492632b42378e5f2f0e3066242",
)

AWS_BUNDLE = Jar(
    name="iceberg-aws-bundle-" + ICEBERG_VERSION + ".jar",
    url=(
        _MAVEN
        + "/iceberg-aws-bundle/"
        + ICEBERG_VERSION
        + "/iceberg-aws-bundle-"
        + ICEBERG_VERSION
        + ".jar"
    ),
    sha256="38f01da7e96850cdd05e6616d758b77b43314b712a8808e3f9a824d56976162f",
)


def jars() -> tuple[Jar, ...]:
    """The jars the Spark job must be given, in order."""
    return (SPARK_RUNTIME, AWS_BUNDLE)
