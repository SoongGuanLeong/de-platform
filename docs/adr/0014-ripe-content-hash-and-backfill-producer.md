# Key the RIPE Atlas stream by a content hash, with REST replay as a backfill producer

**Status:** accepted

The RIPE Atlas live feed is at-most-once: the server buffers results and, when a client falls behind, drops messages with a single warning and no redelivery. The reliable path is the REST results endpoint, which returns a window by start and stop time. RIPE documents no unique result key: `timestamp` is one-second resolution, and a probe buffers results while disconnected and uploads them on reconnect, so `(msm_id, prb_id, timestamp)` is not unique. Idempotency is therefore engineered, not found.

The stream upserts results keyed by `result_id`, a hash over the stable measurement content only: `msm_id`, `prb_id`, `timestamp`, `sent`, `rcvd`, `dup`, and the ordered per-packet RTT or error list. Backend-enriched fields that can differ between live delivery and REST backfill, such as `from`, `src_addr`, `msm_name` and `lts`, are deliberately excluded from the hash; including them would reintroduce the duplication the hash exists to remove. The REST replay is a producer into the same Kafka topic rather than a second writer to the table, so one job writes the table and the overlap between live and backfilled results collapses on the key.

The table is Iceberg format version 2 in merge-on-read upsert mode, partitioned by `days(measurement_ts)`, with identifier field `result_id` and equality fields `{result_id, measurement_ts}`. The partition source column has to be an equality field, which is why `measurement_ts` joins the key. Partitioning on ingest time instead would force the ingest timestamp into the key, and a result re-delivered by REST at a later time would then be a new row rather than an update.

## Considered options

- **Append-only, with a batch MERGE to deduplicate by the content hash.** Rejected: it leaves a duplicate window in the table until the batch job runs and introduces a second writer for a stream whose whole defect is duplication.
- **Use `(msm_id, prb_id, timestamp)` as the natural key.** Rejected: not unique at one-second resolution, and not stable when a probe uploads buffered results late.
- **Partition by ingest time.** Rejected: it makes a REST-backfilled result a new row and breaks idempotency.

## Consequences

The windowed aggregate is keyed the same way, on its window and probe, so replay converges. Records whose clock is unsynchronised (`lts == -1`) and records past the watermark go to a side output, so the publisher's documented disorder is routed and counted rather than averaged into a result. The content hash is ours to keep stable: changing its inputs is a change to the idempotency key. Matrix rows M2, M3 and M13.
