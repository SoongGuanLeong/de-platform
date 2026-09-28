# Governance and data quality: checks, gates, namespaces, retention and PII

**Ticket:** [Governance and data-quality specifics: checks, gates, namespaces and retention](https://github.com/SoongGuanLeong/de-platform/issues/14)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Target posting:** ONL Biz Solutions, Senior Data Engineer - Data Lakehouse ([JobStreet 94703893](https://my.jobstreet.com/job/94703893)), cached verbatim at `~/projects/career-ops/data/jd-cache/031.md`.
**Decision records:** [ADR-0016](adr/0016-gate-on-input-and-promote-through-a-branch.md), [ADR-0017](adr/0017-minimise-pii-rather-than-mask-it.md), [ADR-0018](adr/0018-time-bounded-kafka-retention-for-cdc.md).

---

## 1. What this document is

The concrete shape of the platform's governance and data-quality layer: the check taxonomy and severity model, the gate that turns a severity into a pipeline consequence, the quarantine contract, the namespace and role layout, the retention policy per data class, and the PII inventory with its treatment. It resolves [the governance and data-quality ticket](https://github.com/SoongGuanLeong/de-platform/issues/14) on the map.

It is a design, not a result. Nothing here has been measured, and no check count, threshold, row count or quarantine count appears. Every threshold is deferred to `docs/budgets.yaml` and committed before the measurement it judges.

The checks' subjects are the two sources with publisher-documented defects, ONSPD and RIPE Atlas. TPC-C's 1 percent rollbacks and its `s_quantity` wrap are designed behaviours by specification and are never presented as defects, and a fault the incident laboratory injects is labelled as injected, never as a property of a source.

## 2. The check taxonomy and the severity model

A check is one assertion over data with a stable id, a kind, a subject, a severity and, where it has one, a threshold. Five kinds.

| Kind | What it asserts | Platform subject |
|---|---|---|
| `schema` | The shape of landed data: required columns, types, compatibility | The Apicurio-registered CDC schema against the topic payload |
| `record` | One row's values: null rate, uniqueness, ranges, referential integrity | The TPC-C composite primary key is unique after the merge |
| `pipeline` | The movement of data: reconciliation, freshness, completeness, late data | Source-to-target count by primary key; measurement freshness |
| `business` | A claim about the data's meaning | Stock-out risk is non-negative; a postcode resolves to an area |
| `source` | A publisher-documented defect | ONSPD straddling; the RIPE `-1` sentinel |

The `source` kind exists so that a check catching a defect the publisher documents is a different claim from one catching a fault we injected, which is what `docs/dataset-selection.md` section 8 requires.

**Severity is declared on each check instance**, with the kind carrying a default the instance may override, recorded. Kind-level severity alone cannot express the real cases: the same `record` kind is a `warn` on a nullable dimension attribute and a `fail` on a primary key. Three severities, one action each.

| Severity | Action |
|---|---|
| `warn` | Record the result and emit the metric. The run continues and no rows are diverted. Alerts only on a budget breach. |
| `quarantine` | Divert the offending rows to `platform.quarantine`, continue with the clean rows, record the count. The asset still succeeds. A quarantine-count budget breach escalates to `fail`. |
| `fail` | Fail the asset. Its output is not published and downstream assets do not start. Alerts immediately. |

Escalation is deterministic: the only path from `quarantine` to `fail` is a declared quarantine-count budget breach, and no severity changes with history. Every thresholded check cites a budget id committed in `docs/budgets.yaml` before the run; an existence or type check needs no threshold.

**Placement rule**, not the full catalogue. The enumerated catalogue is an implementation artefact the completion bar requires, not a decision this ticket holds. Every gold table carries `schema`, `record` and `pipeline` checks; `business` checks are named in that table's contract; `source` checks attach to ONSPD and RIPE Atlas, the two sources with real defects.

## 3. The gate

The gate is a Dagster `@asset_check`, never a log side effect, and the check framework behind it stays a pure function: it returns the offending rows and a reason, and the asset performs the write.

**Batch.** Placement splits by where a check can be evaluated.

- A check evaluable on the **input** (the `schema`, `record` and `pipeline` kinds on landed or staged data) is placed on the **upstream** asset. A `fail` means the downstream asset never starts, so no publish problem exists.
- A check evaluable only on the **output** (the `business` kind, and cross-path agreement) uses **branch and promote**: the asset writes to an Iceberg branch, the check runs against the branch, and a promote step fast-forwards `main` only on pass. On `fail` the branch is discarded and `main`, hence gold, is unchanged.
- The write-then-mark-failed pattern is never used, because it violates the severity contract above.

The gate boundary is every layer edge (bronze to silver, silver to gold), with the gold contract check the one that must never be bypassed. "A critical failure blocks the downstream Dagster run" is proven by the downstream run not starting in the run graph.

**Streaming.** There is no Dagster run to stop, so `fail` is expressed differently. A `quarantine` severity sends the record to a Flink side output feeding the quarantine sink. A `fail` sends it to a dead-letter sink and alerts. If a DQ breach persists past a declared window, a **Dagster sensor takes a savepoint and stops the Flink job**, which is the boundary operation Dagster already owns. The persistence window is a budget. The CDC path's checks are structural (LSN present, key present, payload parseable), and a `fail` there is a pipeline defect on the same sensor path.

## 4. The quarantine contract

Location is `platform.quarantine` in Iceberg, a control-plane table in the engineer-only namespace. One table, not one per source: quarantined rows are heterogeneous, so typing them per source multiplies tables without adding a checkable claim.

| Column | Purpose |
|---|---|
| `_quarantined_at` | Fixed by the completion bar. When the row was diverted. |
| `_check_id` | Fixed by the completion bar. Which check caught it. |
| `_reason` | Fixed by the completion bar. The human-readable cause. |
| `_source_table` | Provenance: which table the row was destined for. |
| `_source_layer` | Provenance: bronze, silver or gold. |
| `_record_key` | The offending row's business key, so the payload stays joinable. |
| `_record` | The offending row as JSON, so the payload stays complete. |
| `_severity` | The severity that diverted it. |
| `_run_id` | The run that diverted it. |
| `_source_snapshot_id` or `_source_lsn` | The provenance token, on the batch and CDC paths respectively. |

**Append-only, keyed by `_run_id`.** A re-run appends a new set rather than overwriting, because quarantine is an audit log. M14's no-double-counting guarantee applies to gold, not to this log, and the assertion is scoped per run.

**The gold-unchanged assertion** is three claims, not one: the quarantine count is greater than zero, the specific corrupted keys are absent from gold, and on a `fail` the gold table's snapshot id is unchanged.

**Retention correction.** Iceberg has no TTL, so control-data retention is a scheduled `DELETE FROM platform.quarantine WHERE _quarantined_at < now() - interval` plus snapshot expiry, owned by a Dagster retention asset. Snapshot expiry alone reclaims snapshots, never rows.

**Check results** live in PostgreSQL, the operational database, as `dq.check_result` keyed by `(run_id, check_id)` with severity, status, observed value, `threshold_ref` and timestamp. The check framework writes the row; the `@asset_check` reads it to decide. One write, one source of truth, and the gate and the queryable row are the same event.

**The false-positive rate is measured only over fault-detection checks.** RIPE's sentinels and ONSPD's straddling legitimately fire a check on real data, which is the data-quality story working. So the rate is the count of `quarantine` or `fail` results over N consecutive clean runs divided by the total check-runs, with N declared in budgets first, and **`source` checks are excluded from the rate by design**, with the exclusion stated.

## 5. Namespaces and roles

Polaris is spine-then-layer, because the spine is the unit of justification and the two licence obligations are per-spine, and because a per-spine grant under a layer-first layout would touch every layer.

| Polaris namespace | Holds |
|---|---|
| `commerce.bronze`, `commerce.silver`, `commerce.gold` | The TPC-C and TPC-H tables |
| `network.bronze`, `network.silver`, `network.gold` | The RIPE Atlas and ONSPD tables |
| `platform` | Control-plane tables: quarantine and any control state |

ClickHouse mirrors the serving domains, with the read-through arm separated and the control plane named.

| ClickHouse database | Holds |
|---|---|
| `commerce` | The P1 and P3 MergeTree serving copies |
| `network` | The P2 MergeTree serving copies and the rollup |
| `governance` | The quarantine view and the DQ result view |
| `lakehouse` | The `DataLakeCatalog` read-through arm, one database per catalog namespace |

Column-level grants and row policies exist **only in ClickHouse**, because Polaris enforces neither (ADR-0004).

| Principal | Scope |
|---|---|
| `engineer` | All namespaces, all columns, including PII |
| `svc_platform` | Write silver and gold on both spines |
| `analyst_commercial` | `commerce.gold` and the ClickHouse `commerce` database |
| `analyst_network` | `network.gold` and the ClickHouse `network` database |
| `analyst_ops` | The CDC serving facts, under the row policy |
| `analyst_ops_wh1` | The CDC serving facts, rows with `w_id = 1` only |
| `dq_reader` | `platform` quarantine and `dq.check_result` |

**One row policy**, `analyst_ops_wh1` restricted to `w_id = 1` on the CDC serving facts, demonstrated from both sides: the allowed rows are returned and other warehouses' rows are absent. The TPC-H and network tables carry no row policy, because C1 to C3 are asserted against TPC-H's published answers and a per-principal row filter would make the oracle return different answers for different users.

## 6. Retention per data class

Three mechanisms are in play and are not interchangeable: Kafka topic retention drops whole records, Iceberg snapshot expiry drops snapshots but never current rows, and a ClickHouse TTL drops rows.

| Data class | Source | Kafka | Iceberg | ClickHouse |
|---|---|---|---|---|
| Static oracle | TPC-H | n/a | Rows never expire; snapshots expire with benchmark snapshots **tagged** | No TTL |
| Live OLTP mirror | TPC-C | CDC topic time-bounded | Full history retained; snapshots expire | 365 days on the CDC facts |
| Reference SCD2 | ONSPD | n/a | All releases retained; snapshots expire | No TTL |
| Live capture | RIPE Atlas | Time- and size-bounded | The bounded capture retained whole | 90 days raw; the rollup carries the longer trend |
| Control | Quarantine, check results | n/a | Quarantine 30 days; check results per the operational window | n/a |

**The Kafka correction (ADR-0018).** CDC topics are **time-bounded, not compacted**. The platform demonstrates replay, out-of-order arrival and NULL-to-value transitions, all of which require the historical events, and log compaction retains only the latest record per key. This corrects the size-budget line in `docs/dataset-selection.md`, which said "bounded and compacted". The RIPE topic stays time- and size-bounded.

**Three data classes and their distinctions.** ONSPD terminations are **retained as history**, not deleted: `DOTERM` non-null sets `valid_to`, and that row is exactly what the N2 query reads, so the row's retention semantics are its `valid_to`, not a TTL. TPC-C's `NEW_ORDER` is transient **by design**: Delivery deletes the row, Iceberg carries the delete and the serving copy carries a tombstone with a soft-delete flag, and retention never resurrects it. The RIPE Atlas capture is a bounded, reproducible 24-hour window, so Iceberg retains it whole and the ClickHouse TTLs shape only the serving copy.

**The erasure window.** Iceberg snapshot expiry reclaims snapshots, never current rows, so a row deletion is not complete until the snapshots containing it expire. The PII-bearing tables therefore carry a **shorter snapshot retention than the analytical gold tables**, which bounds the erasure window. Retention on a PII table is effectively the erasure SLA, and that is a policy choice, not a technical limit.

## 7. PII: the inventory, the treatment and the deletion path

**Classification lives in the gold contract files**, as a per-column field, not in a separate register. The completion bar already gives one contract per gold table with columns, types and nullability, and CI already fails on a schema break, so a new column cannot be added without classifying it. A separate register can drift from the schema; the contract cannot.

The treatment is **minimisation first, masking second** (ADR-0017): a direct PII column that no query needs is dropped from gold, not masked in it. The nine queries in `docs/serving-layer.md` need `probe_id`, the resolved postcode area, RTT and ASN, and the TPC-C business keys and amounts. None needs a name, an address, a phone or a probe IP.

| Source | Columns | Class | Treatment |
|---|---|---|---|
| TPC-C `CUSTOMER` | `c_first`, `c_middle`, `c_last` | direct | Dropped from gold; silver only |
| TPC-C `CUSTOMER` | `c_street_1`, `c_street_2`, `c_city`, `c_state`, `c_zip` | direct | Dropped from gold; silver only |
| TPC-C `CUSTOMER` | `c_phone` | direct | Dropped from gold; silver only; the column-level grant test |
| TPC-C `CUSTOMER` | `c_credit`, `c_credit_lim`, `c_data` | financial, free text | Dropped from gold; silver only |
| TPC-C `HISTORY` | `h_data` | free text | Silver only |
| TPC-H `CUSTOMER` | `c_name`, `c_address`, `c_phone`, `c_comment` | direct, free text | Dropped from the serving copy of `dim_customer` |
| RIPE Atlas probe | hostname, fqdn, description | direct | Dropped from gold; `probe_id` retained |
| RIPE Atlas probe | IPv4, IPv6 | direct | Dropped from gold |
| RIPE Atlas probe | coordinates | quasi | Dropped from gold; the resolved postcode area is retained |
| RIPE Atlas probe | ASN | quasi | Retained |
| ONSPD | postcode, coordinates | not PII | Retained |

**ONSPD is not classified as PII, and the reason is recorded rather than assumed.** A postcode identifies a location, not a natural person, ONSPD's coordinates are property centroids rather than an individual's address, and this platform holds no join from a postcode to an individual. The Northern Ireland `BT` subset is excluded at ingest for licence reasons (ADR-0009), independent of any PII question.

**Enforcement matrix**, each denial paired with its allowed counterpart so the refusal is attributable to the grant rather than to a missing object.

| Path | Principal | Object | Expected |
|---|---|---|---|
| Polaris, Iceberg and Spark | `analyst_commercial` | `commerce.silver.customer` | Denied at table level; audited in Polaris |
| ClickHouse | `analyst_ops` | `SELECT(c_phone)` on the one exposed column | Denied at column level; audited in ClickHouse |
| ClickHouse | `analyst_ops_wh1` | Rows with `w_id != 1` on the CDC facts | Absent by row policy |
| ClickHouse | `engineer` | The same column | Allowed |

**The deletion path and the erasure definition of done.** The path runs on the TPC-C `CUSTOMER` table: a source deletion becomes a Debezium `op=d`, lands in Iceberg through the Flink upsert sink, and is applied as a `MERGE ... WHEN MATCHED THEN DELETE`. The serving CDC facts do **not** carry `c_id`, so the path terminates in Iceberg and the ClickHouse side is a documented absence rather than a second deletion to prove. Erasure is complete when three things hold: the current snapshot no longer returns the key, no serving copy holds a reference to it, and the historical snapshots containing it have expired at T plus the retention window, asserted by the retention dry run.

**The quarantine table is itself PII-bearing and licence-sensitive**, which follows from the decisions above rather than being a separate choice. The `_record` payload is the rejected row, so a quarantined customer row carries a name and a phone. Three rules follow: quarantine access is `engineer` and `dq_reader` only and never the analysts; its retention is the shortest of any class, 30 days, because holding PII is the reason; and the `BT` exclusion filter runs **before any check sees the row**, so a licence-restricted row never reaches a quarantine payload. The deletion path covers quarantine as well, and the 30-day retention bounds the residue in the same way snapshot retention bounds the Iceberg residue.

## 8. The DQ signal set

Five signals, all derived from `dq.check_result` and the quarantine table, feeding the M15 dashboard.

| Signal | What it catches |
|---|---|
| `dq_checks_passed_total`, `dq_checks_failed_total` by severity | The pass rate |
| `dq_quarantine_rows_total` by source table | The quarantine count |
| `dq_check_duration_seconds` | A check that has become expensive |
| `dq_last_successful_check_timestamp` by gold table | **A gate that stopped running** |
| `dq_source_hazard_fires_total` | Source-hazard fires, labelled apart from fault-detection fires |

One alert rule per SLO, and `fail` alerts immediately. The last-successful-check timestamp is the signal that matters most, because a green dashboard over a gate that silently stopped executing is exactly the failure the completion bar's signal-versus-behaviour rule exists to catch.

## 9. Named constraints

1. **No cross-domain join.** Nothing joins the commerce spine to the network spine (ADR-0008), so no check and no namespace spans them.
2. **Polaris enforces no column-level or row-level access** (ADR-0004), so every column-level and row-level claim in this document is ClickHouse-only.
3. **The quarantine payload is PII-bearing**, so its access and retention are the tightest in the platform.
4. **The `BT` exclusion runs before DQ**, so no licence-restricted row reaches a quarantine payload.
5. **Nothing here is measured.** Every severity, threshold, window and retention figure is a baseline or a policy to be exercised during implementation.
6. **The check catalogue is implementation, not this ticket.** This document fixes the taxonomy, the severity model and the placement rule.

## 10. Open items

- **The enumerated check catalogue**, with each check's id, kind, subject and severity. An implementation artefact the completion bar requires.
- **The per-check budgets**: N for the false-positive rate, the quarantine-count escalation threshold, and the streaming DQ persistence window.
- **The row policy's warehouse set.** One warehouse is demonstrated; whether the operations persona is split per warehouse or held at one is settled by whether a second warehouse-scoped principal earns its place.

---

*Resolved by [the governance and data-quality ticket](https://github.com/SoongGuanLeong/de-platform/issues/14) on [the map](https://github.com/SoongGuanLeong/de-platform/issues/9). Inputs: [`docs/requirements-matrix.md`](requirements-matrix.md), [`docs/completion-bar.md`](completion-bar.md), [`docs/serving-layer.md`](serving-layer.md), [`docs/dataset-selection.md`](dataset-selection.md), [`docs/technology-selection.md`](technology-selection.md), [`docs/incident-laboratory.md`](incident-laboratory.md), [`docs/adr/0004`](adr/0004-authorisation-seam-between-catalog-and-engine.md), [`docs/adr/0008`](adr/0008-two-spines-with-no-cross-domain-join.md), [`docs/adr/0009`](adr/0009-dataset-licence-position-and-obligations.md).*
