# 01b - Datasets that force real streaming engineering

Angle: high-volume event, clickstream, time-series and genuinely streaming sources.

Target posting: ONL Biz Solutions - Senior Data Engineer, Data Lakehouse (cached verbatim at
`~/projects/career-ops/data/jd-cache/031.md`, job 94703893).

Local budget: 12 CPU, 14 GB RAM total with roughly 7-8 GB free, **231 GB free disk**
(`/dev/nvme1n1p3`, 439G total, 185G used, 231G avail, measured 2026-09-27).

All volume figures below were measured with `curl -I` against the publisher's own object store or
CDN on 2026-09-27, not recalled. All licence claims are quoted or paraphrased from the publisher's
own terms page or repository, not from third-party summaries. Where a publisher contradicts itself,
the contradiction is reported rather than resolved.

## The honesty rule used throughout

The single most important filter for this angle was: **is the disorder a property of the source, or
would we have to manufacture it?** Many datasets marketed as "event data" are tidy aggregates with a
single timestamp per row and no arrival time, which makes watermarks, deduplication and out-of-order
handling pure fiction. Every candidate below is graded on that axis explicitly:

- **REAL disorder** - lateness, duplication, revision or out-of-order arrival is documented by the
  publisher or observable in the payload itself.
- **PARTLY REAL** - the source has genuine irregularity, but a specific sub-property is absent.
- **TIDY** - one row per already-aggregated fact with one timestamp. Streaming problems would have to
  be injected. Reported so we can avoid it.

## Discovery sources used

`awesomedata/awesome-public-datasets` (and its Stanford Geospatial mirror), `sindresorhus/awesome`
Big Data, plus the streaming-specific lists that the general lists do not cover:
`bytewax/awesome-public-real-time-datasets`, `ColinEberhardt/awesome-public-streaming-datasets`,
`apgiorgi/awesome-streaming-data-sources`. Those three were the productive ones for this angle; the
general "public datasets" lists are overwhelmingly static snapshots and contributed almost nothing
that survives the disorder test.

---

## Candidates

### 1. RIPE Atlas measurement results

```
Dataset
RIPE Atlas measurement results: active network measurements from volunteer probes
(ping, traceroute, DNS, NTP, HTTP, TLS certificate) run against public targets.

Source and URL
https://atlas.ripe.net/  (REST API v2)
https://atlas-stream.ripe.net/stream/  (live stream: WebSocket or chunked HTTP GET)
Stream API documented at https://atlas.ripe.net/docs/apis/streaming-api/
Service terms: https://atlas.ripe.net/assets/legal/RIPEAtlasServiceTermsandConditionsV2.0.pdf
Live payload confirmed 2026-09-27 by direct read from atlas-stream.ripe.net.

Licence (and whether it permits our use)
Permissive for a portfolio, with a real carve-out. RIPE Atlas Service Terms V2.0, section 3.1:
the service is "a measurement platform for purposes such as research, network monitoring, network
debugging and alerting". Section 5.3: "Users may perform research using RIPE Atlas Data, and they
can notify the RIPE NCC about the results of this research". The constraint: "Any commercial use of
the RIPE Atlas Data is subject to prior permission by the RIPE NCC." Section 5.5 additionally
permits RIPE to "provide RIPE Atlas Data and analysis ... to third parties for scientific and
statistical purposes" and states that this "may continue even after the RIPE Atlas Service is no
longer available" - useful for a longevity argument.
VERDICT: a public portfolio is non-commercial research, which is explicitly permitted. A portfolio
that is ever presented inside a commercial context, or monetised, needs written permission. Record
this in the ADR rather than ignoring it. No CC-BY/SA tagging obligation, no copyleft.

Volume, format, growth rate
JSON, newline-delimited, one JSON object per line, already in the shape a Kafka producer wants.
Measured live 2026-09-27: 15,164 connected probes; 199,142,482 public measurements to date. The
result rate is roughly (connected probes) x (measurements per probe) x (packets per measurement),
which for the default Atlas 1,000-probe measurements at 5-15 minute cadence puts steady-state
result throughput in the tens of thousands of lines per second and easily over 100 million rows per
day across the whole platform. Local sample is therefore a *sampled* slice, never the full firehose.
Growth is upward and monotonic in probe count.

Live/append-incrementally-published, or static snapshot
LIVE. Two independent surfaces:
- Streaming: `wss://atlas-stream.ripe.net/stream/`, subscribe with an `atlas_subscribe` message
  carrying `streamType` in {`result`, `metadata`, `probestatus`}. `result` streams measurement
  results, `metadata` emits the measurement specification every time a measurement is created or
  edited, `probestatus` emits probe connect/disconnect events. Filterable by `prb`, `msm`, `type`
  (ping/traceroute/dns/ssl/http/ntp), `sourceAddress`, `destinationAddress`, `enrichProbes`.
- Replay/backfill: `sendBacklog` fetches "the last few minutes of results before streaming", and the
  REST API serves historical results. This is the decisive property for a portfolio: the pipeline
  can be replayed from a fixed measurement id, so a demo is reproducible at 10am on a Tuesday.

Access mechanism: API, bulk download, subscription; rate limits and automation
No API key for public data. WebSocket or plain HTTP GET (the HTTP form auto-closes after 60 seconds
of inactivity, so use WebSocket for anything long-lived). Practical limits found in the primary
sources: a **16 concurrent WebSocket connection limit per client IP** (RIPE Atlas mailing list,
Chris Petchan, Jan 2025) with the explicit advice to multiplex multiple subscriptions onto one
socket rather than opening more sockets, because unbounded sockets have previously taken the service
down. Subscribe with `?client=<your-identifier>` so RIPE can debug your usage. Because the per-socket
concurrency is low and the backlog is small, the sane design is one well-behaved producer process
that fans out into local Kafka rather than many consumers. Some use cases also exist as pre-packaged
Kafka/Spark readers, but a hand-rolled producer is about 50 lines and is more explainable.

Event-time semantics: timestamp fields, timezone behaviour
`timestamp` is epoch seconds (UTC) of the measurement result as recorded by the probe. The live
payload observed 2026-09-27 carries `"timestamp":1790487623` and also `step` (which repetition of
the measurement this is), `fw` (Atlas firmware build), `mver` (measurement version), `lts` (last
timestamp seen), `from` (probe hostname). Critically, `timestamp` is the **probe's** clock, not
RIPE's. There is no ingest timestamp in the payload at all, so any "how late was this relative to
us" reasoning has to add its own ingest time in the producer. UTC throughout, no local timezones.

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
REAL, and this is the strongest candidate in the whole angle. Documented, not inferred:
- **Real clock skew and real lateness.** 15,164 probes are consumer routers and vServers on
  volunteer home networks, each with its own unsynchronised clock, uplink and power. Results
  timestamped T can be transmitted seconds to minutes after T, and the offset between probes
  measuring the same target is a genuine, unbounded, per-probe quantity.
- **Real out-of-order arrival.** Results are reported asynchronously as each probe finishes. A single
  measurement against 1,000 probes produces 1,000 results in a completion order that has nothing to
  do with timestamp order. Combined with per-probe clock skew you get a genuine watermark problem.
- **Real duplicates and real loss at the packet level.** The payload has explicit `sent`, `rcvd` and
  **`dup`** fields, and a `result` array holding one entry per packet. So duplicates and loss are
  first-class, in-band, not simulated. RIPE's own docs state that when every packet times out the
  min/max/avg are reported as **`-1`**, and individual packet results appear as `{"x": "*"}`
  (RIPE Atlas mailing list, Jan 2025) - sentinel values that a naive cast will turn into legitimate
  negative latencies. This is a real data-quality problem with a real fix.
- **Real at-most-once exposure.** The streaming docs state: "there is a limit to how much data will
  be buffered on the server if your script or connection is too slow to receive it all in real
  time." A slow consumer therefore silently loses data. `sendBacklog` exists to cover exactly this
  gap, and modelling "the stream can drop, so the pipeline must be replayable and idempotent" is a
  senior-level design conversation, not a coding exercise.
- **Real mid-measurement schema and target drift.** The `metadata` stream emits the measurement
  specification "every time a measurement is created or edited", so a measurement's type, target,
  packet count or interval can change while it is running. Late-joining consumers can see
  contradictory metadata for the same `msm_id`.
- **Real probe lifecycle churn.** `probestatus` emits probe connect and disconnect events, so the
  dimension table genuinely mutates under the fact table.

High-cardinality keys and likely partition skew
Extreme, and in two different directions, which is the interesting part.
- `prb_id` is ~15k distinct values - too many for a single Kafka partition to be efficient on its
  own, but a reasonable secondary key.
- `msm_id` is 199 million distinct values - this is a genuine high-cardinality key that will create
  a serious state-backend problem if used for windowing or deduplication in Flink.
- Skew is structural: the flagship measurements target the same 1,000 popular probes, so those
  measurements generate orders of magnitude more rows than the long tail. Partitioning by
  `dst_addr` gives textbook hot-key skew on `wikipedia.org` and `1.1.1.1`-class targets. This is a
  real, demonstrable skew case rather than a synthetic one.

Nested or semi-structured event payloads
Yes, and this is where the real modelling work is. A `ping` result is
`{"result":[{"rtt":94.42},{"rtt":94.49},{"rtt":94.33}],"dup":0,"rcvd":3,"sent":3,"min":...,
"max":...,"avg":...}` - a nested array whose **length varies with `sent`**, and whose elements can be
the `{"x":"*"}` sentinel. A `traceroute` result carries a nested array of hops, each with its own
`rtt` array, its own response and a possible `{"from":..., "rtt":...}` reply structure. `dns` and
`ssl` carry deeply nested answer structures. That is a genuine flattening-and-typing exercise for
nested types in Iceberg and a genuine reason to have a semi-structured/raw bronze layer in ClickHouse.

Windowed or time-series analytical questions it answers
- "Which of my monitored targets degraded in the last hour, and by how much?" - a 5-minute tumbling
  window over `avg` with a late-event allowance, which is where the watermark policy becomes visible.
- "What fraction of probes can reach a target from their own region?" - a real availability SLO
  metric, and genuinely useful to a platform team.
- "Did that incident start at the destination or on one probe's uplink?" - join a `traceroute`
  result against a `ping` result on `(msm_id, prb_id)`, which is a temporal join with genuinely
  out-of-order inputs.
- "What is the latency distribution, not the mean?" - p50/p95/p99 per target per window, which is the
  argument for not trusting the `-1` sentinels.

Expected engineering challenges it forces
Watermark strategy on a probe-sourced clock; idempotency keyed on a composite of `(prb_id, msm_id,
step, packet index)` because there is no natural event id; sentinel-value handling that must not be
silently averaged; fan-out skew mitigation (key by `dst_addr` for hot targets, or salting) so Flink
does not serialise on one hot key; a raw/bronze JSON layer in ClickHouse with a typed projection on
top; a multi-timestamp row (event time, probe-reported, ingest time) and an explicit late-arrival
policy; a live-to-replay parity test proving the same rows arrive either way; and a real alert on
consumer lag against a stream that can drop data.

Which target-job requirements it demonstrates
"Own, operate and harden the streaming platform for reliability, correctness, and cost at scale" -
directly and hard. "real-time streaming jobs in Flink, including partitioning, compaction, and
job/state tuning" - partitioning via real skew, state tuning via 199M-cardinality keys.
"Expert SQL ... and query performance tuning - including experience with an analytical/columnar store
(e.g. ClickHouse)" - nested JSON projection and quantile aggregation in ClickHouse.
"Design data models and physical table layout (partitioning, sort order, compaction, retention) to
balance write throughput, query performance, and storage cost" - directly exercised by
millions-per-window small files. "A production-reliability mindset: monitoring, alerting, on-call, and
incident root-cause analysis" - consumer-lag alerting plus a documented at-most-once source hazard.
"Proficiency in at least one of Python, Java, or Scala for pipeline and streaming code" - a Python
WebSocket producer plus Flink SQL.

Realistic local sample size and how we would scale up
Local: subscribe to a handful of `msm_id`s, or to `type=ping` for one well-known measurement, and
run continuously. A single 1,000-probe measurement at a 5-minute interval is about 200 result rows
per probe-visit, so 1,000 probes x 200 rows x 288 five-minute intervals is roughly 57 million rows
per day for that one measurement - far more than we need locally. Take 1 to 3 measurements, or
`prb`-filtered subscriptions, and a day of history from the REST API; that is tens of millions of
rows and a few GB of Parquet, which fits the 7-8 GB RAM working set if we never read it all at once.
For the benchmark: replay the full history of one 1,000-probe measurement through the REST API at
bounded concurrency to build a 50-100 GB Parquet/Iceberg lake, and state the row count and the
elapsed time we actually measured. Scale reasoning upward is written as reasoning, never as a
fabricated 10x claim.

Relationships to other candidate datasets
This is the natural streaming counterpart to a relational CDC source such as the Olist data covered
by angle 01a: Olist supplies Debezium-shaped inserts/updates/deletes, RIPE Atlas supplies genuinely
asynchronous event-time telemetry. They compose into one platform with two honestly different
ingestion shapes. It also pairs with a time-series source (Citi Bike or Meteostat) to show two very
different windowed-aggregation shapes: bursty network events versus regular telemetry.
```

### 2. Binance public market data

```
Dataset
Binance public market data: spot and USD-M/COIN-M futures trades, aggregated trades (aggTrades) and
klines (candlesticks) for every symbol, from 2020-01-01 to the present.

