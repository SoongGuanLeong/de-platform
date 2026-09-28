# Run the ClickHouse serving feed as its own job

**Status:** accepted

Iceberg is the record and ClickHouse is a derived serving copy. The ClickHouse Flink connector is at-least-once and offers no two-phase commit, so if the serving feed shared a job with the Iceberg ingestion, a ClickHouse failure would fail the checkpoint and stop ingestion while ClickHouse was down. That is the coupling the architecture exists to avoid. The two feeds are therefore separate jobs with separate consumer groups: an ingestion job that writes Iceberg in upsert mode with exactly-once effect on committed state, and a serving job that writes the ClickHouse `ReplacingMergeTree` copies.

The two jobs handle reordering differently, and that is the point. Iceberg's upsert sink is last-write-wins on arrival, so the ingestion job needs the LSN operator to make arrival order equal LSN order. `ReplacingMergeTree` is version-aware and keeps the highest version on merge, so the serving job needs no operator: the engine carries convergence, exactly as the serving layer records.

## Considered options

- **One job with two sinks.** Rejected: a ClickHouse failure fails the job and stops ingestion, which is the coupling the decision exists to remove.
- **One job with the ClickHouse sink wrapped in a dead-letter path.** Rejected: it silently drops records and gives up the at-least-once guarantee the `ReplacingMergeTree` copy relies on.

## Consequences

The `streaming` profile carries a second job. The serving job is the light one, since it holds no keyed state and only maps the changelog onto rows carrying the LSN version and a soft-delete flag. The reconciliation asset that compares the two stores is the evidence that the serving copy converged. Matrix rows M7, M8 and M12. Rests on ADR-0012.
