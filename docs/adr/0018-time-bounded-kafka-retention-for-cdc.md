# Time-bounded Kafka retention for CDC, not compaction

**Status:** accepted

The CDC topics are time-bounded, not log-compacted. The platform demonstrates replay, out-of-order arrival and NULL-to-value transitions, and every one of those cases needs the historical events in the topic. Log compaction retains only the latest record per key, so a compacted topic cannot feed the replay tests the M2 row commits to. This corrects the size-budget line in `docs/dataset-selection.md`, which said Kafka retention was "bounded and compacted".

## Considered options

- **Compacted CDC topics.** Rejected: convergence would still hold, because last-write-wins is idempotent and a compacted replay lands the same final state, but the out-of-order and NULL-to-value cases would lose the events that make them testable, which is the point of choosing TPC-C at all.
- **Time-bounded with a short window.** Rejected: the window must be long enough to replay a partition from offset 0, which is what M2's idempotence test does.
- **Unbounded retention.** Rejected: it breaks the declared disk budget.

## Consequences

The RIPE Atlas topic stays time- and size-bounded, since it is an event stream rather than keyed state. The CDC retention window is a budget declared before the replay test measures against it. Evidence: ticket [Governance and data-quality specifics](https://github.com/SoongGuanLeong/de-platform/issues/14).