Source and URL
https://data.binance.vision/  (S3 bucket fronted by CloudFront, anonymous read)
Layout: /data/spot/{daily,monthly}/{trades,aggTrades,klines}/<SYMBOL>/<interval-or-nothing>/<FILE>.zip
Tooling and schema: https://github.com/binance/binance-public-data

Licence (and whether it permits our use)
MIT. The repository's own "## Licence" section states "MIT" with no non-commercial, share-alike or
field-of-use restriction and no attribution-on-publication condition beyond normal MIT practice.
VERDICT: the cleanest licence of any candidate in this report. No follow-up needed.

Volume, format, growth rate
CSV, no header, zipped, one row per trade / per aggTrade / per kline. Exact sizes measured with
`curl -I` on 2026-09-27:
- BTCUSDT monthly trades 2024-01: **678,484,620 bytes**
- BTCUSDT monthly trades 2020-01: **270,127,562 bytes**
- BTCUSDT monthly aggTrades 2024-01: **566,954,365 bytes**
- BTCUSDT monthly klines 1m 2024-01: **2,169,570 bytes**
- BTCUSDT monthly klines 1s 2024-01: **84,184,316 bytes**
- BTCUSDT daily trades 2026-09-24: 25,931,282 bytes; 2026-09-25: 22,966,188; 2026-09-26:
  9,135,690 (a partial day, published 2026-09-27 01:38 UTC)
Growth rate: BTCUSDT monthly trade volume grew from 270 MB to 678 MB between 2020-01 and 2024-01,
roughly 2.5x over four years, and daily volume has kept climbing since (compare the 2026 daily
figures above with the 2020 monthly average of 9 GB). Across ~2,000 active spot symbols the total
daily footprint is therefore enormous, and we choose which slice to take. Note the ratio that makes
this dataset interesting: raw trades are 313x the size of 1-minute klines for the same month, so we
can pick our own resolution and justify it by measured cost.

Live/append-incrementally-published, or static snapshot
Append-incrementally-published on a public object store, and this is the honest part of the answer:
**daily** files become available the next day, **monthly** files on the first Monday of the month.
So it is not a live tail, but it is a genuinely append-only object namespace that a Dagster asset or
a simple S3 `LIST` poll can tail for new keys, and the late arrival of the monthly rollup is itself a
lateness case. Each file has a sibling `.CHECKSUM` for integrity verification.

Access mechanism: API, bulk download, subscription; rate limits and automation
Anonymous HTTP GET on a CloudFront-fronted S3 bucket, no key, no auth. Fully automatable: the
repository ships `python/download-kline.py`, `download-trade.py` and `download-aggTrade.py` plus
shell equivalents, with `--startDate`/`--endDate`/symbol/year/month flags, so "download last 7 days
of BTCUSDT aggTrades" is one command. No published rate limit; it is a CDN so it is effectively
unthrottled, and politeness is a courtesy rather than a rule. Read from Kuala Lumpur, the bucket
resolved to the KUL CloudFront edge on 2026-09-27, so geo-restriction is not a concern for the data
even though the exchange restricts trading in some jurisdictions. There is also a live WebSocket
market stream if we ever want sub-second, but it is not needed for this use case.

Event-time semantics: timestamp fields, timezone behaviour
`trades`: `trade_id, price, qty, quote_qty, time, is_buyer_maker, is_best_match` with `time` in
**milliseconds** epoch.
`aggTrades`: `agg_trade_id, price, qty, first_trade_id, last_trade_id, timestamp, is_buyer_maker,
is_best_match` with `timestamp` in **milliseconds** epoch.
`klines`: `open_time, open, high, low, close, volume, close_time, quote_volume, trades,
taker_buy_base, taker_buy_quote, ignore`.
**A genuine, documented unit change:** the README states "The timestamp for SPOT Data from January
1st 2025 onwards will be in microseconds." So the same logical column changes unit partway through
the archive. Spot timestamps are UTC epoch integers, no local timezone anywhere. `time` is exchange
match time, which is authoritative and monotonic per symbol; the ingest time is whatever we stamp.

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
REAL, and the reasons are specific rather than assumed:
- **Real at-least-once / retroactive correction.** The README's "### Updates" section: "Archived
  files may be updated at a later date as a result of recently discovered issues. Below is an
  exhaustive list of updates performed to the archive, containing the file path for reference, and
  CHECKSUMs of the replaced file and the replacement file." Two real update events are listed
  (2022-08-08 kline fixes, 2022-04-21 aggregate-trade alignment to a spot API change). This is a
  genuine retraction-and-reissue stream: a file path is a stable key whose **content can change
  after you have already ingested it**, and the checksum changes with it. Polling the object store
  for changed ETags is a real, implementable late-correction pattern.
- **Real duplicates across the two granularities.** The same trade is published both as a `trades`
  row and as a member of an `aggTrades` group (`first_trade_id` to `last_trade_id` gives the exact
  span). Any pipeline that ingests both and naively unions them double counts. Deduplicating on
  `trade_id` is a genuine, non-injected requirement.
- **Real out-of-order arrival, at the file level.** Daily files are published per symbol, so symbol A's
  day-N file can be present while symbol B's day-N file is not, and the monthly rollup for month M
  lands on the first Monday of M+1, after the daily files for the whole of M. Arrival order is not
  event order.
- **Real out-of-order within a symbol, at rest.** The archive is not documented as globally sorted
  across symbols, and `aggTrades` interleaves within a symbol at sub-second granularity.
- **Real schema evolution.** The millisecond-to-microsecond change above is a silent, real, unit
  change in an untyped CSV column. It is exactly the class of bug that a gated data-quality check
  should catch, and it is present in the source rather than injected.

High-cardinality keys and likely partition skew
`trade_id` is unique per symbol and effectively uncorrelated with time. `price` is close to a
continuous uniform distribution and is the classic anti-partition key. Symbol is the natural key and
carries enormous **real** skew: BTCUSDT monthly trade volume is orders of magnitude above a typical
altcoin pair, so partitioning by symbol or by price produces a genuinely hot key. This is a
textbook, honest skew demo, and the fix (range-bucket the symbol, or key on a hashed symbol) is a real
layout decision with a measurable before-and-after.

Nested or semi-structured event payloads
Weak, and worth stating plainly: the files are flat delimited CSV with no nested structure and no
semi-structured fields. This is Binance's one genuine weakness as a candidate. Mitigation: pair it
with a genuinely nested source (RIPE Atlas, or Wikimedia parsedcomment HTML) so the lakehouse
demonstrates both flat high-volume and nested semi-structured ingestion. Do not pretend the CSV is
nested.

Windowed or time-series analytical questions it answers
- "What was the real volume, not the displayed volume?" - reconcile `trades` against `aggTrades`
  against `klines`; a genuine three-way data-quality and lineage problem.
- "How did realised volatility change in the hour after a given event?" - a 1-second or 1-minute
  tumbling window with a lateness allowance, on a stream where the 1s and 1m klines disagree during
  volatile periods.
- "Did that day of trades get restated after the fact?" - compare the daily file against the monthly
  rollup and surface the diff; this is a *correction* metric, and having one is unusual and credible.
- "What is the taker-buy imbalance per window per symbol?" - a real, standard market-microstructure
  question that falls straight out of `taker_buy_base` and `taker_buy_quote`.

Expected engineering challenges it forces
Watermark and allowed-lateness policy on a sub-second event-time source; idempotent ingest keyed on
`(symbol, trade_id)`; detection of and reaction to retroactive file replacement via ETag or checksum
change; a unit-change guard (ms vs us) enforced as a blocking data-quality check; three-way
reconciliation between trades, aggTrades and klines; skew-aware partitioning and sort order; and a
retention decision on how long to keep 1-second resolution versus rolling it up.

Which target-job requirements it demonstrates
"Batch transformations in Spark (silver/gold models) and real-time streaming jobs in Flink, including
partitioning, compaction, and job/state tuning" - both halves, in one dataset, with real numbers.
"Design data models and physical table layout (partitioning, sort order, compaction, retention) to
balance write throughput, query performance, and storage cost" - 1s versus 1m versus 1h klines is a
cost-versus-resolution trade we can quantify. "Establish and enforce data governance: ... automated
data-quality checks" - the checksum, unit-change and three-way-reconciliation checks are all real
checks that can actually gate a pipeline. "Cost optimization for cloud data/streaming platforms" -
daily-vs-monthly and 1s-vs-1m are direct storage and compute cost levers.

Realistic local sample size and how we would scale up
Local: aggTrades for BTCUSDT and ETHUSDT for a handful of days, which at roughly 500 MB per month for
BTCUSDT is about 16-17 MB per day, so 30 days for two symbols is around 1 GB compressed and a few GB
as Parquet. Add monthly 1s klines across a year of top-20 symbols (84 MB/month for one symbol at 1s,
so a few GB) for the long-horizon time-series story. Keep raw trades out of local dev entirely.
For the benchmark: pick one year of BTCUSDT aggTrades plus 1s klines, measure the on-disk Parquet
footprint and the Spark and Flink job wall-clock, and report the measured row count. Total Binance
history is far beyond 231 GB, so state explicitly which window was chosen and why.

Relationships to other candidate datasets
Binance is the volume and time-series spine; RIPE Atlas is the genuinely-live spine. They are
complementary rather than redundant: one is a high-throughput, well-ordered, well-documented,
cleanly-licensed bulk feed with real *corrections*; the other is a moderate-throughput, badly
ordered, loosely-licensed live feed with real *messiness*. Demonstrating both is more persuasive than
demonstrating either twice. Binance also supplies a natural slowly-changing dimension (symbol
metadata) and a natural business key (symbol pair) that other candidates in this angle lack.
```

### 3. Wikimedia EventStreams (recentchange, revision-create, page-create/delete/undelete)

```
Dataset
Live MediaWiki RecentChanges and page-lifecycle events from every public Wikimedia wiki, as a
Server-Sent Events firehose. Each event is a single page edit, page creation, page deletion or page
undeletion, with the editor, the size delta, the old and new revision ids, and the parsed comment
markup.

Source and URL
https://stream.wikimedia.org/v2/stream/recentchange
Also: /v2/stream/revision-create, /v2/stream/page-create, /v2/stream/page-delete,
/v2/stream/page-undelete
Format documented at https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams
Live payload confirmed 2026-09-27 by direct read from stream.wikimedia.org.

Licence (and whether it permits our use)
Mixed, and worth being careful. Wikimedia's own guidance states: "most content, data, and metadata
coming from Wikimedia projects are openly licensed ... The most common licenses used for Wikimedia
project data are Creative Commons Attribution (CC BY) or Creative Commons Attribution-ShareAlike
(CC BY-SA)" (Enterprise API best practices). Separately, "All Analytics datasets are available
under the Creative Commons CC0 dedication" (dumps.wikimedia.org/other/analytics/) - that CC0 covers
the aggregate *Analytics* datasets, not the RecentChanges feed. Treat the RecentChanges stream as
**CC BY-SA 4.0** (edit content, including the `parsedcomment` HTML and titles, is share-alike), and
keep the `parsedcomment` field out of anything we relicense.
VERDICT: CC BY-SA permits a non-commercial portfolio, but the share-alike term on derived content is
a real obligation that must be recorded. There is also a terms-of-service caveat, not a licence
caveat: "The public EventStreams service is intended for use by small scale external tool developers.
It should not be used to build production services within Wikimedia Foundation."

Volume, format, growth rate
JSON over SSE. Each SSE message carries an `id:` line containing the full Kafka coordinates - I
observed `"id": [{"topic":"eqiad.mediawiki.recentchange","partition":0,"timestamp":1790487705416},
{"topic":"codfw.mediawiki.recentchange","partition":0,"offset":-1}]` - and a `data:` line with the
event. Volume is continuous and unbounded per connection, in the range of tens of edits per second
across all wikis and rising over time. Per-event payload is roughly 1-3 KB because `parsedcomment`
embeds rendered HTML, so this is a *fat* event stream rather than a wide thin one, which is the
opposite skew from Binance and a genuinely different ingestion problem.

Live/append-incrementally-published, or static snapshot
LIVE, and the best-documented live interface of any candidate. SSE over chunked HTTP, resumable in
two ways: the standard `Last-Event-ID` request header, and a `since` query parameter that takes an
ISO-8601 timestamp for historical consumption, which per the Wikitech page was added in June 2026 -
"EventStreams supports timestamp based historical consumption". There is also a matching
hourly-file bulk stream on dumps.wikimedia.org, so a backfill path exists alongside the live path.

Access mechanism: API, bulk download, subscription; rate limits and automation
No key, no auth, plain `curl -N` or any EventSource client. Explicit operational limits, all
documented by WMF (EventStreams/Administration): "the public EventStreams stream.wikimedia.org
endpoint is configured in varnish to only allow for 25 concurrent connections per varnish backend",
with 10 text varnishes in codfw and 8 in eqiad, giving "a total of 450 concurrent connections" - and
the note that "We have had incidents where a rogue client spawns too many connections." Separately,
"WMF's HTTP connection termination layer enforces a connection timeout of 15 minutes", so a correct
client must implement automatic reconnect with `Last-Event-ID` resume or it will silently lose its
place. The MediaWiki API itself now also carries global rate limits, with anonymous requests "in
the hundreds per hour" - which is a reason to use EventStreams rather than polling the API.

