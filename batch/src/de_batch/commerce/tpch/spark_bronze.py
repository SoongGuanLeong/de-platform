"""The Spark job that lands TPC-H into Iceberg bronze.

One Iceberg table per TPC-H source table, written through the Polaris Iceberg
REST catalog to SeaweedFS. Bronze holds the source's own records as they
arrived, so every source column lands as a string and one provenance column
records the flat file. No cleansing, no dedup and no business logic happen here;
silver is where these are typed.

The load is idempotent: each table is created if absent and then overwritten
with the source rows, so a second run leaves every row count unchanged rather
than appending a duplicate set.

The row-count assertion is against the flat files, counted independently by
de_batch.commerce.tpch.flatfiles, never against Spark's own read of them.

The job reads its configuration from the environment, because it runs inside the
batch profile's Spark container, where the catalog and the object store are
reached by their compose service names:

- DE_TPCH_FLAT_DIR          the directory dbgen wrote the .tbl files into
- DE_TPCH_SCALE_FACTOR      the scale factor those files are, for the label
- DE_ICEBERG_CATALOG        the Spark catalog name (default polaris)
- DE_ICEBERG_REST_URI       the Polaris Iceberg REST base
- DE_ICEBERG_WAREHOUSE      the catalog name
- DE_ICEBERG_CREDENTIAL     client_id:client_secret for the REST catalog
- DE_S3_ENDPOINT            the S3 endpoint Polaris vends the location under
- DE_S3_ACCESS_KEY_ID       the object store access key
- DE_S3_SECRET_ACCESS_KEY   the object store secret key
- DE_S3_REGION              the object store region
"""

from __future__ import annotations

import json
import os
import time

from de_batch.commerce.tpch import load, spec, volume


class Config:
    """The job's configuration, read from the environment."""

    def __init__(self, env) -> None:
        self.flat_dir = env["DE_TPCH_FLAT_DIR"]
        self.scale_factor = int(env.get("DE_TPCH_SCALE_FACTOR", "1"))
        self.catalog = env.get("DE_ICEBERG_CATALOG", "polaris")
        self.rest_uri = env["DE_ICEBERG_REST_URI"]
        self.warehouse = env["DE_ICEBERG_WAREHOUSE"]
        self.credential = env["DE_ICEBERG_CREDENTIAL"]
        self.s3_endpoint = env["DE_S3_ENDPOINT"]
        self.s3_access_key = env["DE_S3_ACCESS_KEY_ID"]
        self.s3_secret_key = env["DE_S3_SECRET_ACCESS_KEY"]
        self.s3_region = env.get("DE_S3_REGION", "us-east-1")


def build_spark(config: Config):
    """A SparkSession whose default catalog is the Polaris REST catalog."""
    from pyspark.sql import SparkSession

    catalog = config.catalog
    return (
        SparkSession.builder.appName("tpch-bronze-load")
        .config("spark.sql.catalog." + catalog, "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog." + catalog + ".type", "rest")
        .config("spark.sql.catalog." + catalog + ".uri", config.rest_uri)
        .config("spark.sql.catalog." + catalog + ".warehouse", config.warehouse)
        .config("spark.sql.catalog." + catalog + ".credential", config.credential)
        .config("spark.sql.catalog." + catalog + ".scope", "PRINCIPAL_ROLE:ALL")
        .config(
            "spark.sql.catalog." + catalog + ".io-impl",
            "org.apache.iceberg.aws.s3.S3FileIO",
        )
        .config("spark.sql.catalog." + catalog + ".s3.endpoint", config.s3_endpoint)
        .config("spark.sql.catalog." + catalog + ".s3.path-style-access", "true")
        .config("spark.sql.catalog." + catalog + ".s3.access-key-id", config.s3_access_key)
        .config("spark.sql.catalog." + catalog + ".s3.secret-access-key", config.s3_secret_key)
        .config("spark.sql.catalog." + catalog + ".s3.region", config.s3_region)
        .config("spark.sql.catalog." + catalog + ".client.region", config.s3_region)
        .config("spark.sql.defaultCatalog", catalog)
        .getOrCreate()
    )


def _identifier(config: Config, table: str) -> str:
    return config.catalog + "." + table


def ensure_namespaces(spark, config: Config) -> None:
    """Create the spine and layer namespaces. A nested namespace needs its parent."""
    spark.sql("CREATE NAMESPACE IF NOT EXISTS " + config.catalog + "." + spec.SPINE)
    spark.sql(
        "CREATE NAMESPACE IF NOT EXISTS " + config.catalog + "." + spec.SPINE + "." + spec.LAYER
    )


def read_source(spark, config: Config, table: spec.SourceTable):
    """The flat file as a DataFrame of strings, one column per source column.

    dbgen separates fields with a pipe and terminates every record with a
    trailing pipe. Spark's split() drops trailing empty fields, so splitting the
    raw line yields exactly the source columns and no synthetic trailing one.
    """
    from pyspark.sql import functions as functions

    columns = [column.name for column in table.columns]
    parts = functions.split(functions.col("value"), "\\|")
    lines = spark.read.text(os.path.join(config.flat_dir, table.flat_file))
    return lines.select(*[parts[i].alias(name) for i, name in enumerate(columns)]).withColumn(
        "_source_file", functions.lit(table.flat_file)
    )


def write_bronze(spark, config: Config, target: load.LoadTarget) -> None:
    """Create the table if absent and overwrite it with the source rows."""
    table = spec.source_table(target.source)
    identifier = _identifier(config, target.table)
    columns = [column.name for column in table.columns]
    ddl = (
        "CREATE TABLE IF NOT EXISTS "
        + identifier
        + " ("
        + ", ".join(name + " STRING" for name in columns)
        + ", _source_file STRING) USING iceberg"
    )
    spark.sql(ddl)
    frame = read_source(spark, config, table)
    frame.createOrReplaceTempView("_tpch_source")
    spark.sql("INSERT OVERWRITE " + identifier + " SELECT * FROM _tpch_source")


def count_table(spark, config: Config, table: str) -> int:
    return spark.sql("SELECT count(*) FROM " + _identifier(config, table)).collect()[0][0]


def main(argv: list[str] | None = None) -> int:
    config = Config(os.environ)
    targets = load.plan(config.flat_dir)
    expected = {target.table: target.expected_rows for target in targets}

    spark = build_spark(config)
    try:
        ensure_namespaces(spark, config)
        started = time.monotonic()
        for target in targets:
            write_bronze(spark, config, target)
        elapsed = time.monotonic() - started

        actual = {target.table: count_table(spark, config, target.table) for target in targets}
        load.verify(expected, actual)
    finally:
        spark.stop()

    total = sum(actual.values())
    print("COUNTS " + json.dumps(actual, sort_keys=True))
    print(volume.Volume(volume.DECLARED_SCALE_FACTOR, config.scale_factor).label())
    print(volume.throughput(total, elapsed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
