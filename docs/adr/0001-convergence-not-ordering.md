# Claim convergence, not ordering, for the change-capture path

**Status:** accepted

The path from PostgreSQL through Debezium and Kafka into Iceberg is specified as converging on the correct final state under duplicated and reordered arrival, not as preserving order. Kafka guarantees order within a partition only; per-key order is a consequence of how messages are keyed rather than a guarantee of its own, and a primary-key update moves the message key, so the old-key and new-key events land in different partitions and can be read in either order. Debezium inherits Kafka's rules and adds no ordering of its own, which makes "ordering preserved" a claim that is both free to state and impossible to falsify.

## Considered options

- **Claim ordering is preserved.** Rejected: it cannot fail, so it proves nothing, and one question about partition counts or primary-key updates punctures it.
- **Claim per-key ordering.** Rejected: the same guarantee wearing a narrower label, and it still breaks on a primary-key update.

## Consequences

Every event carries the source LSN as an ordering token, and the sink applies last-write-wins against it. The evidence changes shape: an idempotence test (replay a partition from offset 0, assert an identical snapshot state), a convergence test (feed a deliberately shuffled and duplicated stream, assert an identical final state), and a source-to-target reconciliation by primary key. Matrix row M2.