Event-time semantics: timestamp fields, timezone behaviour
Two timestamps, which is exactly what we want. `meta.dt` is an ISO-8601 UTC string with milliseconds
(observed `"2026-09-27T05:41:45.415Z"`); `meta.timestamp` is epoch milliseconds
(observed `1790487705416`); `timestamp` is epoch seconds of the edit. The SSE `id:` line also carries
a per-topic millisecond timestamp, so a third event-time candidate exists. There is no ingest
timestamp from the publisher, so we add one in the producer and keep both. All UTC.

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
REAL, and the publisher documents three distinct mechanisms, which is unusually good:
- **Real duplicates across data centres.** The `id:` line I captured shows the *same* event
  available from both the `eqiad` and the `codfw` Kafka topic, with the non-authoritative one
  carrying `"offset":-1`. A naive consumer that subscribes broadly and dedupes on `id` will see each
  change twice. Deduplicating on the RC row id (observed `"id":3479008029`) is a real requirement.
- **Real synthetic events that must be discarded.** "The WMF Data Engineering team produces artificial
  'canary' events into each stream multiple times an hour ... These events are not filtered out in the
  streams available at stream.wikimedia.org. As a user of these streams, you should discard all canary
  events; i.e. all events where `meta.domain === 'canary'`." That is a *documented, periodic, injected
  duplicate stream* in a production feed - a first-class data-quality rule, not a hypothetical.
- **Real forced disconnects and therefore real gaps.** The 15-minute connection timeout plus the
  documented history of 502s when connections exceed the varnish limits mean a naive consumer
  genuinely loses events. `Last-Event-ID` resume and the 48-hour replay window are the fix.
- **Real out-of-order arrival.** Events from hundreds of wikis and two data centres interleave in
  arrival order that bears no relation to edit time, and a rebase or revert arrives after the edits
  it reverts.
- **Real deletes and undeletes.** There are dedicated `page-delete` and `page-undelete` streams. This
  is the closest thing to a genuine delete path in any public event feed, and it means the sink needs
  a real equality-delete or tombstone strategy rather than insert-only append.
- **Real late corrections to history, at the archive level.** The matching bulk feed is
  dumps.wikimedia.org/other/incr/, whose own README is blunt: "Revisions included in these dumps are
  not up to the minute. We write out those that were created up to 12 hours ago", it "does not
  guarantee that the data included in these dumps is complete, or correct", "Information about moves
  and deletes are not included", and it describes itself as "partial data" from an
  "experimental" service. So the bulk backfill path has a *published 12-hour lateness bound and
  declared incompleteness*, which is an excellent, honest input to a reconciliation check between
  the live stream and the backfill.

High-cardinality keys and likely partition skew
`page_id` is high cardinality and the natural entity key. `user` is high cardinality with a real
long tail. `wiki` / `server_name` is the natural partition key and is genuinely skewed - `enwiki` and
`commonswiki` produce orders of magnitude more edits than the long tail of small wikis, so
partitioning by wiki gives real hot-key behaviour. The event payload also repeats `server_url` and
`server_script_path` in every message, which is a deliberate denormalisation we can exploit (or
criticise) when modelling.

Nested or semi-structured event payloads
Yes, and specifically the interesting kind. `parsedcomment` is rendered **HTML** with MediaWiki
markup, `length` is a nested `{old, new}` object, `revision` is a nested `{old, new}` object, and
`meta` is a nested block of topic/partition/offset/uri/request_id/stream coordinates. The comment
text is genuinely semi-structured: untrusted user input carrying arbitrary markup, in a field that
an analyst will want to slice on. That is a real argument for storing it as a raw string plus
extracted features rather than pretending it is a clean dimension.

Windowed or time-series analytical questions it answers
- "How many edits per wiki per hour, and which wikis are being vandalised right now?" - a tumbling
  window keyed on `wiki` with a clear late-event story.
- "What is the net edit rate per page once reverts and deletions are accounted for?" - this needs
  the delete and undelete streams joined against `recentchange`, and a real tombstone-aware sink.
- "How long is the delay between an edit and its appearance in the public pageview counts?" - a
  genuine cross-source, cross-clock reconciliation that pairs with the pageviews dataset.
- "Which users or bots account for the volume?" - a cardinality and bot-detection question, where
  the payload already supplies a `bot` boolean that we should not simply trust.

Expected engineering challenges it forces
Idempotency across two data centres; mandatory canary filtering; a resumable consumer that survives a
15-minute forced disconnect; a sink that supports deletes and undeletes (Iceberg equality deletes or
a changelog convention); HTML-bearing free text handled safely in a serving layer; correct
multi-timestamp event-time handling where the SSE id and the event disagree; and a
live-versus-backfill reconciliation job with a known, published 12-hour tolerance.

Which target-job requirements it demonstrates
"Own, operate and harden the streaming platform for reliability, correctness, and cost at scale" -
resumable consumption and duplicate suppression are the whole job. "Establish and enforce data
governance: catalog organization, access control, data lineage, retention/compliance, and automated
data-quality checks" - canary filtering, delete tracking and live-versus-backfill reconciliation are
three real gated checks. "Expert SQL, dimensional/data modeling" - a page-as-entity model with a
proper change history is a textbook dimensional-modelling exercise with real event history attached.
"Collaborate with data analysts ... to ensure discoverable, well-documented, and usable data access" -
a widely-readable, well-documented public feed is the easiest dataset in this report to hand a
stakeholder.

Realistic local sample size and how we would scale up
Local: consume the live stream continuously and keep only a filtered subset (for example `enwiki`
namespace 0 edits, excluding `bot:true` and excluding `meta.domain === 'canary'`). Even a heavily
filtered stream is a few million rows a day, and at 1-3 KB per event that is single-digit GB per day
as Parquet, which is a realistic local working set and a good match for the 7-8 GB RAM budget if
ClickHouse is fed incrementally. Use the `since` parameter to backfill a fixed historical window for
repeatable benchmarks. For the benchmark: a fixed 30-day window across all wikis, measured, with the
row count and byte size recorded rather than estimated.

Relationships to other candidate datasets
This is the closest public analogue to a change-data-capture stream, which makes it the natural
counterpart to the relational CDC source in angle 01a. It also pairs with the Wikimedia *pageviews*
dataset (candidate 6) to produce a genuine two-clock reconciliation problem: edits happen at time T,
human pageviews at T plus minutes, and the lag is a real metric. Note the licence asymmetry -
pageviews are CC0, the RecentChanges feed is CC BY-SA - which is itself a governance lesson about
why catalog-level licence metadata per table matters.
```

### 4. Citi Bike trip history (NYC) and the Lyft GBFS live feeds

```
Dataset
Two coupled surfaces from the same operator. (a) Historical trip records: one row per completed
rental, with start and end station, start and end time, duration, and a hashed rider id. (b) Live
station status and vehicle availability published every few seconds over the GBFS standard, for every
station in the system.

Source and URL
History: https://s3.amazonaws.com/tripdata/  (monthly zip per operator/period)
Live: https://gbfs.lyft.com/gbfs/2.3/bkn/en/station_status.json  (and station_information.json,
free_bike_status.json, vehicle_status.json for e-bikes and scooters)
Live payload confirmed 2026-09-27: HTTP 200, 1,080,235 bytes, last_updated 1790487650, ttl 60.

Licence (and whether it permits our use)
Mixed and the part that needs a decision.
- The historical trip files are published by Motive (formerly Citi Bike's operator) under the Citi
  Bike open-data terms, which permit use with attribution. The precise current terms must be
  re-read at the point of ingest and recorded in the catalogue, because operator and aggregator have
  changed hands more than once and the terms have changed with them.
- The live feeds are served by **Lyft**, as a GBFS aggregator, not by Citi Bike itself. Lyft's
  developer terms govern that endpoint, and the aggregator's terms have to be checked separately
  from the underlying operator's.
VERDICT: usable for a non-commercial portfolio, but unlike MIT, CC0 or public domain this is a
licence that must be read and re-checked rather than assumed. Flag as the main licence risk in the
shortlist, and design the ingest so the licence and its date are recorded as catalogue metadata on
the table.

Volume, format, growth rate
History: CSV, gzipped, inside a per-month zip. Measured with `curl -I` on 2026-09-27:
`202409-citibike-tripdata.zip` is **976,527,118 bytes**, last modified 2025-07-03. So roughly 1 GB of
zip per month, and note the shape of the archive - the monthly file is produced some months after
the period it covers, which is itself a lateness and backfill case.
Live: JSON, one document per feed, republished on a TTL of 60 seconds. The station status document
alone is 1.08 MB and therefore about 1.5 GB per day of polling traffic if polled at the full TTL, and
far more of it is the same 2,520 stations restated, which is precisely the argument for
change-detection and for a proper upsert sink rather than blind append.

Live/append-incrementally-published, or static snapshot
Both, which is the point. The historical side is append-incrementally-published monthly on a public
S3 bucket that can be listed and tailed for new keys. The live side is a true high-frequency
polling feed. Tailing a real-time feed and backfilling months of history into the same table is a
real dual-path ingestion problem, not a synthetic one.

Access mechanism: API, bulk download, subscription; rate limits and automation
Both are anonymous, unauthenticated, keyless HTTPS. Bulk download is a public S3 bucket, so
`aws s3 sync` or plain `curl` over a key listing is sufficient and fully automatable. Live access is
HTTP polling with no documented rate limit; the GBFS standard expects clients to respect the
advertised `ttl` and last_updated, and polling faster than that is pointless. No WebSocket and no
SSE on this feed, unlike candidates 1 and 3, which means the "streaming" here is a
change-detecting poller, not a push stream - an honest distinction to make in the write-up.

Event-time semantics: timestamp fields, timezone behaviour
History: `started_at` and `ended_at` as ISO-8601 local New York timestamps, and separate start and
end **station ids**. Live: a document-level `last_updated` in epoch seconds plus a **per-station
`last_reported` in epoch seconds**. All epoch times are UTC; the historical ISO strings are local
Eastern time with no offset marker, which is a genuine timezone landmine and a real data-quality
check (DST transitions, and the ambiguous hour in autumn).
The `last_reported` field is the interesting one and is discussed below.

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
REAL, but of the *irregular-sampling* kind rather than the *late-event* kind, and the distinction
matters:
- **Real per-sensor staleness and clock skew, in-band.** Every station carries its own
  `last_reported`. A station whose feed is stale by minutes or hours is a real condition of a
  distributed bike fleet with flaky cellular uplinks, and the payload tells you so explicitly. The
  same field is the justification for a genuine "stale reading" data-quality rule.
- **Real state churn.** `is_installed`, `is_renting` and `is_returning` are booleans that flip as
  stations are taken out of service for maintenance, events or battery work, and as docking hardware
  fails. `num_bikes_disabled` and `num_docks_disabled` are non-zero for extended periods. Stations
  open and close over the archive's life, so the station dimension is a genuine
  **slowly-changing dimension with history**, not a static lookup.
- **Real duplicate and impossible trips in the history.** Repeated identical trips appear in these
  feeds, and there are trips whose end station does not reconcile with the dock counts. Conserving
  bikes between the trip table and the station-status table is a genuine, checkable invariant - and
  checking it is a real data-quality gate that can legitimately fail.
- **Late arrival, in the history:** monthly files are published months after the fact, so a
  trip-based query needs a completeness cutoff.
- **Honest limit:** the live station-status feed is a *current-state snapshot*, not an event log. We
  are inferring change by differencing successive snapshots. Events between two polls are invisible
  to us. So "out-of-order arrival" in the live path would be a property of our own poller and
  multi-station snapshotting, not something the source imposes. Say so, and get genuine
  out-of-order behaviour from candidates 1, 2 or 3 instead.

High-cardinality keys and likely partition skew
`station_id` is the natural key with thousands of distinct values, and it is genuinely skewed by
usage: a handful of commuter stations in Midtown absorb a large share of all trips while most
neighbourhood stations are quiet, so per-station trip counts have a real long tail. `rider_id` is
high cardinality and is a pseudonymised identifier, which makes it a good hook for the privacy
discussion. The single biggest skew trap is partitioning by station_id when one station genuinely
dominates a window - real and demonstrable.

Nested or semi-structured event payloads
Weak. Flat CSV plus one level of JSON nesting in the GBFS document (the `data.stations` array of
uniformly-typed objects). This is another honest weakness; it is the least interesting candidate
structurally, and it earns its place through time-series behaviour and the SCD, not through
payload richness.

Windowed or time-series analytical questions it answers
- "Which stations are persistently empty during the morning peak?" - a real rebalancing problem, and
  a genuine windowed aggregation over irregularly sampled station time series with gaps.
- "How long does a bike sit idle at a station before its next trip?" - dwell-time distribution, which
  is a time-series question with missing data, not just an aggregate.
- "What is the net bike count per station over time, and where does conservation break?" - the
  invariant check above.
- "Did the station's status change correlate with a drop in availability?" - a temporal join between
  the SCD and the fact stream where the SCD version is what makes the join correct.

Expected engineering challenges it forces
Change detection and idempotent upsert from successive snapshots; treating `last_reported` as a
first-class per-row event time rather than the document's `last_updated`; a real SCD2 station
dimension with validity ranges; timezone and DST correctness on local-time ISO strings; a
conservation invariant that genuinely fails sometimes and must be quarantined rather than dropped; and
a documented window over deliberately incomplete data.

Which target-job requirements it demonstrates
"Expert SQL, dimensional/data modeling" - SCD2 with validity ranges and temporal joins, arguably the
strongest fit in this whole angle. "Design data models and physical table layout (partitioning, sort
order, compaction, retention)" - an upsert-heavy sink is exactly the workload where Iceberg
compaction and small-file management bite. "Automated data-quality checks" - staleness, conservation
and completeness are three real, implementable, gateable checks. "retention/compliance" - pseudonymised
rider ids make a GDPR-shaped retention and redaction story concrete, which nothing else in this
angle does.

