# Write the streaming serving copy from Flink, and carry convergence with ReplacingMergeTree

**Status:** accepted

Flink writes the streaming serving copy in ClickHouse rather than the ClickHouse Kafka engine consuming the CDC topic directly. Both paths are at-least-once, so the choice is not about delivery guarantees; it is about the serving copy and the system of record sharing one processing path. Flink is the same job that writes Iceberg, so one keying and one ordering token drive both, and the lineage graph M11 requires stays intact. Upserts land in a `ReplacingMergeTree` keyed on the business key and versioned by the source LSN, so last-write-wins is deterministic and replay converges; deletes are tombstones.

## Considered options

- **ClickHouse Kafka engine with a materialised view.** Rejected: it makes the serving copy a second, independent consumer of the CDC topic with no common reconciliation path against Iceberg, so the two can diverge silently. It also reads the topic directly, so the CDC-to-ClickHouse lineage edge bypasses the Iceberg path that M11 records.
- **Micro-batch materialisation from Iceberg.** Rejected: it reuses the batch partition-swap mechanism cleanly, but bounds freshness by the batch interval, which is weaker than the near-real-time claim M8 exists to evidence.

## Consequences

The official ClickHouse Flink connector's sink does not support exactly-once semantics, which its README states outright, so delivery is at-least-once and the convergence claim rests on deterministic LSN versioning in the table engine. This mirrors ADR-0002's exactly-once-effect framing: the guarantee is a property of committed state, not of delivery. A second sink in the Flink job means ClickHouse backpressure can stall the Iceberg sink; if that appears, the fallback is a separate consumer of the gold changelog. `ReplacingMergeTree` deduplicates on merge, so the P3 queries must read through `FINAL` or an `argMax`/`GROUP BY` idiom, and which of the two is used is an open measurement rather than a settled choice. Evidence: ticket [The serving layer's concrete shape](https://github.com/SoongGuanLeong/de-platform/issues/12).
