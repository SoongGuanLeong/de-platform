# Rollback restores the Iceberg table only

**Status:** accepted

Rollback is `CALL iceberg.system.rollback_to_snapshot(...)` on one gold table, verified by the persona query returning its pre-change oracle value. It restores the table's data only. It does not propagate to the ClickHouse serving copy, which must be re-materialised, and it does not restore the schema, because field deletion cannot be rolled back unless the field was nullable or the snapshot is unchanged.

## Consequences

Rollback is the manual form of the branch fast-forward that [ADR-0016](0016-gate-on-input-and-promote-through-a-branch.md) uses to promote a batch, and both define "the previous good state" as the last snapshot whose persona queries returned their oracle values, so the two cannot drift. The runbook carries the re-materialisation step. Evidence: ticket [Data contracts and schema compatibility policy](https://github.com/SoongGuanLeong/de-platform/issues/15).