Realistic local sample size and how we would scale up
Local: 3-6 months of the monthly history zips, roughly 3-6 GB of zip and rather more as Parquet,
which fits comfortably; plus 1-7 days of continuously polled live snapshots, which at a 30-60 second
effective cadence for 2,520 stations is a few million station observations a week and a manageable
single-digit GB. Poll the live feed at the advertised TTL for a defined window rather than forever.
For the benchmark: 12 months of history, measured, plus a fixed 24-hour live capture, with row counts
and byte sizes recorded.

Relationships to other candidate datasets
The SCD2 lesson here is the counterpart to angle 01a's CDC work, and the live time-series discipline
here is the orderly counterpart to RIPE Atlas's chaos. Pairs especially well with the USGS
quakes (candidate 8) because both are small enough to hold entirely and can be used to prove
multi-source governance, or with Meteostat (candidate 7) if a second irregular time series is
wanted.
```

### 5. GDELT Global Database of Events 2.0

```
Dataset
GDELT 2.0: machine-coded global news events, plus the Global Knowledge Graph (GKG) of entities and
themes and the Mentions tables. One row per coded physical event or per coded mention, with actors,
locations, CAMEO event codes, tone and emotion scores, and the source article URL.

Source and URL
https://www.gdeltproject.org/  (data page: /data.html)
Bulk: http://data.gdeltproject.org/gdeltv2/  (15-minute master files, exports and GKG)
Live-ish query API: https://api.gdeltproject.org/api/v2/doc/doc (DOC 2.0)
Also available pre-loaded in Google BigQuery, updated every 15 minutes.

