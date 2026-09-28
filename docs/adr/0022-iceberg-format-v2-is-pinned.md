# Iceberg format v2 is pinned, and v3 is a reviewed gap

**Status:** accepted

The gold tables are Iceberg format v2. The reason is the serving reader, not Iceberg: ClickHouse 26.8 LTS, the pinned version, cannot read v3 deletion vectors, and read support only reaches an LTS in 27.3 (March 2027). The CDC facts are merge-on-read, so a v3 fact would break the read-through arm. The consequence is that `add-required-with-default` cannot be demonstrated at the schema level, because column defaults are v3-only, and the matrix records that as an honest gap with the add-optional, backfill, contract-invariant workaround.

## Considered options

- **Move every table to v3 and bump ClickHouse to 26.10.** Rejected for now: 26.10 is not yet published and is not LTS, and the one-way upgrade cannot be reverted.
- **Split, with the Spark-written tables on v3.** Deferred: it is a real option, but the serving-engine and Flink questions belong to the v3 stack review, not here.

## Consequences

The vague reason previously recorded in `docs/streaming-jobs.md` is corrected to the ClickHouse version constraint. The full-v3 question is owned by [the v3 stack review](https://github.com/SoongGuanLeong/de-platform/issues/22). Evidence: ticket [Data contracts and schema compatibility policy](https://github.com/SoongGuanLeong/de-platform/issues/15).
