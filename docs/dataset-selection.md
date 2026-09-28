# The dataset selection and the data story

**Ticket:** [The dataset combination and the data story](https://github.com/SoongGuanLeong/de-platform/issues/7)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Target posting:** ONL Biz Solutions, Senior Data Engineer - Data Lakehouse ([JobStreet 94703893](https://my.jobstreet.com/job/94703893)), cached verbatim at `~/projects/career-ops/data/jd-cache/031.md`.
**Decisions recorded here:** [ADR-0008](adr/0008-two-spines-with-no-cross-domain-join.md), [ADR-0009](adr/0009-dataset-licence-position-and-obligations.md).

---

## 1. What this document is

The platform's dataset selection: which sources are in, what each one is for, how they are shaped, what they cost in disk, what we are signing up for, and which candidates were deliberately left out. It is the mission's section 27 deliverable, and it resolves [the dataset combination ticket](https://github.com/SoongGuanLeong/de-platform/issues/7) on the map.

The candidates were researched in [`docs/research/01a-datasets-relational-cdc.md`](research/01a-datasets-relational-cdc.md) (15 relational, CDC and reference candidates) and [`docs/research/01b-datasets-event-streaming.md`](research/01b-datasets-event-streaming.md) (12 event and streaming candidates). Those reports hold the schema-level evidence and the dated primary sources; this document holds the decision.

**The rule that governs every size and volume figure here: nothing is measured yet.** Every number is a **budget** in the completion-bar sense, declared before the measurement it will judge. A budget that is exceeded is revised in a new entry, and the evidence that cited the old one is invalidated.

---

## 2. The business story

A fictional UK networking-equipment distributor, referred to here as **Kelvin Networks Ltd** (the name is cosmetic and can change). It sells network hardware and connectivity services to business resellers.

> Kelvin Networks distributes networking equipment to business resellers across the UK. Its order and stock system runs on PostgreSQL, and because its product is network performance it also runs internet-measurement probes and publishes connectivity data for its customers. The platform unifies the order stream, the measurement stream and UK geographic reference data, so analysts can see where the business is and how the network is performing.

The story is what makes the combination a platform rather than a data zoo: the company genuinely operates both a distribution business and a network-measurement service, so the two data domains belong to one firm. It is **not** a claim that the two domains join. They do not, and [ADR-0008](adr/0008-two-spines-with-no-cross-domain-join.md) records that as a constraint rather than an omission.

---

## 3. The combination

Four sources, two spines.

| Source | Spine | Ingestion | Processing | Role | M-rows |
|---|---|---|---|---|---|
| **TPC-C** on live PostgreSQL | Commerce | Debezium CDC to Kafka (KRaft), Avro via Apicurio | Flink upsert to Iceberg v2; Spark for gold | The CDC centre of gravity. Real binlog change events | **M2, M3**, M5, M11, M12, M17, M19, M21 |
| **TPC-H** SF100 | Commerce | Batch file | Spark batch silver/gold to Iceberg; materialise to ClickHouse | The batch and serving centre. A benchmark with published answers | **M4, M5, M6, M7**, M9, M18 |
| **RIPE Atlas** | Network | Live WebSocket plus REST replay | Flink streaming to Iceberg, with declared watermark and lateness | The streaming centre of gravity. Genuinely live, genuinely messy | **M8, M13, M16**, M2, M3, M15 |
| **ONSPD** | Network | Batch file, quarterly releases | Spark batch; SCD2 `MERGE` into Iceberg | Geography, SCD2 history, and the publisher's own documented defects | M5, M6, M12, M13, M17 |

Each source is the best available referent for a distinct named requirement, and no source exists to justify a technology. The technologies (Kafka, Flink, Spark, Iceberg, ClickHouse) are named by the posting; the datasets were chosen to exercise them with real engineering problems.

**A domain relationship is not a key join.** TPC-C and TPC-H share a subject matter (wholesale distribution), so one gold layer style serves both. They share no key, and nothing in this platform joins them.

---

## 4. Source records

### 4.1 TPC-C

| Field | Value |
|---|---|
| **Dataset** | Order-entry OLTP benchmark: 9 tables, 5 transaction types, a published population model, and the exact DML of every statement each transaction issues |
| **Source** | TPC-C v5.11.0, `https://www.tpc.org/tpc_documents_current_versions/pdf/tpc-c_v5.11.0.pdf`. **No TPC-official loader exists**, so the loader is ours to build |
| **Licence** | TPC permission-with-notice. Attribution mandatory. A permission notice, not an open-source licence: no warranty and no patent grant |
| **Size** | **W=100, approximately 30M rows** (research figure, to be confirmed at load). W minimum is 10 |
| **Format** | DDL plus load data, engine-dependent |
| **Update frequency** | Neither live nor snapshot. It is a workload specification: generate the population once, then drive continuous transactions |
| **Tables** | 9 |
| **Relationships** | `WAREHOUSE` 1:N `DISTRICT` 1:N `CUSTOMER` 1:N `ORDER` 1:N `ORDER_LINE`; `ITEM` 1:N `STOCK`; `ORDER_LINE` references both `ITEM` and its supplying `WAREHOUSE`, giving genuine cross-warehouse remote orders; `NEW_ORDER` is transient and deleted by Delivery; `HISTORY` is append-only |
| **Primary keys** | `(w_id)`, `(w_id,d_id)`, `(w_id,d_id,c_id)`, `(o_id,ol_number)`, `(s_i_id,s_w_id)`, `(i_id)` |
| **Timestamp characteristics** | **The weakest point, stated honestly.** `ORDER.o_entry_d` is the only order timestamp; `ORDER_LINE.ol_delivery_d` and `ORDER.o_carrier_id` are NULL until Delivery runs. No timezone, no business event-time, no late-arrival semantics |
| **CDC or event simulation** | **T1: genuinely real binlog CDC.** New-Order inserts `NEW_ORDER`, `ORDER` and `ORDER_LINE` and updates `STOCK`; Delivery deletes `NEW_ORDER` and performs two NULL-to-value updates; Payment updates `CUSTOMER` and inserts `HISTORY`; 1 percent of New-Orders roll back, so the stream contains real aborted transactions |
| **Data-quality problems** | Designed only: the 1 percent rollbacks, the 1 percent remote orders, and the `s_quantity` wrap. Otherwise referentially perfect, with **no accidental defects**. This is why it cannot carry the data-quality story |
| **Streaming suitability** | Excellent. This is the streaming ingestion path the posting names first |
| **Batch suitability** | Weaker. The population is homogeneous, with no seasonality and no business-day shape. Batch belongs to TPC-H |
| **Lakehouse suitability** | Ideal write side: small-rowcount upserts, real deletes, constant schema |
| **Analytical suitability** | Real questions exist (weekly GMV per warehouse, stock-out risk, missed delivery windows), but it is a poor ClickHouse benchmark because it measures OLTP throughput in a row store |
| **Engineering challenges** | The Debezium snapshot-to-stream boundary, multi-table atomicity across a four-table fan-out, equality deletes on composite keys, NULL-to-value transitions, delete handling, and backpressure |
| **M-rows demonstrated** | M2 and M3 (load-bearing), M5, M11, M12, M17, M19, M21 |

### 4.2 TPC-H

| Field | Value |
|---|---|
| **Dataset** | Decision-support benchmark: 8 tables, 22 published queries with published expected answers |
| **Source** | TPC-H v3.0.1 official tools zip. DuckDB's `tpch` extension is available but its output deviates from the specification; `tpchgen-cli` is the compliant option |
| **Licence** | TPC permission-with-notice, same class as TPC-C. Use the official tools zip, not the `databricks/tpch-dbgen` mirror, which has no licence file. **Declare which generator produced the data** |
| **Size** | **SF100 = 26 GB** (verified). The documented step-down is **SF30 = 7.6 GB** (verified) |
| **Format** | Pipe-delimited `.tbl` from `dbgen`, or a pre-generated DuckDB file |
| **Update frequency** | Static. Generated once |
| **Tables** | 8 |
| **Relationships** | `REGION` 1:N `NATION` 1:N `CUSTOMER` and `SUPPLIER`; `CUSTOMER` 1:N `ORDERS` 1:N `LINEITEM`; `PART` M:N `SUPPLIER` through `PARTSUPP`; `LINEITEM` references `PARTSUPP` on the composite key |
| **Timestamp characteristics** | `o_orderdate` plus the `l_shipdate`, `l_commitdate` and `l_receiptdate` chain. No timezone and no late arrivals |
| **CDC or event simulation** | **None.** Insert-only, with no updates and no deletes |
| **Data-quality problems** | None genuine: no NULLs, no updates, no deletes. **Any defect demonstrated on TPC-H is one we manufactured** |
| **Streaming suitability** | None |
| **Batch suitability** | Excellent. This is the batch centre |
| **Lakehouse suitability** | Excellent analytical fixture, with answers that act as an assertion oracle |
| **Analytical suitability** | Excellent, and comparable to published ClickHouse TPC-H figures because the queries and answers are published |
| **Engineering challenges** | The `LINEITEM` to `PARTSUPP` composite-key join with missing rows, the fan-out trap that inflates revenue, partitioning and sort-order decisions with measurable effect, and skew on popular parts |
| **M-rows demonstrated** | M4, M5, M6 and M7 (load-bearing), M9, M18 |

### 4.3 RIPE Atlas

| Field | Value |
|---|---|
| **Dataset** | Internet measurement results from volunteer probes, plus probe and measurement metadata |
| **Source** | `wss://atlas-stream.ripe.net/stream/` for live subscription, plus a REST replay API for reproducible windows |
| **Licence** | RIPE Atlas Service Terms V2.0. Research use is explicitly permitted and there is no copyleft. **Any commercial use requires prior permission from the RIPE NCC** |
| **Size** | A **reproducible 24-hour capture**, target cap 5 GB. The live corpus was measured at 15,164 connected probes and 199,142,482 public measurements on 2026-09-27. The local sample is a sampled slice, never the full firehose |
| **Format** | Newline-delimited JSON, already in the shape a Kafka producer wants |
| **Update frequency** | Live and continuous, with REST replay for reproducibility |
| **Tables or files** | Result records, probe metadata, measurement metadata |
| **Relationships** | `probe` M:N `measurement` through result records; a result resolves to a probe and thence to a location |
| **Timestamp characteristics** | Probe clocks are unsynchronised, so lateness and out-of-order arrival are real. `sent`, `rcvd` and `dup` give in-band duplicate and loss accounting |
| **CDC or event simulation** | Not CDC. A genuine live event stream, at-most-once in the places the publisher documents |
| **Data-quality problems** | Documented by the publisher: `-1` and `{"x":"*"}` sentinels that silently corrupt an average, server-side buffer drops, clock skew, 199M-cardinality measurement ids, hot-key skew on popular targets, and mid-measurement specification drift |
| **Streaming suitability** | Excellent. This is the streaming centre |
| **Batch suitability** | The REST replay path makes a reproducible window possible |
| **Lakehouse suitability** | Good: append-heavy, with a declared watermark and lateness policy |
| **Analytical suitability** | UK connectivity by postcode area, joined to ONSPD |
| **Engineering challenges** | At-most-once delivery means replayability and idempotency are ours to engineer. A 16-concurrent-WebSocket cap per IP. No service-level agreement to monitor against |
| **M-rows demonstrated** | M8, M13 and M16 (load-bearing), M2, M3, M15 |

### 4.4 ONSPD

| Field | Value |
|---|---|
| **Dataset** | The UK postcode-to-geography directory, covering live and terminated postcodes |
| **Source** | ONS Geography. A 235 MB multi-CSV zip, a 2.31 GB hosted table, and a scriptable GeoService REST API |
| **Licence** | Open Government Licence v3.0, with three mandatory attributions. **Northern Ireland `BT` postcodes are internal-business-use-only** and must be excluded from published tables |
| **Size** | 235 MB zip, approximately 2.7 million postcodes, **137 fields** |
| **Format** | Fixed-width TXT with no text qualifiers, and CSV. Spatial formats are also published |
| **Update frequency** | Quarterly releases |
| **Tables or files** | One very wide record: a degenerate star of one entity against roughly 20 conformed geographies at different grains |
| **Relationships** | Postcode to administrative, health and census geographies, **many-to-many in the boundary-straddling cases**; postcode to postcode across releases, which is the SCD2 history |
| **Timestamp characteristics** | `DOINTR` and `DOTERM` in `YYYYMM`, with **null meaning live**. Three different as-of dates inside a single release: postcodes, administrative areas, and health areas |
| **CDC or event simulation** | Quarter-over-quarter diffing produces a real change stream of inserts, updates and terminations. T2, from a statutory source |
| **Data-quality problems** | Publisher-documented: the ONSPD user guide admits that allocating addresses to geographies is imprecise through straddling and wrong assignment. Also two coordinate reference systems, and a null-means-live semantic |
| **Streaming suitability** | None |
| **Batch suitability** | Excellent reference dimension |
| **Lakehouse suitability** | A MERGE-heavy, delete-free write profile, in deliberate contrast to TPC-C's churn, and 137 columns make column pruning a demonstrable layout optimisation |
| **Analytical suitability** | The geographic enrichment for the network spine |
| **Engineering challenges** | Excluding the Northern Ireland `BT` subset, aligning three as-of dates inside one release, and handling two coordinate reference systems |
| **M-rows demonstrated** | M5, M6, M12, M13, M17 |

---

## 5. The relational shape

### 5.1 The commerce spine: TPC-C

| Join | Cardinality | Why it is hard |
|---|---|---|
| `WAREHOUSE` to `DISTRICT` to `CUSTOMER` to `ORDER` to `ORDER_LINE` | 1:N at each level | The four-level hierarchy is the grain trap: order-level and line-level metrics are one careless join apart |
| `ORDER_LINE` to `ITEM` and to `STOCK` on `(ol_supply_w_id, ol_i_id)` | N:1, but **self-referential across warehouses** | Remote orders reference another warehouse's stock, so a join on item alone fans out across warehouses and silently multiplies quantity |
| `ORDER` to `ITEM` through `ORDER_LINE` | **M:N, the bridge** | The genuine many-to-many, and where a fan-out inflates revenue |
| `ORDER` to `NEW_ORDER` | 1:1, **transient** | Delivery deletes the row, which is both the retention and compaction parable and the source of real DELETE change events |

### 5.2 The commerce spine: TPC-H

| Join | Cardinality | Why it is hard |
|---|---|---|
| `PART` to `SUPPLIER` through `PARTSUPP` | **M:N, the bridge** | Many suppliers per part and many parts per supplier |
| `LINEITEM` to `PARTSUPP` on `(l_partkey, l_suppkey)` | N:1 by composite key, **with missing rows** | The canonical shuffle hazard, and a naive inner join silently drops revenue |
| `LINEITEM` to `ORDERS` to `CUSTOMER` to `NATION` to `REGION` | N:1 up the chain | The standard revenue-by-nation shape, and **the fan-out trap for M6**: reaching supplier detail through `partsupp` multiplies rows and inflates revenue |
| `PART` to `PARTSUPP` | 1:N | Skewed, because popular parts have many supplier rows |

### 5.3 The network spine: RIPE Atlas

| Join | Cardinality | Why it is hard |
|---|---|---|
| `probe` to `measurement` through result records | **M:N at very high cardinality** | 15,164 probes against roughly 199 million measurement ids. Both sides are hot-keyed, so skew here is real rather than assumed |
| Result to probe to location | N:1 then **spatial** | See the join below |
| `metadata` to `measurement` | 1:N, **drifting** | The specification changes mid-measurement, which is real schema drift |

### 5.4 The network spine: ONSPD, and the one join between the sources

| Join | Cardinality | Why it is hard |
|---|---|---|
| Postcode to administrative, health and census geographies | **M:N in straddling cases** | One wide record against roughly 20 conformed geographies at different grains, with publisher-documented imprecision |
| Postcode to postcode across releases | SCD2, on `DOINTR` and `DOTERM` | Quarter-over-quarter diffing is a real `MERGE` of inserts, updates and terminations, with null meaning live |
| **RIPE Atlas probe to ONSPD postcode** | **Spatial, approximate** | Coordinates to nearest postcode. A real join with a documented tolerance rather than a key join, and the only honest bridge between the two network-spine sources |

### 5.5 The geography constraint

**Geography lives only in the network spine.** TPC-C's address columns are random strings with no real-world referent, TPC-H's `nation` and `region` are fictional and too thin to carry a geographic story, and the relational research says outright not to force a geographic enrichment onto TPC-C.

There is therefore **no conformed geography dimension spanning the two spines**. M6's conformed-dimension claim holds within a spine and must not be written as if it spans them. This is a named constraint, not an omission.

---

## 6. The cross-source questions

Working through every pair, and naming which pairs have no question:

| Pair | The question they answer together | Verdict |
|---|---|---|
| RIPE Atlas and ONSPD | Which UK postcode areas have the worst measured connectivity, and how does that change as postcodes are terminated? | **Genuine.** A real spatial join over a real SCD2 dimension |
| ONSPD across releases | Which postcodes appeared, changed or terminated this quarter, and did the administrative geography they belong to change under them? | **Genuine.** Real SCD2 |
| TPC-C and RIPE Atlas | On a shared time axis, how did order volume and UK network quality move over the same period? | **Time-only.** No key, no causality claimed. An honest correlation over a common clock |
| TPC-C and TPC-H | None | **Domain relationship only.** They share a subject matter and a gold-layer style, nothing more |
| TPC-C and ONSPD; TPC-H and ONSPD | None | **None.** Synthetic, US-shaped geography against UK postcodes |

**The count is two genuine pairs, both inside the network spine, plus one time-only cross-spine correlation.** The combination's justification is not that every pair has a question. It is that each source is the best available referent for a distinct requirement, and that the platform's unity is the control plane: one catalog, one lineage graph, one data-quality framework, one serving layer, carrying a CDC-fed OLTP mirror and a live measurement stream without either degrading the other. That platform-level question is measurable, and it is the one the combination actually answers.

The absence of cross-domain joins is documented deliberately. Inventing a synthetic region key to join orders to network measurements would have produced a join that no reviewer could trust, which is a worse outcome than a stated gap.

---

## 7. Size budget

All figures are **initial budgets**, declared before measurement.

| Source | Target | Basis |
|---|---|---|
| TPC-C | W=100, approximately 30M rows, target 10 GB in PostgreSQL | The research figure. W=10 at roughly 3M rows is too small to force real compaction and layout behaviour |
| TPC-H | SF100, 26 GB, 600M-row `lineitem` | Verified size. The factor at which published answers and ClickHouse's published TPC-H results are comparable. The documented step-down is SF30 at 7.6 GB |
| ONSPD | The 235 MB multi-CSV zip, 2.7M rows by 137 fields | Verified. The full record is kept so column pruning is demonstrable |
| RIPE Atlas | A reproducible 24-hour capture, cap 5 GB | The measurement set is chosen at capture and its size measured, not assumed |

**Working-set arithmetic against 231 GB of disk:**

```text
Reserve: OS, container images and tooling            60 GB
Reserve: Spark shuffle and compaction temp           30 GB
Data working-set ceiling                            140 GB
  raw landing                                        41 GB
    TPC-H 26, TPC-C 10, RIPE Atlas 5, ONSPD 0.25
  Iceberg bronze, silver and gold with snapshots     60 to 80 GB
  ClickHouse materialised serving copy               15 to 25 GB
  Kafka retention, time-bounded                       5 to 10 GB
```

Disk is not the binding constraint; memory is. The whole stack cannot be co-resident at 7 to 8 GB of free RAM, which is why reproducibility is defined by **profiles** rather than by a clean checkout of everything.

Every benchmark on this data is a **declared reduction** from production scale, with its window stated. Partition pruning, file-count behaviour and compaction at production file counts are extrapolated, never measured, and the proposal must say so.

---

## 8. The data-quality position

Neither TPC-C nor TPC-H has genuine defects: TPC-C's oddities are designed behaviours by specification, and TPC-H has no NULLs, no updates and no deletes at all. The data-quality requirement therefore rests on the two sources that have real, publisher-documented problems:

- **ONSPD** documents its own imprecision, admitting that allocating addresses to geographies is lossy through straddling and wrong assignment, and publishes a data-quality section that is effectively a test suite.
- **RIPE Atlas** documents its own disorder: sentinels that corrupt a naive average, in-band duplicate and loss accounting, server-side buffer drops, clock skew and specification drift.

**Injected faults are a separate thing.** The incident laboratory injects failures deliberately, and those are labelled as injected test incidents, never presented as a property of a source. A check that catches a publisher's documented defect and a check that catches a fault we injected are different claims, and the proposal keeps them apart.

---

## 9. The awkward list

Known engineering constraints, not reasons to reject a source.

**TPC-C.** No official loader exists, so we build one and budget the time for it. It has no timezone or business event-time semantics and no nested or semi-structured columns. Its 1 percent rollbacks and its `s_quantity` wrap are designed behaviours, not defects. Its geography can never be enriched.

**TPC-H.** Insert-only, with no updates, no deletes and no NULLs, so any defect demonstrated on it is manufactured. `nation` and `region` cannot carry geography. The `lineitem` to `partsupp` join has missing rows. The generator choice must be declared, because DuckDB's output deviates from the specification.

**RIPE Atlas.** The non-commercial licence carve-out. Unsynchronised probe clocks make lateness and out-of-order arrival real. The sentinels silently corrupt averages. Documented buffer drops make the feed genuinely at-most-once, so replayability and idempotency are ours to engineer. A 16-concurrent-WebSocket cap per IP. Real cardinality pressure and hot-key skew. Mid-measurement specification drift. No service-level agreement to monitor against.

**ONSPD.** The Northern Ireland `BT` restriction. Three as-of dates inside one release. Two coordinate reference systems. A null-means-live semantic. 137 fields, and a fixed-width TXT variant with no text qualifiers. A publisher that admits its own joins are imprecise.

---

## 10. The licence position

| Source | Licence | Obligation |
|---|---|---|
| TPC-C | TPC permission-with-notice | Reproduce the TPC copyright notice, title and date, and state that copying is by permission. A permission notice, not an open-source licence |
| TPC-H | TPC permission-with-notice | Same notice. Use the official tools zip, not the unlicensed mirror. Declare which generator produced the data |
| RIPE Atlas | RIPE Atlas Service Terms V2.0 | Research use permitted, no copyleft. **Commercial use requires prior written permission from the RIPE NCC** |
| ONSPD | Open Government Licence v3.0 | Display the OS, Royal Mail and ONS attributions. **Exclude Northern Ireland `BT` postcodes from published tables and document the exclusion** |

The RIPE Atlas commercial boundary and the ONSPD `BT` exclusion are recorded in [ADR-0009](adr/0009-dataset-licence-position-and-obligations.md), because both are obligations a reviewer will ask about.

---

## 11. Deliberate exclusions

**Failed on licence or automation.** Olist (CC BY-NC-SA 4.0). Stack Exchange (CC BY-SA plus a login gate with a disputed LLM clause). OpenStreetMap, OpenFlights and Open Food Facts (ODbL share-alike). MusicBrainz (split CC0 and CC BY-NC-SA). Amazon Reviews (static, non-commercial custom licence). Criteo 1TB (no timestamp column at all). HUD crosswalk (public domain but gated behind a login and a token, so unattended automation is only partial).

**Technically unsuitable for the bar.** Companies House (a real change stream, and ONSPD's most self-consistent pairing, but API-level: no cross-table transaction, no before-image, no atomicity, so it cannot evidence Debezium CDC, and it would be a fifth source that still does not join the commerce spine). Citi Bike and the Lyft GBFS feeds (the live-feed terms are separate from the historical terms; structurally the least interesting; and its geography is New York against a UK reference). GDELT 2.0 (a single year of GKG is 2.5 TB against 231 GB, files arrive essentially in order, and its complexity is dictionary drift rather than payload). Sakila (45k rows, no workload). Synthea (the best semi-structured source available, but wholly synthetic with no real change events and no shared domain). data.gov.my (flat single tables that force no engineering). OurAirports and GeoNames (Type 1, with no temporal dimension, which is exactly what ONSPD beats them on).

**Considered and deliberately not taken.** **SEC EDGAR XBRL**, recorded as a **future-extension candidate** rather than a failed dataset: US public domain, the cleanest licence of all candidates, and the only genuine bitemporal restatement source. It is excluded on scope, because it would be a fifth source with no home in either spine's narrative. **TPC-DS**, recorded as the documented alternative to TPC-H, to be chosen instead only if the pitch becomes dimensional and data-modelling expertise, since its heterogeneous fact grains force a grain-unification decision that TPC-H's clean schema never will.

**Out of scope by the requirements matrix, not dataset choices.** Trino or any federated query engine. dbt, Great Expectations and Soda. Superset, Power BI or any BI tool. A vector database or RAG pipeline. MinIO. Terraform. A built multi-region or cross-account platform. Formal HIPAA and SOC 2 programmes. An actually built 10x or 100x system.

No source was added to create more joins or more complexity.

---

## 12. Olist

**Out**, for two independent reasons:

1. **Licence.** Its data is CC BY-NC-SA 4.0: non-commercial and share-alike, and share-alike propagates to derived tables, so silver and gold tables built from it inherit the restriction. That is incompatible with the project's requirements for a published portfolio. The restriction belongs to the dataset itself, separate from and additional to any code licence.
2. **Simulated CDC.** Its change events would be synthesised from a dead 2016 to 2018 snapshot, which is T3 in the research's honesty tier system. The platform claims genuinely real binlog CDC, and a synthesised change stream cannot evidence that claim.

This confirms the condition [the salvage ticket](https://github.com/SoongGuanLeong/de-platform/issues/5) was waiting on. [ADR-0006](adr/0006-reference-only-reuse-and-provenance.md) already records the prior repository as reference-only with no code copied, and [`docs/salvage-list.md`](salvage-list.md) already assumed the dataset out and mapped its prior assets to this map's unspecified items.

---

## 13. Named constraints

The decisions that are easiest to get wrong later, stated once here so they are not re-litigated:

1. **No cross-domain join.** Nothing joins the commerce spine to the network spine. The only cross-spine link is time.
2. **No conformed geography dimension across the platform.** Geography is a network-spine concept only.
3. **TPC-C and TPC-H share a domain, not a key.**
4. **Every size figure is a budget, not a result.** Nothing here has been measured.
5. **The data-quality story comes from ONSPD and RIPE Atlas.** TPC-C and TPC-H have no genuine defects, and injected faults are labelled separately.
6. **Every benchmark is a declared reduction** from production scale, with its window stated and its extrapolations named.
7. **No source was added to create joins.** SEC EDGAR is a recorded future extension, not a rejection on merit.