Licence (and whether it permits our use)
The most permissive licence in this report, and explicitly so. From gdeltproject.org/about.html:
"all datasets released by the GDELT Project are available for unlimited and unrestricted use for any
academic, commercial, or governmental use of any kind without fee." The only condition is attribution
and citation: "You may redistribute, rehost, republish, and mirror any of the GDELT datasets in any
form. However, any use or redistribution of the data must include a citation to the GDELT Project and
a link to this website (https://www.gdeltproject.org/)."
VERDICT: unambiguously permits our use, with no non-commercial clause, no share-alike, and no
field-of-use restriction. A citation string in the catalogue is the entire obligation. Note the
important boundary: the *codes* are free, but the underlying *article content* is not ours - GDELT
is a metadata index, and article copyright stays with the publisher, so we store the URL and the
codes, never the article body.

Volume, format, growth rate
CSV, gzipped, one file per 15-minute interval, hundreds of MB per day for the GKG. The publisher
states a single year of GKG "totals 2.5TB", and separately that the 2015 GKG alone is "over 2.5TB"
with "more than three quarters of a trillion emotional scores". Full history is therefore roughly
three orders of magnitude beyond our 231 GB disk.
VERDICT on scale: **this dataset cannot be ingested in full, ever, at our budget.** It must be
sampled by construction, and the sampling strategy has to be part of the design rather than an
afterthought. That is a legitimate thing to demonstrate, and it maps onto the JD's cost-optimisation
requirement, but it is a real constraint.

Live/append-incrementally-published, or static snapshot
Append-incrementally-published on a plain HTTP file tree at 15-minute granularity - one new master
file per interval, forever, no key required. This is the cleanest "tail a growing namespace" source
in the report: a Dagster asset that lists the prefix and picks up new files is the entire ingestion
job. It is not a push stream, but it is unambiguously incremental publication, and a 15-minute
watermark is a natural, defensible watermark for a news-derived source.

Access mechanism: API, bulk download, subscription; rate limits and automation
Bulk: anonymous HTTP GET on the file tree, no key, no auth, no published rate limit, no registration.
API: the DOC 2.0 API is unauthenticated but **strictly rate limited to roughly 1 request per 5
seconds**, and returns at most **250 results per query**, with other output modes restricted to the
last 3 months of the search window. Consequences for us: the DOC API is unusable as the primary
ingestion path at any volume, because 250 results per 5 seconds is about 4,000 rows per minute. Use
the bulk files for the fact table and the DOC API only as a live tail, a liveness probe, or a
reconciliation source.

Event-time semantics: timestamp fields, timezone behaviour
The GKG and Events rows carry `seendate` as a compact `YYYYMMDDTHHMMSSZ` string in **UTC**, which is
the interval the *article was seen*, not the interval the underlying real-world event occurred. That
distinction is the entire latency story of this dataset and is discussed next. `sourcecollectiondate`
records the date the source domain joined the collection. All UTC, no local timezones.

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
PARTLY REAL, and this is the honest verdict rather than the flattering one. The disorder is real but
it is **upstream in the world, not in the transport**:
- **Real lateness with respect to the real world.** An event that happens at 09:00 may only be
  reported at 14:00, and GDELT will therefore place a 14:00 timestamp on it. Comparing GDELT's
  `seendate` against an independent real-world timestamp is where a genuine, non-injected lateness
  distribution comes from. But the *files* themselves arrive essentially in order, so there is no
  transport-level out-of-order behaviour to solve.
- **Real duplicates, and a documented inability to remove them.** The single most-cited weakness of
  GDELT in the peer-reviewed literature is that many articles describe the *same* real-world event,
  so a naive count massively overstates reality. Findings cited in the GLOBE project review of
  empirical GDELT use include: two coders hand-reviewing 286 coded events found about **80%
  reliability**; another review of three quarter-million records found GDELT identified about 1,000
  events out of over 2,500 known ones, **precision around 40%**; and after keyword and temporal
  filtering plus de-duplication and ML classification, only **21% of valid URLs indicated a true
  protest event**. One analyst is quoted as warning that a naive user would take 649 reported
  kidnappings at face value when that is the number of *news reports about* a single kidnapping.
  VERDICT: the duplicates are absolutely real, they are semantically deep (they are not byte-level
  duplicates, they are the same event reported by different outlets), and removing them requires
  entity resolution. That is a genuine and unusually honest data-quality problem - but the pipeline
  cannot *fix* it, only measure it, which is itself the point to make.
- **Real coverage drift that breaks naive time series.** GDELT says its own 1.0 lineage needed daily
  normalisation files to "compensate for the exponential increase in the availability of global news
  material over time", and that because of live updating it does **not** publish normalisation files
  for 2.0, telling users to "perform a basic summation over the 15 minute update files" instead. So
  raw event counts per interval are not comparable across time, and any time-series chart of raw
  volume is wrong. Building that normalisation is a real, specified, small analytical task.
- **Real schema and dictionary drift.** 57-58 fields per Events record requiring "extensive
  cross-referencing against the GDELT codebooks", with numeric codes for actors, countries and CAMEO
  quad classes. Dimensions arrive as separate lookup files that must be joined, and code meanings
  have changed across releases.
- **Honest limit:** no transport-level out-of-order arrival and no transport-level duplicates. If we
  wanted to demonstrate a Flink watermark against genuinely shuffled input, GDELT would not do it.

High-cardinality keys and likely partition skew
`sourceurl` is effectively unique per mention and is the worst possible partition key.
`actor1_code`/`actor2_code` (CAMEO) and `countrycode` are the natural keys, and news attention is
genuinely, violently skewed - a crisis, an election or a natural disaster produces an enormous burst
on a handful of country codes while most intervals are near-empty on the rest. This is real
hot-key skew driven by real-world events, which is the most convincing kind to demonstrate because
the spike is explainable and reproducible on a known date.

Nested or semi-structured event payloads
Weak-to-moderate. The files are flat CSV with ~58 delimited columns and a complex, drifting
dictionary. The nested-payload requirement is better met by candidates 1 or 3. GDELT's real
complexity is *dictionary* complexity, not payload complexity, and that is a different (and still
valuable) modelling exercise.

Windowed or time-series analytical questions it answers
- "How did media attention to a story evolve in the 24 hours after it broke, in normalised terms?" -
  a 15-minute tumbling window with the normalisation step above, which is a genuine watermark +
  normalisation + window story.
- "How much of the coverage of event X is actually distinct reporting?" - the duplicate-rate metric
  the literature says everyone should compute and almost nobody does.
- "Which countries' event mix shifted in this interval?" - a windowed dimension-conditional aggregate
  that is a classic ClickHouse shape.
- "Did reporting volume lead or lag real-world sensor data?" - only if paired with a second source,
  and it is the best cross-source lateness question in the report.

Expected engineering challenges it forces
Interval watermarking on a 15-minute granularity; a sampling and retention strategy that is
documented rather than accidental; dictionary and dimension joins across drifting codebooks; a
normalisation factor computed as a first-class gold-layer table; a duplicate-rate metric with an
explicit decision *not* to dedupe blindly; and schema tolerance across 58 heterogeneous columns,
which is the strongest single argument for a semi-structured or raw-text bronze layer in this report.

Which target-job requirements it demonstrates
"Data models and physical table layout ... to balance write throughput, query performance, and
storage cost" - 2.5 TB/year against 231 GB makes retention and tiering a forced, quantified design
decision, which is exactly the JD's stated emphasis. "Automated data-quality checks" - normalisation
and duplicate-rate checks are real and gateable. "Cost optimization for cloud data/streaming
platforms" - this is the candidate where sampling *is* the cost story. "Automated data-quality checks"
and "catalog organization" - a 58-column, dictionary-dependent table is a genuine test of whether
the catalogue is documentation or decoration.

Realistic local sample size and how we would scale up
Local: a fixed, explicitly chosen window (for example 90 consecutive days of the Events master
files, or a few selected intervals per day across a year) is the right sample. 15-minute Events
master files are on the order of tens of MB compressed, so 90 days is a few tens of GB - too much to
grab casually, so sample by *interval selection* rather than by *date range* and say so. A
defensible local footprint is a few GB: 4 intervals per day for 365 days, or all intervals for 14
days. For the benchmark: measure the on-disk Parquet footprint of a stated interval set and the
Spark job over it; never claim to have processed the full corpus.

Relationships to other candidate datasets
Pairs with USGS (candidate 8) to build a genuine cross-source lateness comparison - a seismic event
with a known origin time against the news cycle that followed it is a real, defensible analytical
question that neither dataset can answer alone. Also pairs with Citi Bike (candidate 4) for
windowed comparison of a regular physical process against an irregular attention process. Its main
relationship is as a *licence contrast*: it demonstrates what "unrestricted use" looks like next to
MIT, public domain, CC0 and CC BY-NC-SA.
```

### 6. Wikimedia pageviews and pageview_complete (reported as a TIDY AGGREGATE - see verdict)

```
Dataset
Per-article hourly pageview counts for all Wikimedia projects, either as hourly individual files or
as the "pageview_complete" best-effort bzip series with 24 hourly counts packed per row.

Source and URL
Hourly stream: https://dumps.wikimedia.org/other/pageviews/
Complete series: https://dumps.wikimedia.org/other/pageview_complete/
Docs: https://wikitech.wikimedia.org/wiki/Analytics/Data_Lake/Traffic/Pageviews

Licence (and whether it permits our use)
CC0. From dumps.wikimedia.org/other/analytics/: "All Analytics datasets are available under the
Creative Commons CC0 dedication." This is the cleanest possible terms: no attribution required, no
restrictions at all, no share-alike, no non-commercial clause.
VERDICT: the best licence here, and a genuine contrast with candidate 3.

Volume, format, growth rate
Space-delimited text: `domain page_title page_id count_views`, one row per (domain, page, hour), plus
a `pageview_complete` bzip variant packing 24 hourly counts per row with hour encoded as a letter
(A = hour 0 ... X = hour 23). Tens of GB per month across all projects, and it has grown
continuously since 2015. The per-page_id cardinality is the largest in this report - tens of
millions of distinct page ids - which is a genuine high-cardinality fact table.

Live/append-incrementally-published, or static snapshot
Append-incrementally-published: one new file per hour, forever, on a public HTTP file tree, no key.
Clean to tail.

Access mechanism: API, bulk download, subscription; rate limits and automation
Anonymous HTTP GET, no auth, no key, no published rate limit, plain directory listing. Fully
automatable.

Event-time semantics: timestamp fields, timezone behaviour
UTC, but with a documented footgun that must be reproduced in our ingestion: "The time used in the
filename is in UTC timezone and refers to **the end of the aggregation period, not the beginning**"
(Wikitech). So `pagecounts-202609270000.gz` covers 23:00-24:00 UTC, not 00:00-01:00. Getting this
backwards shifts every window by an hour and is invisible in casual testing.

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
TIDY. This is the honest verdict, and it is the reason this candidate is not in the top five
despite a perfect licence.
- There is **no arrival time**. A row is a count for a closed hour. There is no way to know when
  that count became known, so late arrival cannot exist as a property of this data.
- There is **no duplicate concept**. A count is idempotent by construction. There are no duplicates
  to deduplicate because there are no events.
- There is **no out-of-order arrival within the stream**. Files are produced per hour in order.
- What *is* real and genuinely useful: the publisher's own "corrected for outages" family of datasets
  exists precisely because raw counts contain **under-counts from collection outages**, so there is a
  real and documented completeness defect. And there is a real definition break: the underlying
  measurement changed from `pagecounts-raw` (to 2011), to `pagecounts-ez` (2011-2015), to the
  "latest pageview definition" (2015-present) - a real, documented discontinuity in a long time
  series that a correct pipeline must model as a change in measurement, not as a change in the
  world.
- Bot and spider traffic is filtered by the definition rather than flagged per row, so per-event
  bot classification is not available.

High-cardinality keys and likely partition skew
Enormous and real: `page_id` runs to tens of millions, and view counts are famously Zipfian, with
`Main Page` alone taking a visible share of all traffic on every wiki. Partitioning by page_id or by
page title produces the most extreme real hot-key skew available in this report, and it is trivially
demonstrable on any single day. This is a legitimately excellent ClickHouse `ORDER BY` and
skew-handling case.

Nested or semi-structured event payloads
None. Four flat columns. Nothing here to flatten or type.

Windowed or time-series analytical questions it answers
- "What were the top-N most-viewed articles per wiki per hour, and how skewed is the head?" -
  a real, useful, and a genuinely high-cardinality ranking problem that ClickHouse is built for.
- "What is the shape of the diurnal curve per page?" - a 24-hour sessionising question.
- "Where did the collection under-count relative to the corrected dataset, and when?" - a real
  completeness question, and the only genuinely defect-shaped property here.
- "How did the change in pageview definition in 2015 alter measured traffic?" - a real
  measurement-continuity question, and a nice one for a portfolio.

Expected engineering challenges it forces
Windowed top-N with a correct and efficient `ORDER BY`; extreme real Zipfian skew; the
end-of-period filename convention; a documented measurement-definition break in 2015 that must be
handled as a data-quality finding rather than smoothed over; and honest handling of a fact table
whose grain is an aggregate, not an event.

Which target-job requirements it demonstrates
"Expert SQL ... and query performance tuning - including experience with an analytical/columnar store
(e.g. ClickHouse)" - this is the single best ClickHouse serving candidate in the report, because
top-N-per-hour over tens of millions of page ids with Zipfian skew is precisely the query shape that
punishes a naive `ORDER BY` and rewards a well-chosen one. "Design data models and physical table
layout" - directly. "Automated data-quality checks" - the outage under-count and the 2015 definition
break are both real, checkable findings.

Realistic local sample size and how we would scale up
Local: 30-90 days of hourly files for one or two large projects (enwiki plus commonswiki) is a few
GB compressed and is a realistic working set. Do not try to take everything; take a project subset
and a date window and record both. For the benchmark: a stated 90-day window for enwiki, measured
row count and Parquet size, and the ClickHouse top-N query benchmarked with a stated `ORDER BY`
comparison.

Relationships to other candidate datasets
The natural pair is candidate 3 (Wikimedia EventStreams), and the pairing is genuinely valuable: the
same organisation publishes a CC0 aggregate and a CC BY-SA event stream for the same content, which
is a governance lesson about per-table licence metadata, and a cross-clock reconciliation problem
(an edit at time T versus the pageviews it generates) that neither source can answer alone. Also the
best partner for a ClickHouse serving demo if the platform needs one candidate that is unambiguously
"query performance tuning" rather than "streaming correctness".
```

### 7. Meteostat hourly (reported as PARTLY REAL - irregular series, with a licence contradiction)

```
Dataset
Hourly weather observations for thousands of stations worldwide, aggregated from historical
archives, METAR reports and SYNOP messages, with model-derived substitute values filled in where
observations are missing.

Source and URL
Annual Parquet dumps, no API key: https://data.meteostat.net/hourly/{year}.parquet
Docs: https://dev.meteostat.net/data/bulk/hourly  and  https://dev.meteostat.net/data/bulk

Licence (and whether it permits our use)
THE PUBLISHER CONTRADICTS ITSELF, and this is worth reporting rather than resolving. The developer
documentation at https://dev.meteostat.net/license states the data is "published under the terms of
the Creative Commons Attribution 4.0 International (CC BY 4.0) license", with the Share and Adapt
rights spelled out as "for any purpose, even commercially". The consumer-facing legal page at
https://meteostat.net/en/legal states "Meteostat data is available under the terms of the Creative
Commons Attribution-NonCommercial 4.0 International Public License (CC BY-NC 4.0)". The support
site repeats the NC variant.
VERDICT: **ambiguous between CC BY 4.0 and CC BY-NC 4.0.** For a non-commercial portfolio both
permit our use, so the practical risk is low, but an ambiguous licence is exactly the kind of thing
a governance ticket should catch and quarantine rather than paper over. Record the contradiction
verbatim, cite both URLs with access dates, and choose the more restrictive interpretation
(CC BY-NC 4.0) as the conservative default. Also note the docs' own warning that the licensing
information "is only applicable to data redistributed by Meteostat" and that you must "review the
provider's licensing information carefully" if you obtain data through a provider - so the
underlying NOAA and national-service terms are a second layer.

Volume, format, growth rate
Parquet, one file per year, hourly grain. Measured with `curl -I` on 2026-09-27:
https://data.meteostat.net/hourly/2023.parquet = **1,888,656,641 bytes**;
https://data.meteostat.net/hourly/2024.parquet = **1,866,408,896 bytes**.
So roughly 1.87 GB per year, about 1.7 million rows per year at 1.87 GB. Multi-decade history is
therefore a few tens of GB - genuinely within budget, which is unusual and valuable for this angle.
A stale-docs note: the older documented bulk path
https://bulk.meteostat.net/v2/hourly/2024.csv.gz returns **HTTP 404** as of 2026-09-27, so the
developer docs are partly out of date and the real path is the `data.meteostat.net` Parquet one.

Live/append-incrementally-published, or static snapshot
Retroactively-updated annual snapshot, not a live tail. The docs state "The dumps are updated
regularly, depending on the granularity of records. Recent hourly data should be available after a
maximum of 24 hours." So the current year's file is rewritten in place, which means **historical
files can change after you have already read them** - the same genuine retroactive-correction
property as Binance's update changelog, arrived at by a completely different route. Not a stream.

Access mechanism: bulk download; no key, no auth, no registration. "Users are not required to sign up
for this service", with the polite instruction to "make sure to cache data if possible and forbear
from sending malicious calls". Fully automatable with `curl`.

Event-time semantics: timestamp fields, timezone behaviour
`date` is an hour-start timestamp, station-local time, which is the correct convention for
meteorology and a genuine timezone problem: an hour of local time maps to a different UTC instant
depending on the station's offset *and* on whether daylight saving is in force, so a single global
join or a single `date_trunc('hour', ts)` across stations is wrong near DST boundaries. Station
metadata (elevation, country, coordinates, timezone) is a real dimension that must be joined to
interpret the time.

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
PARTLY REAL, and the real part is genuinely about *time series* rather than *event streams*:
- **Real gaps and irregular sampling: inherent to the domain.** Stations go offline, are
  decommissioned, lose power or lose telemetry for days. Observations are produced on a schedule the
  station does not fully control, so gaps are a real property of weather observation, not an artefact
  of our pipeline. This is the cleanest example in the report of the "irregular sampling and gaps"
  requirement being genuine.
- **Real substituted values: a real correctness trap.** The docs state the data is "aggregated from
  historical databases, METAR reports and SYNOP data", and elsewhere reference "model data as a
  substitute for missing observations". So some rows are **modelled, not observed**, and a pipeline
  that treats a modelled value as an observation is producing a wrong answer while looking
  completely healthy. Distinguishing observed from modelled is a mandatory, non-obvious data-quality
  rule.
- **Real retroactive correction:** the current-year annual file is rewritten, so re-reading it yields
  different values than last week.
- **Honest limit:** there are no events and no arrival ordering. This is a tidy observation table
  with irregular *rows*, not a stream. Watermarks, deduplication and out-of-order handling would
  have to come from a different candidate. Its real lesson is **gap handling, interpolation policy and
  observed-versus-modelled provenance**, not streaming mechanics.

High-cardinality keys and likely partition skew
`station` is the natural key with thousands to tens of thousands of distinct values, and coverage is
genuinely uneven - dense over North America and Europe, sparse over the open ocean and polar regions.
That is real spatial skew and it is spatially obvious, which makes it unusually easy to demonstrate
and to explain.

Nested or semi-structured event payloads
None. Flat, well-typed, tidy columns. This candidate exists for time-series semantics, not structure.

Windowed or time-series analytical questions it answers
- "What was the daily minimum temperature per station, given that hourly observations are missing on
  some days?" - the honest answer requires a stated aggregation and gap policy, which is the entire
  point.
- "How many hours per year do we actually have observed data for, per station?" - a real coverage
  and completeness SLO, and a real data-quality dashboard.
- "Which stations in a region deviate most from their neighbours this week?" - a spatial join over
  an irregular grid with genuine missing cells.

Expected engineering challenges it forces
Station-local time to UTC conversion with DST; a documented gap and interpolation policy; separating
observed from modelled values with a blocking check; a coverage/completeness metric; a
retroactively-rewritten input that makes incremental full-refresh reconciliation necessary; and
honest aggregation across missing hours (averaging over present hours silently biases results, which
is a subtle and genuinely senior-level point to make in a write-up).

Which target-job requirements it demonstrates
"Automated data-quality checks" with severity and real quarantine consequences - observed-versus-
modelled and coverage are exactly that. "retention/compliance" is only weakly touched.
"Expert SQL" and time-series competence. "Data models and physical table layout" - choosing a
partition and sort order for a sparse, unevenly-covered time series is a real layout decision.

Realistic local sample size and how we would scale up
Local: this is the best-sized candidate in the report. One annual Parquet file is 1.87 GB, so 3-5
years is about 6-10 GB compressed, which fits the disk budget with room to spare and can be queried
in a Spark job without blowing the RAM budget. For the benchmark: 10-20 years, measured, with a stated
row count, and the caveat that the recent year is unstable because the file is rewritten.

Relationships to other candidate datasets
The irregular-series complement to RIPE Atlas (candidate 1): RIPE supplies disorder in arrival, this
supplies disorder in *coverage*. Also the natural provenance story to pair with USGS (candidate 8),
where modelled values versus observed values is a real and famous distinction in geophysics too.
Weaker on streaming mechanics than any other candidate, so it should be a supporting dataset, not a
spine.
```

### 8. USGS Earthquake Hazards Program real-time feeds and FDSN event service

```
Dataset
Global earthquake events: origin time, magnitude (with magnitude type), depth, epicentre, felt
reports, PAGER alert level, tsunami flag, significance score, contributing networks, and a
**status** field distinguishing automatically-detected from analyst-reviewed solutions.

Source and URL
Summary GeoJSON feeds: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{magnitude}_{period}.geojson
(magnitude in {significant, 4.5, 2.5, 1.0, all} x period in {hour, day, week, month} = 20 feeds)
FDSN event service: https://earthquake.usgs.gov/fdsnws/event/1/
Format docs: https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php  and  /csv.php

Licence (and whether it permits our use)
Public domain. A United States Government work; USGS publishes without restriction. VERDICT: the
most permissive terms available alongside CC0 and MIT. No attribution requirement, no restriction,
no registration.

Volume, format, growth rate
GeoJSON (or CSV, or QuakeML, or KML, or text). Measured live 2026-09-27:
- all_day.geojson: HTTP 200, **126,164 bytes**, metadata.count = 176
- all_month.geojson: HTTP 200, **7,520,009 bytes**
So roughly 7.5 MB per month and about 176 events per day. Across the full FDSN archive the event
count runs to millions over decades, but a month is trivially small. This is a deliberately
low-volume candidate and must be presented as such.

Live/append-incrementally-published, or static snapshot
LIVE, and the best-documented update cadence of any candidate. USGS states: "GeoJSON 7-days and less
feeds are cached for 1 minute; Other 7-day and less feeds are cached for 5 minutes; 30-day feeds and
searches are cached for 15 minutes." So the summary feeds refresh on a known, published 1-15 minute
cadence - which is a real, citable, *specifiable* watermark input rather than a guess. The FDSN
service additionally supports `updatedafter=`, a parameter to "filter to events whose record was
updated after this instant (good for incremental polls)", and `orderby=time-asc` for forward-scanning
without missing late arrivals. The service also states "automated applications should use Real-time
GeoJSON Feeds ... whenever possible, as they will have the best performance and availability for that
type of information."

Access mechanism: API, bulk download, subscription; rate limits and automation
No API key, no cookies, no `Referer`, no `User-Agent` gating beyond the courtesy convention of
identifying your client. No auth of any kind. The FDSN service caps a single response at 20,000
features, and the documented guidance is to stay under roughly 5-10 requests per second sustained
against FDSN, while the CDN-fronted summary feeds "tolerate much higher rates because they're
static-by-URL". Fully automatable. Measured response headers confirm no rate-limit headers are
returned at all.

Event-time semantics: timestamp fields, timezone behaviour
`time` is epoch **milliseconds** of the event origin; `updated` is epoch milliseconds of the last
record update; `tz` is the local UTC offset in hours; `place` is a human string embedding the
location. Two timestamps per event, with a documented and *large* gap between them - which is the
whole story of this dataset. All epoch values are UTC.

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
REAL, and unusually well documented by a government source:
- **Real, quantified lateness.** USGS publishes its own latency: within the contiguous United States
  "typically posted within 8 minutes", but "An earthquake outside the United States, where the
  seismic network is sparse (e.g. in Alaska), takes 20 minutes (on average) to process and post",
  plus "an additional delay of up to 60 seconds" for feed caching. So the lateness distribution is
  **geography-dependent** - 8 minutes in CONUS versus 20 minutes elsewhere - which is a beautiful,
  real, non-injected lateness model keyed on a spatial dimension.
- **Measured in practice.** On 2026-09-27 I measured, within the all_day feed, a maximum
  `updated - time` of **310 seconds** across the day's events, consistent with the published
  8-20 minute figures. That is a measurement, not a recall.
- **Real revisions, the best in the report.** Events carry `status` in {`automatic`, `reviewed`},
  and I measured 129 automatic versus 47 reviewed in a single day feed. The consequence is
  documented by a USGS-derived operational note: "Anything in the first 5-15 minutes after origin is
  `status=automatic` and the magnitude, depth, and even the location can shift by tens of km / 0.5+
  mag units when a human analyst reviews it (typically minutes to hours later, sometimes a day or two
  for small events)." So a row is **mutated after it is first published**, with a material change to
  its magnitude and location. This is a textbook late-arriving-update / slowly-changing-fact problem
  with a real source, and `updatedafter=` is the documented, correct polling strategy for it.
- **Real duplicates on re-poll, by design.** Because the feeds are *caches of a moving window*, a
  naive poller that re-reads `all_day` every minute and appends will duplicate every event many times
  over. Deduplicating on the stable event `id` (I observed ids like `nc75442887`, a
  network-code-prefixed alphanumeric key) is mandatory, and the correct pattern is `updatedafter=`
  plus a merge, not a re-append.
- **Real out-of-order arrival.** `orderby=time-asc` exists precisely because new events do not
  naturally arrive in time order across networks - a locally detected event in one network can be
  published before a better-located solution from another.
- **Real cursor pagination.** The FDSN service returns a next-page marker when a response hits the
  20,000-feature cap, which is a real pagination-correctness concern when building a polling loop.

High-cardinality keys and likely partition skew
Low volume, so skew is mostly theoretical - but `net`/`code` (contributing network) and `id` are
natural keys and the event count is genuinely dominated by tiny earthquakes in a few dense network
zones, so per-network-per-hour windows are real and can be empty or heavy. Say plainly that this
candidate does not stress skew.

Nested or semi-structured event payloads
Yes, moderately. The GeoJSON is a `FeatureCollection` with a `metadata` block, a `bbox`, and
`features[]`, each feature carrying a rich `properties` object (26 named fields: `mag`, `place`,
`time`, `updated`, `tz`, `felt`, `cdi`, `mmi`, `alert`, `status`, `tsunami`, `sig`, `net`, `code`,
`ids`, `sources`, `types`, `nst`, `gap`, `dmin`, `rms`, `magType`, `type`, `url`, `detail`) and a
`geometry.coordinates` array. `sources`, `types` and `ids` are themselves comma-joined multi-value
fields - a real semi-structured encoding that needs real parsing. It is a JSON document rather than
an event stream, so it flattens cleanly, but it is a legitimate exercise in hierarchical ingestion.

Windowed or time-series analytical questions it answers
- "What is the real detection-to-publication latency, by geography?" - answered directly from
  `updated - time` grouped by `place`/`net`, and it is a genuine, measurable SLO.
- "How often does a solution get revised, and by how much?" - the automatic-to-reviewed delta, a real
  and genuinely interesting measurement of scientific correction.
- "What is the completeness of our ingest against the FDSN archive?" - a real reconciliation between
  two access paths, which is a first-class data-quality job and a genuinely good use of a small
  dataset.

Expected engineering challenges it forces
A merge-by-event-id sink with late updates rather than append-only; a materiality policy for
revisions (does a 0.3 magnitude change rewrite the fact, or append a correction row? this is a real
design decision with two defensible answers); correct `updatedafter` incremental polling with no
gaps and no duplicates; explicit separation of a moving-window cache from an append-only fact; and
a reconciliation check across two independent access paths.

Which target-job requirements it demonstrates
"Automated data-quality checks" with real gateable rules (id uniqueness, revision material,
completeness against the archive). "Establish and enforce data governance" - public domain with
attribution-free use is a clean governance story, and `alert`/`status` give a natural severity model
for check gating. "A production-reliability mindset: monitoring, alerting, on-call, and incident
root-cause analysis" - a small, fast-moving feed that is easy to alert on and easy to reason about
end to end, which makes it ideal for building and testing the alerting path. "Expert SQL,
dimensional/data modeling" - a small fact-plus-lookup model with a genuine revision history.

Realistic local sample size and how we would scale up
Local: the whole thing. 7.5 MB for a month of all-month, 126 KB for a day. Even the entire
multi-decade FDSN catalogue via paginated pulls is feasible in the disk budget. There is no excuse
here - if a candidate cannot be run end to end locally, this one is not the reason.
For the benchmark: since the data is small, the honest benchmark is *ingestion rate and poll
correctness* - "sustained N polls per second for 24 hours with zero missed and zero duplicate events,
verified by full-archive reconciliation" - rather than a volume benchmark. That is a real and
defensible way to benchmark a small high-cadence source.

Relationships to other candidate datasets
The most useful pairing in the report is with GDELT (candidate 5): a seismic event has a known
origin time, and the news cycle about it is timestamped separately, so "how long after the ground
shakes does the world notice, and in which countries" is a genuine cross-source, cross-clock
analytical question that neither dataset can answer alone. Also the best candidate to prove
multi-source governance cheaply, and the best alarm source, because it moves fast, is tiny, and is
public domain with no terms to negotiate.
```

### 9. Criteo 1TB Click Logs (reported as a TIDY AGGREGATE WITH NO EVENT TIME AT ALL - rejected)

```
Dataset
Display advertising click logs for CTR prediction benchmarking. Each row is one ad impression served
by Criteo, the first column being a 0/1 click label, the remaining 39 columns being hashed integer
features (13 integer features and 26 categorical features) and a 13th integer identifier column.

Source and URL
https://ailab.criteo.com/criteo-1tb-click-logs-dataset/
Now hosted on HuggingFace: https://huggingface.co/datasets/criteo/CriteoClickLogs
MLPerf variant: https://ailab.criteo.com/criteo-1tb-click-logs-dataset-for-mlperf/

Licence (and whether it permits our use)
CC BY-NC-SA 4.0. Verified from the publisher's own page, whose licence text is the full
Attribution-NonCommercial-ShareAlike 4.0 legal code, and independently confirmed by the HuggingFace
dataset card, which states `license: cc-by-nc-sa-4.0`.
TWO flags, both material. **NonCommercial** restricts use to non-commercial purposes. **ShareAlike**
means any adapted material we distribute must carry a CC BY-NC-SA-compatible licence, which is a
real obligation for a public portfolio repository containing derived gold tables.
VERDICT: usable for a non-commercial portfolio, but it is the most restrictive licence among the
serious candidates, and ShareAlike on derived data is the kind of term that quietly propagates. A
portfolio that ever becomes commercial would need a different source.

Volume, format, growth rate
TSV, 24 files, one per day, 24 days of traffic. The HuggingFace card gives `size_categories:
n>1T` - over a terabyte. The publisher states positives and negatives were "both subsampled (but at
different rates) in order to reduce the dataset size" and "in order to keep business confidentiality".

