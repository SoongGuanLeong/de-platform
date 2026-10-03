---
id: lsn-operator-unit-test-mutation-note
capability: lsn-operator-unit-test
matrix_rows:
  - M21
claim: The keyed LSN operator holds the maximum source.lsn seen per key and forwards a record only when its LSN is not strictly less than that maximum.
proves: signal
command: bash deployment/scripts/run-java-tests.sh
profile: streaming
commit: a52e485
date: 2026-10-03
mutation_note: Removed the "if (seen != null && lsn < seen) return;" staleness comparison from LsnMaxOperator.processElement; LsnMaxOperatorTest then failed 3 of its 4 tests.
artifact: docs/evidence/flink-streaming/lsn-operator-unit-test/raw/mutation-removed-staleness-rule.txt
---

# The LSN operator's unit test and its mutation note

The keyed LSN operator is the stateful Java component the CDC ingestion job runs between the Kafka source and the Iceberg sink (ADR-0013). The sink's upsert path does not compare versions, so a reordered stale event would reinstate a superseded row; the operator makes the stream reaching the sink LSN-monotonic per key, which is what makes the sink's last-write-wins coincide with highest-LSN-wins. This item records the unit test that proves the operator's own rule, and the mutation that shows the test is load-bearing.

## The seam

The test is at the operator's output seam, under Flink's own harness. `LsnMaxOperatorTest` drives a `KeyedOneInputStreamOperatorTestHarness<String, LsnRecord, LsnRecord>` and asserts on `extractOutputValues()`; it reaches into no private state and asserts on no internal field. The operator is keyed by the business key, so the harness, not the test, owns the keyed-state backend, which is the same mechanism the job uses.

Four behaviours are asserted, all per key:

1. The maximum LSN is held and a strictly stale record is dropped. A key sees LSN 10, then 5, then 20, then 15; only 10 and 20 are forwarded.
2. The maximum is held rather than the last-seen LSN. A key sees 20, then 10, then 15; only 20 is forwarded, so a mid-range LSN after a lower one is still dropped.
3. An equal LSN is not strictly stale. A key sees LSN 7 twice and both are forwarded, because ADR-0013 drops only the *strictly* less. Collapsing equal LSNs within a commit is the source changelog deduplication's job, which complements the operator rather than replacing it.
4. Keys are independent. One key's maximum drops only its own stale record.

## The mutation

The `mutation_note` records what was removed. The staleness comparison `if (seen != null && lsn < seen) return;` was deleted from `LsnMaxOperator.processElement`, the operator was rebuilt and the suite re-run with `--rerun-tasks`, and 3 of the 4 tests failed. The raw output is committed at the `artifact` path. The behaviour is therefore falsifiable in the register's sense (docs/completion-bar.md section 3, core item 2): removing it fails the test, and the test is cited by a command that resolves.

## Level and the profile field

This is a unit test (docs/testing-strategy.md section 2): it runs against the distribution's own code with no container and no network, so it may carry a `signal` item and may not carry a `behaviour` item. The CI java job runs it on every change under `streaming/` (docs/ci-cd-strategy.md section 5), which is what makes the cited command resolve.

The item is produced by the CI java job, not by a profile run, and the register schema has no profile value for a CI-only test. The `profile` field names the streaming path the operator belongs to. This is a recorded limitation of the evidence schema rather than a claim that a `streaming`-profile run produced the artifact; the claim is `signal`, so the profile is not load-bearing for it. The test that would close the gap is a `streaming`-profile run of the CDC job at Phase 5, which is the point at which the class's representative evidence item and its profile-scoped behaviour claims land.
