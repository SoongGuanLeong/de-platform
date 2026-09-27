# Materialise the serving layer into MergeTree rather than reading Iceberg in place

**Status:** accepted

ClickHouse serves analysts from MergeTree tables materialised out of Iceberg by Spark and Flink, with catalog read-through of Iceberg retained only as a measured comparison arm. "ClickHouse over Iceberg" admits two architectures with opposite performance characteristics: reading Iceberg in place through the catalog copies nothing, but is read-only, in beta, and gets none of MergeTree, so there is almost nothing to tune; materialising into MergeTree is where `ORDER BY` keys, projections, aggregate engines, codecs and TTL actually apply. The posting's emphasis on optimising the serving layer and tuning queries on a columnar store has nothing to attach to under the first reading.

## Considered options

- **Read Iceberg in place through the catalog.** Rejected as the architecture and retained as a benchmark arm: it is read-only, in beta, and exposes no physical-layout surface, so it cannot carry a serving-performance claim.
- **Materialise with no comparison arm.** Rejected: the architecture choice would then be a preference rather than a measurement.

## Consequences

Iceberg stays the system of record and ClickHouse holds a copy, so the two can disagree; the freshness gap becomes an explicit measurement rather than an unstated assumption, and the ingestion mechanism into ClickHouse is left as its own open decision. The comparison arm carries a beta dependency, which is a longevity liability. Matrix row M7.