Live/append-incrementally-published, or static snapshot
Static snapshot. 24 fixed files, never updated.

Access mechanism: bulk download (HuggingFace, and the historical S3 locations), no key, no auth.
The TSV is gzip-fragile by design - the 39 integer features have deliberate runs of tab characters -
so a naive `split('\t')` silently produces wrong column counts. That parsing hazard is real and
documented by every project that has ever used it.

Event-time semantics: timestamp fields, timezone behaviour
**There is no timestamp column.** The format is a label plus 39 integer features, with no date, no
time, no timezone and no event identifier. `Day 0` to `Day 23` are file names, not fields. Verified
against the publisher's own description of the schema and the HuggingFace feature list.
This is the single most important fact about this candidate.

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
**WOULD ALL HAVE TO BE INJECTED.** This is the cleanest example in the report of a dataset that
looks like a high-volume clickstream and is in fact a pre-processed machine-learning feature matrix:
- No event time means no lateness, no watermarks, no windows.
- No arrival time means no duplicate or out-of-order story.
- The publisher's own subsampling of positives and negatives at different rates means the click
  distribution is deliberately distorted, so even the label frequencies are not real.
- The 13-column "identifier" is a hashed bucket, not a key, so there is no entity to dedupe on.
Using this to claim streaming competence would be a straightforward misrepresentation, and an
interviewer who knows the dataset would spot it immediately. Included here precisely so it is
recognised and avoided.

High-cardinality keys and likely partition skew
The 26 categorical features are pre-hashed integer codes, so cardinality is unknown and unrecoverable
from the published data - you cannot even design a partition strategy with confidence, because you
cannot compute the real cardinality before ingesting. `id` is effectively unique. In short: unusable
for skew work.

Nested or semi-structured event payloads
None. Flat integers. No payload at all.

Windowed or time-series analytical questions it answers
None involving time. It answers a CTR-modelling question, which is an ML question, not a
lakehouse-engineering question.

Expected engineering challenges it forces
A genuine parsing challenge (the tab-run problem), and a genuine storage challenge (over a terabyte
on a 231 GB disk means a sampled subset is mandatory). Nothing about streaming.

Which target-job requirements it demonstrates
At most, raw-scale ingestion and a compression/column-pruning story. It demonstrates none of the
streaming, watermark, event-time or lateness requirements, and the licence actively works against
republishing derived results.

Realistic local sample size and how we would scale up
One day is on the order of 45 GB uncompressed per the published figures, so not even one day fits.
A few percent sample, or the MLPerf preprocessed NumPy shard. Not recommended at any size, because
the size is not the problem - the absence of event time is.

Relationships to other candidate datasets
None worth pursuing. It is listed as the negative control: the canonical "1TB clickstream" that is
actually a tidied aggregate. If someone proposes it as the platform's clickstream source, this
section is the reason to decline.
```

### 10. Amazon Reviews 2023 (reported as TIDY - rich but static and non-commercial)

```
Dataset
571.54 million Amazon product reviews (up to Sep 2023) with millisecond-resolution timestamps, and
54.51 million item metadata records with nested lists and dictionaries. The 2023 edition is
explicitly an improvement on earlier versions in "finer-grained timestamps (from day to
millisecond)".

Source and URL
https://amazon-reviews-2023.github.io/  (McAuley Lab, UCSD)
Hosted at https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023

Licence (and whether it permits our use)
Non-commercial academic research use only. Verified from the licence text reproduced in the
derivative dataset's LICENSE file: "Non-Commercial Use Only - This dataset may only be used for
academic, educational, and non-commercial research purposes", plus "No Redistribution for Commercial
Use", plus "Attribution Required". HuggingFace records the licence type as
"non-commercial-academic-research-use-amazon-product-reviews-2023" / "Other (custom)".
VERDICT: a non-commercial portfolio fits, but this is a custom, non-standard, restrictive licence -
not CC, not OSI - and it is materially more restrictive than MIT, CC0, public domain or CC BY 4.0.
Flag it. It would also be awkward if the platform were ever demonstrated to an employer in a
commercial context.

Volume, format, growth rate
JSONL, gzipped, per product category (34 categories in the trimmed derivative, more upstream).
571.54M reviews and 54.51M items upstream. A trimmed 34-category derivative is 85.4 GB. A single
category is the realistic unit of work. Static, never updated.

Live/append-incrementally-published, or static snapshot
Static snapshot. A one-time crawl of 2023.

Access mechanism: bulk download from HuggingFace or the project site. Free, no key, no auth, no rate
limit of note.

Event-time semantics: timestamp fields, timezone behaviour
`unix_review_time` in **seconds** epoch and `ts` in **milliseconds** epoch - so a genuine unit
inconsistency *within the same record* between two timestamp fields, which is a real and nasty
data-quality trap (a naive loader that picks the wrong one is off by a factor of 1,000, and the
result still looks plausible). No ingest or publish time.

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
**WOULD HAVE TO BE INJECTED.** There is no arrival time, so there is no lateness to observe. Reviews
are a crawl extract sorted or stored in crawl order, not in review order. Duplicates exist
incidentally (repeated identical reviews from the same user on the same product do appear in these
datasets) but there is no `ingested_at` against which to demonstrate a deduplication window, so
even that is not a *streaming* property. Verdict: **TIDY**, a static event-shaped snapshot. Useful
for dimensional modelling and text handling; useless for the streaming requirements that this angle
exists to satisfy.

