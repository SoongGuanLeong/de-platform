# Avro on the CDC topics with BACKWARD_TRANSITIVE compatibility

**Status:** accepted

The CDC Kafka topics carry Avro, one subject per topic named `<topic>-value`, with `BACKWARD_TRANSITIVE` compatibility enforced by the serializer against Apicurio's ccompat v7 endpoint. The producer is Debezium's Kafka Connect `AvroConverter` in `as-confluent` mode and the reader is Flink's `avro-confluent` format. **Correction, 2026-09-28 (ticket #15).** This amends the earlier reading that the platform's CDC path was Flink's `debezium-json`, which needs no registry.

## Considered options

- **`debezium-json` on the wire, with compatibility checked elsewhere.** Rejected: completion bar 6.1's test is that a backward-incompatible schema is rejected by the serializer, and only a registry-backed serializer can reject. Choosing JSON would downgrade that evidence item to a CI check.
- **Plain `BACKWARD`.** Rejected: the platform replays partitions from offset 0 and reads history through the read-through arm, so every historical consumer must read new data, not only the last one.

## Consequences

The Git YAML contracts are the sole authoring source; CI pushes them into Apicurio's native Data Contracts feature as a mirror, never the reverse, because the ccompat path accepts data-contract rules but does not store or enforce them. Research 06 and 11 carry dated correction notes. Evidence: ticket [Data contracts and schema compatibility policy](https://github.com/SoongGuanLeong/de-platform/issues/15).