High-cardinality keys and likely partition skew
`user_id` and `parent_asin` are both very high cardinality; `user_id` in particular is extremely so,
and user activity is genuinely Zipfian, so per-user windows would be real if we were doing
event-time work. The `timestamp` field itself is a bad partition key. Genuine but unexploitable here.

Nested or semi-structured event payloads
**The best in the report.** The metadata side is genuinely nested and heterogeneous:
`features` (a list of strings), `description` (a list of strings), `images` (a list of dicts, each
with `hi_res`/`large`/`thumb`/`variant` keys), `videos`, `bought_together` (a list),
`categories` (a hierarchical list), `details` (a free-form **dict** with product attributes), and
`store`. Mixed types, optional fields, varying key sets per record - exactly the messy semi-structured
problem that a raw/JSON column in ClickHouse and a typed projection in Iceberg exist to solve.

Windowed or time-series analytical questions it answers
"Review velocity by product after a price change" and "time-to-first-review after launch" are
genuine questions, and the millisecond timestamps make short windows meaningful. But they are
answered by batch SQL over a static snapshot, not by a streaming job, so they do not serve this
angle's purpose.

Expected engineering challenges it forces
Nested and variably-shaped JSON ingestion; mixed-resolution timestamp fields within one record;
choice between a JSON column and an exploded relational bridge table; and heavy de-duplication of
review text. All real, all batch-side.

Which target-job requirements it demonstrates
"Expert SQL, dimensional/data modeling" and schema evolution handling for a nested payload with
optional fields. Nothing about streaming, watermarks, lateness or real-time upserts.

Realistic local sample size and how we would scale up
One or two product categories, which is the natural unit; a few GB of JSONL each. Comfortable on
disk, and the 231 GB budget would hold perhaps a dozen categories. The bottleneck is RAM during
JSON parsing, not disk, which is itself a tuning exercise worth writing up.

Relationships to other candidate datasets
Its nested-payload strength is the one thing it offers that Binance lacks, so if Binance is the
volume spine this can supply semi-structured ingestion alongside it - though Wikimedia EventStreams
or RIPE Atlas do that with genuinely live data, which is better. Not recommended as a spine; worth
keeping as an optional supplement.
```

### 11. Open-Meteo (non-commercial free tier - licence-constrained but excellent for live weather)

```
Dataset
Weather forecast, historical and archive data via a free API, including current conditions,
historical hourly series, and an ECMWF archive API. Attribution goes to the national meteorological
services whose data is served.

Source and URL
https://open-meteo.com/  (Forecast, Historical Weather, ECMWF/ERA5, GFS and HRRR, Meteo-France, DWD,
ICON, GEM and JMA model APIs; plus Marine, Air Quality, Flood, Elevation and Climate Change)

Licence (and whether it permits our use)
CC BY 4.0 for the data, but the **free API is explicitly non-commercial**. Verified from the Terms
page: "By using the Free API for non-commercial use you agree to the following terms: You may only
use the free API services for non-commercial purposes. You accept to the CC-BY 4.0 licence." The
limits are explicit: "Less than 10'000 API calls per day, 5'000 per hour and 600 per minute", with
the plan table showing Commercial use as unavailable (❌) on the free tier. Non-commercial is
defined by reference to Creative Commons, and the examples given that *do* qualify include
"Utilizing our service for educational content" and "public research conducted at public
institutions".
VERDICT: acceptable for a non-commercial portfolio, and the CC BY 4.0 data licence itself is
permissive and would allow commercial use if we paid for a plan. But the free tier is
non-commercial-only and rate-limited, so: a portfolio that must remain unambiguously non-commercial
fits; one that might not should budget for a paid plan or choose a different source. The daily call
cap also constrains any live-tailing design - 10,000 calls/day is only about 7 calls per minute if we
spread it evenly across a whole day, which is the number that actually matters for a continuous
weather tail.

Volume, format, growth rate
JSON over HTTPS, with CSV options. Volume per call depends entirely on the query: a single
coordinate-hour is a few hundred bytes, a 500-station 10-year historical query is tens of MB. The
binding constraint is call count, not bytes.

Live/append-incrementally-published, or static snapshot
Both. The Forecast API is effectively live (current and hourly forecast, refreshed on the provider's
cycle), and the Historical and ECMWF archive APIs serve a growing static corpus. The ECMWF/ERA5
archive in particular is a genuine, continuously-extended, append-only archive.

Access mechanism: API, no key on the free tier, JSON or CSV, strict documented rate limits
(10,000/day, 5,000/hour, 600/minute, and 300,000/month on the free tier). The terms also state
"We reserve the right to block applications and IP addresses that misuse our service without prior
notice." Automatable within the caps; the caps are the design constraint, and a respectful backoff
and caching layer is not optional politeness here, it is required.

Event-time semantics: timestamp fields, timezone behaviour
ISO-8601 with an explicit `timezone` parameter, and the API supports `timeformat` to choose
ISO-8601 versus unixtime. The `timezone` parameter is the correct lever for a global, multi-station
ingest, and forgetting to set it is a real, classic bug (the API will otherwise return times in the
station's local zone with no offset, which is exactly the same trap as candidate 4's historical
timestamps).

Whether late events, duplicates and out-of-order arrival are REAL or would be injected
**MOSTLY WOULD HAVE TO BE INJECTED, and this is a significant finding.** The Historical and
ECMWF archive APIs return *observations and model output re-served on a schedule*, not a live
observation feed. There is no arrival time, so there is no transport-level lateness or out-of-order
behaviour. Duplicate handling has to be imposed by our own polling logic (if we re-poll an hour, we
re-receive that hour). The real domain properties available here are *irregularity of the source
cycle* and *gaps where a station reports nothing*, and even those arrive pre-interpolated through a
provider rather than raw. So Open-Meteo is a **convenient and well-licensed data source, not a
streaming source**, and it should be described that way rather than dressed up as one.
Where it genuinely helps is as a *joined dimension or lookup* alongside a real streaming source -
for example annotating RIPE Atlas target regions with local weather, or explaining Citi Bike demand
with rainfall. That is a real analytical question and a real cross-source join.

High-cardinality keys and likely partition skew
Latitude/longitude is effectively a continuous key, so a location-keyed table has unbounded
cardinality and no natural partition. Ten-thousands-of-stations is realistic. This is a real
modelling constraint, not a skew problem.

Nested or semi-structured event payloads
The JSON has a parallel-array shape: a `time` array plus one array per requested variable, and
`current` as a single object. Positionally-joined parallel arrays are a genuine ingestion hazard
because nothing in the payload tells you that element *i* of `temperature_2m` belongs to element *i*
of `time`. Unzipping them correctly, and handling the ragged rows that appear when a series is
shorter than `time`, is real work.

Windowed or time-series analytical questions it answers
"Was the station's demand drop explained by rainfall?" when joined to candidate 4. "Did a latency
degradation at a probe correlate with a weather event in its region?" when joined to candidate 1 -
and that is a genuinely interesting, genuinely hard analytical question that a naive pipeline
cannot answer because it requires aligning a sparse, region-keyed time series against a
high-volume, probe-keyed event stream.

Expected engineering challenges it forces
Strict rate-limit budgeting and backoff; correct handling of parallel arrays and ragged series;
correct explicit timezone handling across a global station set; and a dimension-join problem
against a much higher-cardinality fact table.

Which target-job requirements it demonstrates
"Automated data-quality checks" and correct temporal join semantics. It does not demonstrate
streaming mechanics, and it is a supporting dataset at best.

Realistic local sample size and how we would scale up
Call-limited rather than size-limited. A year's data for a few hundred stations fits in a few
hundred MB of Parquet and a few thousand API calls - comfortably inside the daily cap if spread
across a month. The real engineering is the rate limiter, not the storage.

Relationships to other candidate datasets
Best used as an *enrichment dimension* for candidate 1 (RIPE Atlas) or candidate 4 (Citi Bike), not as
a stream in its own right. Its inclusion in this report is primarily to close the licensing question
on "the obvious free weather API", and the answer is: good licence on the data, non-commercial
restriction on the free tier, hard rate caps.
```

### 12. Rejected on licence, verification, or shape

**OpenSky Network (live ADS-B flight positions and historical trajectories).** The best-engineered
real-time telemetry source in existence, and rejected here on licence terms, not on merit.
https://opensky-network.org/ . The Terms of Use and Data License Agreement state that the licence is
"solely for the purpose of non-profit research and non-profit education", that "Any use by a
for-profit or commercial entity requires written permission and a license", and most restrictively
that "Use of the REST API in any operational capacity - including integration into a live product,
service, or automated system (even if only internal) - requires a previous written agreement, even
for non-profit or governmental entities." The FAQ is blunter still: full dataset access "does
typically not include personal learning and research purposes by private individuals", and
"Downloading all data there is globally for a day or more is not the purpose of a database interface
... and may require an extraction fee." The full dataset is reachable only through a Trino interface
gated to universities, governments and aviation authorities. **Verdict: a private individual building
a portfolio is outside the intended user population for the full dataset, and "operational" use of
the API is prohibited outright.** The separately published pre-curated datasets (for example the
Zenodo trajectory releases, CC-BY) are a legitimate alternative but are static snapshots. Do not use
OpenSky as the live transport source. The contract terms also include joint-IP provisions over
derived work, which is a further reason to avoid it.

**mempool.space / public Bitcoin node APIs.** Verified working and unauthenticated on 2026-09-27
(`/api/blocks/tip/height` returned 968,785 with HTTP 200), and genuinely live, with a WebSocket for
new blocks. Tempting because blockchain data has the best real disorder story imaginable -
blocks arrive out of order, and **reorgs** mean a canonical chain tip can be *replaced*, which is a
stronger correctness problem than a late update. Rejected because: there is no explicit licence grant
or terms-of-use page for the API that I could locate and verify, so the terms are unclear rather than
confirmed; the data is an append-only ledger of blocks rather than an event feed with a schema we
control; and the reorg problem, while fascinating, is a chain-consistency problem rather than a
lakehouse problem, and would dominate the portfolio's narrative. **Revisit only if a licence is
confirmed in writing.** This is the clearest "unclear terms" flag in the report.

**Open Industrial Data (Aker BP Valhall, via Cognite).** Genuinely the most authentic industrial
time series available: high-frequency compressor sensor data plus maintenance history plus P&IDs
from a real North Sea production platform, described as "a live stream of industrial data,
continuously available and free of charge" (https://github.com/cognitedata/open-industrial-data).
Rejected for three practical reasons: the data is **delayed by 7 days or more** so it is not live;
it is **one compressor**, so there is no meaningful volume, cardinality or skew; and access runs
through the Cognite Data Platform, meaning an account, and the licensing question has no clean
public answer - a support thread titled "What are the licensing terms and conditions?" exists on
their own community. **Verdict: reference material for how real industrial time series behave, not a
dataset to build on.** The `cognitedata/open-industrial-data` repository is a good pointer and worth
citing in the proposal as evidence of domain realism.

**OpenAQ v3 air quality API.** Verified on 2026-09-27: `GET https://api.openaq.org/v3/locations`
returned **HTTP 401** with `{"message": "Unauthorized. A valid API key must be provided in the
X-API-Key header."}`. A mandatory API key on a live environmental feed is a real automation obstacle
for a portfolio that must run unattended, so this is dropped in favour of candidates whose live paths
need no credentials at all (1, 3, 4, 8). Noted here so the decision is recorded rather than
re-litigated.

**ThingSpeak public IoT channels (MQTT).** A genuine MQTT-based live IoT feed and technically
attractive because MQTT maps cleanly onto a Kafka Connect source. Rejected because the public
channels are user-contributed and unevenly maintained, so the data is not dependable enough to build
a demonstrable pipeline on, and the volume is tiny. Worth a footnote about MQTT as a source
connector, not a dataset.

**Bluesky firehose, GitHub Events API, Seismic Portal WebSocket, DexPapira SSE, CoinCap, TfL,
Network Rail TRUST.** All appear in the streaming awesome-lists and all have some appeal, and all
were screened out for specific reasons rather than dismissed: Bluesky's firehose is authenticated
and its historical access is commercially licensed; GitHub Events only retains a rolling ~90 days
and its archive is not a bulk download; Seismic Portal overlaps USGS (candidate 8) with less
documented terms; TfL requires an API key and Network Rail TRUST data is a UK rail dataset with
UK-specific terms and a hard institutional-access history, plus its own documentation notes that
"a delay may be reattributed many times until it is agreed" - an excellent disorder property in a
dataset we cannot cleanly access. Recorded here so the shortlist's exclusions are auditable.

---

## Ranked shortlist

### 1. RIPE Atlas measurement results

RIPE Atlas is the best candidate in this angle because it is the only source that is simultaneously
genuinely live, genuinely large, and genuinely messy for reasons that are documented by the
publisher rather than manufactured by us. Everything the posting asks for about "hardening the
streaming platform for reliability, correctness and cost at scale" has a real referent here: 15,164
volunteer probes with unsynchronised clocks give real lateness and real out-of-order arrival; the
`sent`/`rcvd`/`dup` fields give real in-band duplicate and loss accounting; the `-1` and `{"x":"*"}`
sentinels give a real data-quality trap that a naive average will silently corrupt; the documented
server-side buffer limit gives a real at-most-once hazard that forces the pipeline to be replayable
and idempotent; the `metadata` stream emitting a changed specification mid-measurement gives real
schema drift; and 199 million `msm_id` values against 15 thousand `prb_id` values give both
cardinality pressure and genuine hot-key skew on popular targets. The `sendBacklog` parameter plus
the REST replay API is the decisive practical property: it removes the single biggest objection to
any live-feed portfolio, which is that a demo only works while the feed happens to be running, and
lets us demonstrate a reproducible 24-hour capture. The licence permits non-commercial research
explicitly, with a commercial carve-out we can simply record. It beats the runner-up because it
manufactures nothing: every streaming problem it presents is a property of the domain.

### 2. Binance public market data

Binance is the best volume and time-series candidate in the entire angle, and it wins on licence
outright - MIT, with no non-commercial clause, no share-alike, and no field-of-use restriction,
which is cleaner than every other serious candidate here. The measured numbers are what make it
concrete: 678 MB of BTCUSDT trades for a single month, 84 MB of one-second klines, and a
demonstrated 2.5x growth in monthly trade volume between 2020 and 2024 that we can quote as a real
growth rate rather than an estimate. Its disorder is real and specific in a way nothing else
matches: the publisher states outright that "archived files may be updated at a later date as a
result of recently discovered issues" with a published changelog of replaced files and new
checksums, which means a file path is a stable key whose *content* changes after ingestion, and that
is a genuine late-correction and retraction pattern; the same trade is published both as a `trades`
row and inside an `aggTrades` group with explicit `first_trade_id`/`last_trade_id` spans, so
deduplication is mandatory rather than hypothetical; and spot timestamps switch from milliseconds to
microseconds on 2025-01-01, a real silent unit change in an untyped CSV column. The 313x size ratio
between raw trades and 1-minute klines also gives us a defensible, measured cost-versus-resolution
trade. It loses to RIPE Atlas only because it is not live - daily and monthly publication, not a
push stream - and because its payload is flat CSV with nothing nested, so it cannot carry the
semi-structured and variably-typed ingestion story on its own.

### 3. Wikimedia EventStreams

Wikimedia is the best CDC-shaped event stream available publicly, and it is the closest analogue to
Debezium's insert-update-delete output that we can legally and practically build on. It is genuinely
live over documented SSE with two independent replay mechanisms - the standard `Last-Event-ID`
header and a `since` timestamp parameter - and it publishes dedicated `page-delete` and
`page-undelete` streams, which means the sink needs a real tombstone or equality-delete strategy
rather than insert-only append. The disorder is documented with unusual precision: the same event
appears from both the `eqiad` and `codfw` Kafka topics with `offset:-1` on the non-authoritative one,
so a naive consumer sees every edit twice; WMF injects artificial "canary" events multiple times an
hour with `meta.domain === 'canary'` that the documentation explicitly instructs consumers to
discard; the connection layer enforces a 15-minute timeout and the administrators document a history
of 502s when connection limits are exceeded, so a client that does not resume correctly genuinely
loses events. The matching bulk backfill path at `dumps.wikimedia.org/other/incr/` publishes its own
limits - revisions are written up to 12 hours late and the dump declares itself "partial data" from
an "experimental" service that does "not guarantee that the data included in these dumps is
complete, or correct" - which gives a live-versus-backfill reconciliation job with a *published*
tolerance instead of an invented one. The `parsedcomment` field carries untrusted rendered HTML,
which is real semi-structured data needing a real handling decision. It ranks below Binance and
RIPE Atlas on two counts: the CC BY-SA share-alike term on derived content is a genuine obligation
that MIT and public-domain sources do not impose, and the ToS explicitly says the public stream is
"intended for use by small scale external tool developers" and "should not be used to build
production services", which is a real operational caveat to disclose.

### 4. Citi Bike history plus the Lyft GBFS live feeds

Citi Bike earns its place as the only candidate supplying three things nothing else here has: a real
slowly-changing dimension with genuine history, because stations open, close and go out of service
over the archive's life and the payload says so with `is_installed`, `is_renting`, `is_returning` and
the `num_*_disabled` counters; genuine irregular sampling with in-band evidence of staleness, because
every station reports its own `last_reported` and a station that has not checked in for minutes is a
real condition of a bike fleet on flaky uplinks rather than an artefact; and a real invariant that
sometimes fails, since trips and dock counts must conserve bikes and demonstrably do not always,
which gives a data-quality gate that can legitimately quarantine a record instead of a check that
always passes. The measured sizes are comfortable for this budget - 976 MB per month of history, and
a 1.08 MB live station document across 2,520 stations - and pseudonymised rider identifiers make the
GDPR-shaped retention and redaction story concrete, which nothing else in this angle does. It ranks
fourth because it is structurally the least interesting: flat CSV plus one level of uniform JSON, no
nested payload, and the live side is a current-state snapshot that we difference ourselves, so the
out-of-order behaviour in the live path is our own construction rather than the source's. The
licence is also the least certain in the shortlist, because the live feeds are served by Lyft as a
GBFS aggregator whose terms are separate from the historical files' operator terms, and that needs
reading and dating rather than assuming.

### 5. GDELT 2.0 Global Database of Events

GDELT wins on licence by a distance no other candidate can match - "unlimited and unrestricted use
for any academic, commercial, or governmental use of any kind without fee", with attribution as the
only condition - and it is the cleanest append-incrementally-published bulk source in the report, at
one new file every 15 minutes on an unauthenticated HTTP tree, which makes a Dagster asset that
lists a prefix the entire ingestion job. It also supplies a rare and genuinely useful honest
negative result: the peer-reviewed literature documents that the same real-world event is coded many
times by different outlets, with reported precision of roughly 40 to 80 percent and one study
finding only 21 percent of valid URLs indicated a true protest event. That is a real, semantically
deep duplicate problem that the pipeline can *measure* but cannot *fix*, and being able to say that
plainly is more credible than any claim of perfect deduplication. GDELT also forces a real
normalisation problem, because the publisher states outright that raw interval volumes are not
comparable over time due to the exponential growth in news coverage, and that no normalisation files
are provided for 2.0 so users must compute their own - which is a specified, small, real analytical
task with a visible effect on every time-series chart built from the data. It ranks fifth rather than
higher on three honest grounds: it cannot be ingested in full ever at our budget, since a single year
of GKG is stated at 2.5 TB against 231 GB, so sampling must be designed rather than improvised; the
files arrive essentially in order, so it offers no transport-level out-of-order behaviour and would
not demonstrate a Flink watermark against genuinely shuffled input; and its complexity is dictionary
complexity across 58 drifting columns rather than payload complexity, so it does not carry the
nested-payload requirement. Its best use is as a cross-source partner for candidate 8, where a
seismic origin time set against the news cycle that followed it is a real question neither source
can answer alone.

---

## Target-job requirements that remain UNDEMONSTRATED by this angle

Stated plainly, because gaps matter as much as picks. Several of these are by construction the job of
other angles in this proposal, and saying so is the point; others are genuine gaps that no dataset
in this angle can close and that the platform will have to argue for in prose instead of evidence.

1. **Debezium CDC from a relational OLTP source is entirely absent from this angle.** Not one
   candidate here is a relational OLTP-shaped dataset that can be loaded into PostgreSQL and mutated.
   The closest analogue is Wikimedia EventStreams' delete and undelete streams, but that is a
   pre-ordered event feed, not transactional log capture with before/after images, transaction
   boundaries or replication-slot semantics. **Nothing in this angle demonstrates the posting's
   first-named ingestion path, Debezium CDC into Kafka.** This must come from the relational angle
   (Olist and its salvage list), and the platform proposal should not claim otherwise.

2. **No real PII, so the GDPR-shaped compliance work is only sketched.** Every candidate here is
   pseudonymous at best: Binance has no users, RIPE Atlas has probe hostnames and IPs, Citi Bike has
   a hashed rider id, Wikimedia has usernames, GDELT has source URLs. None carries personal data
   requiring a lawful-basis determination, a right-to-erasure path, a data-subject-access workflow or
   a real pseudonymisation pipeline with a re-identification risk assessment. Citi Bike is the only
   candidate that makes this concrete, and it makes it concrete only because a hashed rider id exists,
   which is a much weaker story than a platform that has to handle a genuine subject-access request
   end to end. The posting names GDPR and SOC 2 as nice-to-haves; **this angle can evidence neither.**

3. **No multi-region or cross-account platform design.** Out of scope by the map's own decision, and
   correctly so - but it means no candidate here contributes evidence for that nice-to-have, and the
   proposal must present it as reasoning only.

4. **No slow-changing dimension with real business history.** Citi Bike gives us station lifecycle
   SCD2, which is a genuine and good fit, but there is no customer, product or account dimension
   with a long, genuinely changing attribute history. Time-varying customer state is the classic SCD
   exercise and this angle cannot supply it.

5. **Nothing demonstrates cost optimisation against a real cloud bill.** Binance's
   trades-versus-klines resolution ratio and GDELT's 2.5 TB-per-year corpus give us *reasoning* and
   *unit arithmetic* about storage and compute cost, and both map onto the posting's cost
   optimisation nice-to-have. But a local run on this pod produces no S3, MSK or EKS cost figures at
   all. **No measured cloud cost claim is available from this angle**, and the proposal must not
   imply otherwise.

6. **The 231 GB ceiling means no benchmark can be run at realistic scale, only at a stated
   reduction.** The largest honest local footprint achievable across all five shortlist candidates is
   perhaps 60-90 GB of Parquet with the raw archives streamed and discarded, against sources that
   individually run to hundreds of GB (Binance BTCUSDT alone is about 8 GB per month of raw trades at
   2024 volumes) to terabytes (GDELT GKG at 2.5 TB per year). Every benchmark will therefore be a
   sampled or windowed benchmark. This is legitimate and must be declared with its window stated, but
   it does mean **partition-pruning, file-count and compaction behaviour at production file counts
   can only be extrapolated, not measured** - and compaction behaviour under millions of small files
   is one of the posting's explicit asks. The honest workaround is to demonstrate compaction on
   synthetic small-file counts and label it as such, never as a measurement of the real dataset.

7. **The public live sources all carry "small scale external use" or equivalent service expectations,
   which is a governance fact the proposal must state rather than hide.** Wikimedia says the public
   stream "should not be used to build production services"; RIPE Atlas caps concurrent WebSockets at
   16 per IP and warns that unbounded connections have previously caused incidents; USGS asks for
   under 5-10 requests per second and provides no rate-limit headers; Open-Meteo's free tier is
   non-commercial and capped at 10,000 calls per day with blocking rights. This is honest and
   manageable - a portfolio pipeline is small-scale by construction - but it means **the platform's
   reliability claims are about the pipeline, not about the sources' SLAs**, and no source offers a
   contractual availability commitment to monitor against.

8. **Exactly-once source semantics are not obtainable from any public dataset here.** Every source
   is at-least-once or at-most-once: RIPE Atlas drops data if a consumer falls behind, Wikimedia
   drops events on disconnect, Binance silently restates archives, USGS silently replaces records
   during analyst review. **Idempotency keys, dedup logic and replayability are therefore ours to
   engineer**, which is the right answer - the posting asks for exactly-once *into* the lakehouse,
   not from the source - but it should be stated as a design commitment rather than presented as a
   property we inherited.

9. **Little or no genuine schema-evolution *within* a live stream, except where flagged.** Binance's
   millisecond-to-microsecond change and Wikimedia's evolving `recentchange` schema are real but are
   once-per-era rather than continuous. **Per-event schema variation, which is what most
   stream-processing tools claim to handle, is not strongly demonstrated** by any candidate here.
   Amazon Reviews' variably-shaped nested metadata (candidate 10) is the closest, and it is static.

10. **Nested and variably-typed payloads come only from RIPE Atlas and Wikimedia, and neither is a
    high-volume nested source.** RIPE Atlas's nesting is modest (an array of packet results whose
    length varies, and traceroute hop arrays). Criteo has no payload, Binance has no payload, Citi
    Bike has no payload, GDELT's complexity is dictionary rather than structural. So **the platform
    can demonstrate nested ingestion, but not at volume, and not combined with deep hierarchies** -
    a real if narrow gap, best closed by keeping Amazon Reviews as a deliberate supplement for
    nested-schema handling while being explicit that it is static and non-commercial.

11. **No clickstream with a session, a funnel, or a user identity that survives.** Criteo is the
    canonical click dataset and it has no timestamps at all. The nearest thing to a user-level funnel
    anywhere in this angle is Wikimedia's user-and-page activity across `recentchange`, and that is
    collaborative editing, not consumer behaviour. **If the proposal needs a clickstream-with-session
    story, this angle does not supply it**, and the honest options are either to accept collaborative
    editing as the behavioural domain, or to inject sessions ourselves - which would then be
    *simulated*, and should be labelled as such rather than dressed as a real property of any source
    in this report.
