# 01a - Relational / OLTP-shaped / CDC-simulable datasets, plus reference, dimension and geographic companions

**Angle:** dataset research - relational, CDC, reference, dimension, geographic
**Target role:** Senior Data Engineer - Data Lakehouse (ONL Biz Solutions Sdn Bhd, Cheras KL; JD cached at `career-ops/data/jd-cache/031.md`)
**Research date:** 2026-09-27
**Method:** `awesomedata/awesome-public-datasets` and `sindresorhus/awesome` (Big Data section) used as *indexes only*; every candidate below was then re-verified against its primary source (publisher dataset page, licence text, official API spec, live HTTP `HEAD`/`GET`, or the actual schema/data files). Where I could not verify from a primary source, I say so rather than repeating community lore.

---

## 0. The governing constraint: what "CDC" can honestly mean here

The JD's streaming spine is **Debezium CDC → Kafka → Flink → Iceberg**. Debezium is a *log reader*: it can only emit change events for mutations that actually occur in a live database. Therefore:

> **There is no downloadable public dataset that ships real binlog/WAL-level CDC events.** None. Any project claiming otherwise is doing one of three things: (a) replaying a real-world publisher's change stream, (b) driving a real Postgres/MySQL with a real workload so Debezium reads a genuine WAL, or (c) synthesising DML.

Three tiers, used throughout this report:

| Tier | Meaning | Demo strength |
|---|---|---|
| **T1 - real OLTP mutation, real binlog** | A running Postgres/MySQL executing a specified OLTP workload; Debezium reads the actual WAL. Events are artefacts of real transactions. | Strongest. Literally the JD's pipeline. |
| **T2 - real-world change stream (file or API level)** | A real publisher emits real, dated change records (government streaming API, or diffing two dated releases of the same real dataset). Events are real; there is no transaction log and no before-image. | Strong. Real, attributable, replayable, honestly exercisable. |
| **T3 - synthesised** | A static snapshot is loaded and mutations are invented (by a load generator or by SQL you wrote). | Weaker. **Must be disclosed as synthesised.** |

This is the most important honesty constraint in the report. Most "OLTP" datasets are a **schema plus one final-state snapshot**. Loading one into Postgres and then running `UPDATE` statements does not make the CDC real; it makes the *pipeline* real and the *data* fabricated. Still worth doing - it exercises Debezium, Flink upserts, Iceberg MERGE, compaction, exactly-once - but the README must say which half is which.

A useful corollary: **a spec-defined schema plus a spec-defined workload is the best of both worlds.** TPC-C is the rare case where the transaction semantics (including UPDATE, NULL→value transitions, and rollbacks) are published, so you can drive a real database with a real, non-arbitrary workload and get T1 CDC without inventing anything. That is why it ranks where it does.

---

## Group A - Primary OLTP-shaped / CDC sources

---

### A1. TPC-C (Transaction Processing Council, revision 5.11.0)

**Dataset**
Order-entry OLTP benchmark: 9 tables, 5 transaction types, a published population model, and a published transaction profile for every statement each transaction issues.

**Source and URL**
- Spec (PDF, current): `https://www.tpc.org/tpc_documents_current_versions/pdf/tpc-c_v5.11.0.pdf`
- Spec index: `https://tpc.org/tpc_documents_current_versions/current_specifications5.asp` - lists TPC-C v5.11.0 with **Source Code: "n/a"**. TPC publishes **no reference implementation**; you need a third-party loader.

**Licence (and whether it permits our use)**
Spec text, verified: *"Permission to copy without fee all or part of this material is granted provided that the TPC copyright notice, the title of the publication, and its date appear, and notice is given that copying is by permission of the Transaction Processing Performance Council. To copy otherwise requires specific permission."*
- Permits schema/text reproduction in an attributed, non-commercial portfolio. **Permits our use.**
- **Flag:** this is a *permission* notice, not an OSS licence - no warranty, no patent grant. Weakest licence of the recommended set. Attribution mandatory.
- **Automation flag:** no TPC-official loaders. Third-party loaders exist in every engine's tree and on GitHub but vary in fidelity. Budget engineering time for this.

**Size, format, file or table count**
9 tables. Per-warehouse population (spec Clauses 1.2 / 4.3, cross-checked against published Full Disclosure Reports): 10 districts, 100,000 items, `W × 100,000` stock rows, `W × 100,000` customers, `W × 30,000` order rows, `W × 30,000` new_order rows, `W × 300,000` order_line rows, `W × 10,000` history rows; `W` minimum 10. A published FDR for a 330-warehouse run reports 99,002,313 order_line rows and 33,000,000 stock rows, so **`W=10` is a ~3M-row database and `W=100` is ~30M rows** - a realistic ClickHouse/Spark size. Format: DDL + load data, engine-dependent. **Tables: 9.**

**Update frequency; live or snapshot**
**Neither - it is a workload specification.** You generate the population once, then drive continuous transactions. That is precisely the property you want: it converts cleanly to T1 CDC.

**Tables and their relationships**
`WAREHOUSE` (1) → `DISTRICT` (1:N, 10/warehouse) → `CUSTOMER` (1:N, 3,000/district) → `ORDER` (1:N, 10 initial/customer) → `ORDER_LINE` (1:N, 5–15/order). `ITEM` (1) → `STOCK` (1:N, per warehouse), with `ORDER_LINE` referencing both `ITEM` **and its supplying `WAREHOUSE`** - i.e. genuine self-referential cross-warehouse "remote" orders. `NEW_ORDER` is the transient input table for New-Order and is **deleted** by the Delivery transaction. `HISTORY` is an append-only customer-balance log. Three-level hierarchy *plus* a self-referential cross-warehouse edge - better relational shape than most "real" datasets.

**Primary keys, natural and business keys**
- PKs: `(w_id)`, `(w_id,d_id)`, `(w_id,d_id,c_id)`, `(o_id,ol_number)`, `(s_i_id,s_w_id)`, `(i_id)`.
- **Business/natural keys:** `o_id` is a monotonically increasing order number; `ol_number` is unique *within* an order - a textbook composite-natural-key case. `c_last` is a business-ish key the Payment/Order-Status transactions index on, with a documented SQL-92 escape hatch using `c_id` instead, tracked as a disclosed statistic.
- `s_data`, `i_data`, `c_adata` are 300-byte filler fields with ~10% random text - deliberate padding so row widths are realistic. A **feature** for a lakehouse demo: wide, poorly-compressible rows make parquet/ORC/ClickHouse compression choices visible.

**Timestamp semantics and timezone behaviour**
**TPC-C's weakest point - state it honestly.** `ORDER` has a single `o_entry_d`; `ORDER_LINE.ol_delivery_d` and `ORDER.o_carrier_id` are **NULL until Delivery runs**, then become a timestamp and an integer. No timezone, no business event-time, no late-arrival semantics. **Nothing in this report handles timezone correctness; nothing in this report demonstrates it either.** If tz handling is a requirement you want shown, TPC-C will not do it (see A4 or B2 for partial substitutes).

**Nested or semi-structured content**
**None.** Flat and typed. Nothing to exercise a `struct`/`map`/`array` column or a semi-structured ingest path.

**Expected data-quality problems actually present**
Deliberate, by spec:
- **1% of New-Order transactions reference an unused item id and must roll back** - so your stream contains real aborted transactions if you log them. Genuinely valuable.
- **1% of order lines are remote** (cross-warehouse), producing `s_dist_xx` reads that are *not* joined.
- **`s_quantity` wraps**: `(S_QUANTITY - OL_QUANTITY) + 91` when within 10 of zero. Looks like a corruption in a gold model if you don't know why.

Those are the *designed* problems. Otherwise the dataset is referentially perfect with no accidental quality issues - **a genuine weakness if "automated data-quality checks" is a headline requirement.**

**CDC suitability, and whether change events are real or synthesised**
**T1. The strongest CDC story available from a public source.** Each transaction's DML is specified:
- **New-Order:** INSERT `NEW_ORDER`, INSERT `ORDER`, **UPDATE `STOCK`** (decrement `s_quantity`, increment `s_ytd`, `s_order_cnt`, maybe `s_remote_cnt`), INSERT `ORDER_LINE`.
- **Delivery:** **DELETE `NEW_ORDER`**, **UPDATE `ORDER`** (`o_carrier_id` NULL→value), **UPDATE `ORDER_LINE`** (`ol_delivery_d` NULL→timestamp).
- **Payment:** **UPDATE `CUSTOMER`** (`c_balance`, `c_ytd_purchase`, `c_payment_nbr`, `c_last` update count), INSERT `HISTORY`.
- **Order-Status / Stock-Level:** read-only, but generate join pressure and predicate variety.

You get multi-table transactional fan-out, genuine UPDATEs of value *and* counter columns, a **NULL→value transition** (the single most important Iceberg/Flink upsert case), **DELETE**, and periodic rollbacks. **None of it is synthesised.** The `NEW_ORDER` insert-then-delete lifecycle also gives a natural retention/compaction story.

**Batch suitability**
Weaker than the OLTP story. The population is homogeneous - no seasonality, no business-day shape - so batch silver/gold has less to work with than TPC-H or a real marketplace. TPC-C is for the stream, not the batch. **Pair with A2** so the project has both legs.

**Lakehouse and ClickHouse serving suitability**
- **Iceberg:** ideal write-side. Small-rowcount upserts, real deletes in the stream, constant schema. Textbook Flink upsert-kafka → Iceberg v2 path.
- **ClickHouse:** good as the serving read of final state; **weak as a benchmark peer** (TPC-C measures OLTP throughput in a row store; ClickHouse loses and looks bad). Use TPC-C to *feed* ClickHouse and **TPC-H to benchmark it** - ClickHouse publishes TPC-H results, so your numbers are comparable. That division of labour is deliberate.

**Realistic analytical questions it answers**
"Weekly GMV and orders per warehouse region, net of cancellations." "Which SKUs are at risk of stocking out (the Stock-Level query's own definition: fewer than 10 units on hand, descending)?" "Mean order-line value per district." "Did any order miss its delivery window - `o_entry_d` vs `ol_delivery_d`?" "How long from `o_carrier_id` being set to the row being queryable in ClickHouse?"

**Expected engineering challenges it forces**
Debezium snapshot+stream boundary (snapshot must not double-count against the stream); multi-table atomicity (one New-Order touches 4 tables - how does your Flink job checkpoint across that?); **composite primary keys** `((o_id,ol_number)`, `(s_i_id,s_w_id)`) - Iceberg equality deletes on composite keys are a real correctness trap; NULL→value transitions; delete handling; schema evolution; backpressure when a large run outruns your sink.

**Which target-job requirements it demonstrates**
"Debezium CDC → Apache Kafka" ✅ (directly, for real). "Apache Flink (real-time upserts / streaming)" ✅ (the core demo). "Partitioning, compaction, job/state tuning" ✅. "Production experience with an open table format / lakehouse" ✅ (Iceberg v2 MERGE; its row deletes are position deletes, not equality deletes - corrected 2026-09-27, see [ADR-0002](../adr/0002-exactly-once-effect-not-delivery.md)). "Physical table layout (partitioning, sort order, compaction, retention)" ✅ - `NEW_ORDER` is *the* compaction parable. "Production-reliability mindset" ✅ (connector restarts mid-transaction, LSN gaps, interrupted snapshots). "Expert SQL" ✅. "AWS S3 + RDS" ✅. ClickHouse ✅ as a sink, ⚠️ as a benchmark. Spark batch ❌ (use A2).

**Relationships to other candidate datasets**
- Pairs with **A2 (TPC-H)**: same subject matter (wholesale distribution), so one gold layer serves both. Same domain makes the project coherent.
- Geography is too coarse to be interesting; do not force an enrichment.
- `ITEM` (100k items, one name + one price) is a deliberately poor product dimension. Do not try to make it one.

---

### A2. TPC-H (revision 3.0.1) and `dbgen`

**Dataset**
Decision-support benchmark: 8 tables, 22 queries, a published data generator with published expected answers at SF 0.01 / 0.1 / 1.

**Source and URL**
- Spec index: `https://tpc.org/tpc_documents_current_versions/current_specifications5.asp` - TPC-H v3.0.1, tools `TPC-H_Tools_v3.0.1.zip`
- Official tools linked from that page
- `https://github.com/databricks/tpch-dbgen` - mirror of the official `dbgen`/`qgen` C sources (README confirms: *"This is the general README file for DBGEN and QGEN, the database population and executable query text generation programs used in the TPC-H benchmark."*)
- `https://www.duckdb.org/docs/current/core_extensions/tpch` - `CALL dbgen(sf=…)` plus **pre-generated databases at every scale factor**

**Licence (and whether it permits our use)**
Same class of notice as TPC-C: free copying with the TPC copyright notice, title and date reproduced; other copying reserved. Permits portfolio use with attribution. **Flags:** (1) `databricks/tpch-dbgen` has **no licence file** (GitHub API confirms `license: None`) - the mirror is unlicensed even though the underlying TPC text is permission-granted. Prefer the official tools zip and keep the TPC notice in the repo. (2) DuckDB is MIT so the `tpch` extension is licence-clean code, but DuckDB's own docs warn the generated data *"has small differences from the official TPC-H specification. To obtain fully TPC-compliant datasets, use the `tpchgen-cli` project."* **If you publish answers, say which generator you used.**

**Size, format, file or table count**
8 tables: `customer`, `lineitem`, `nation`, `orders`, `part`, `partsupp`, `region`, `supplier`. **Pre-generated DuckDB database sizes, read from DuckDB's docs:** `sf1` 250 MB, `sf3` 754 MB, `sf10` 2.5 GB, `sf30` 7.6 GB, `sf100` 26 GB, `sf300` 78 GB, `sf1000` 265 GB, `sf3000` 796 GB. Format: single DuckDB file, or pipe-delimited `.tbl` text via `dbgen`. **Recommend `sf100` (26 GB) or `sf300` (78 GB)** - big enough that partitioning and sort order visibly matter, small enough to iterate on.

**Update frequency; live or snapshot**
**Pure snapshot.** You generate it; nothing updates it. Honest headline: **TPC-H produces no UPDATEs and no DELETEs.** All 22 queries are reads. One nuance worth knowing and worth *not* over-claiming: `dbgen` has a `-U <streams>` option emitting *update files* for the TPC-H throughput measurement, so change data can be generated for a throughput run - but that is a niche benchmark feature, not a change feed you can lean on. **Do not present it as one.**

**Tables and their relationships**
`region` (5) → `nation` (25) → `supplier` (10,000) → `orders` (`SF × 1,500,000`) → `lineitem` (`SF × ~6,000,000`) → `part` (`SF × 200,000`) → `partsupp` (`SF × 800,000`, composite PK `(ps_partkey, ps_suppkey)`). `customer` (`SF × 150,000`) → `orders`. **`lineitem` has four foreign keys** (`l_orderkey`, `l_partkey`, `l_suppkey`, `l_partsuppkey`) and joins back to `partsupp` on a composite key - the canonical many-to-many fan-out trap.

**Primary keys, natural and business keys**
`o_orderkey` is a surrogate but **sort-order-significant** (values deliberately non-contiguous). `l_linenumber` is a natural per-order sequence. `ps_partkey + ps_suppkey` is a composite natural key. `c_mktsegment` is a low-cardinality business attribute designed to be a dimension. `l_returnflag`/`l_linestatus` are the F/N/A business states. Deliberately, no business-natural order number exists.

**Timestamp semantics and timezone behaviour**
`o_orderdate`, `o_commitdate`, `l_shipdate`, `l_commitdate`, `l_receiptdate`, `l_shipinstruct`, `l_shipmode`. **All naive, no timezone, no offset, no DST.** TPC-H models an interval in a fictional calendar. It teaches date arithmetic; it teaches nothing about timezone. Do not claim otherwise.

**Nested or semi-structured content**
None. Flat and typed.

**Expected data-quality problems actually present**
- **Comment-bearing strings** (`o_comment`, `l_comment`, `c_address`, `s_address`, `p_comment`) with random words at random intervals - semantically meaningless, useful as payload, not `NULL`-homogeneous. These are the columns you can strip in silver without losing anything.
- **No `NULL`s anywhere.** `dbgen` is referentially perfect and complete. Zero genuine quality problems. TPC-H is a *performance* fixture, not a quality fixture. If your DQ story rests on TPC-H you will be inventing defects and must disclose that.
- At SF < 1 the `orders`/`lineitem` join is sparse and some queries return zero rows at SF 0.01 - don't demo at tiny scale.

**CDC suitability, and whether change events are real or synthesised**
**T3 at worst.** Insert-only by design; getting CDC would mean writing the `UPDATE`s/`DELETE`s yourself. **Recommendation: do not.** Use TPC-H purely as the batch/OLAP/serving leg and say in the README that it is insert-only. It is a supporting role here, not a primary one - which is exactly how it is ranked.

**Batch suitability**
**Excellent, and this is its job.** 22 published queries with published expected answers at SF 0.01/0.1/1 means you can assert correctness. Natural Spark silver/gold exercise: `lineitem` at SF100 is 600M rows, joins are multi-hop, answers are checkable. Also the standard ClickHouse benchmark, so your serving numbers are comparable to published ClickHouse results.

**Lakehouse and ClickHouse serving suitability**
**Both excellent.** Iceberg over parquet with `o_orderdate`-range partitioning and `l_orderkey` sort order at SF100 is a legible, teachable layout decision with measurable before/after. ClickHouse over the same Iceberg table turns the 22 queries into a serving benchmark. **This is the dataset that actually earns the "analytical/columnar store + query performance tuning" line on the JD.**

**Realistic analytical questions it answers**
The 22 TPC-H queries (Q3 shipping priority and revenue, Q5 local supplier volume, Q6 forecasting revenue change, Q18 volume shipping, Q22 global sales opportunity) plus the ones analysts actually ask: revenue by month with a 3-month moving average (Q7), nation-level share of spend (Q8).

**Expected engineering challenges it forces**
Small-table broadcast joins; `lineitem`↔`partsupp` composite-key join (a real shuffle hazard); partition pruning on `o_orderdate`; sort-order benefit measurement with and without; ClickHouse `ORDER BY` key choice; predicate pushdown and late materialisation; compaction policy for a write-once table.

**Which target-job requirements it demonstrates**
"Apache Spark (batch silver/gold)" ✅. "Apache Iceberg tables on S3" ✅. "Apache Polaris (Iceberg REST catalog)" ✅ (many tables, needs catalog organisation). "ClickHouse serving layer… query performance tuning" ✅✅ (strongest in this report). "Expert SQL, dimensional/data modeling" ✅. "physical table layout: partitioning, sort order, compaction" ✅✅. "Data governance: catalog organization" ✅. **Debezium/Flink ❌ by design - say so.**

**Relationships to other candidate datasets**
- Natural companion to **A1**: same domain, so one gold layer serves both; you can even reconcile a TPC-C warehouse/district against a TPC-H nation/region.
- TPC-H's `nation`/`region` are far too thin to be a geographic story. Bolt on **B1** or **B3** explicitly as an enrichment.
- **A2 and A6 (TPC-DS) are substitutes, not complements.** Pick one for the batch leg.

---

### A3. Companies House Public Data API + Streaming API + bulk snapshots (UK)

**Dataset**
The UK statutory company register: company profiles, officers, persons with significant control, and every statutory filing with its transaction id, form type, category/subcategory and date. The closest thing to a real, live, relational OLTP-shaped source that is fully open.

**Source and URL**
- REST API home: `https://developer.company-information.service.gov.uk/`
- REST spec: `https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/`
- **Streaming API (the important one):** `https://developer-specs.company-information.service.gov.uk/streaming-api/reference/filing-history/stream` and `https://developer-specs.company-information.service.gov.uk/streaming-api/guides/overview`
- Rate limits: `https://developer-specs.company-information.service.gov.uk/guides/rateLimiting`
- Bulk products: `https://www.gov.uk/guidance/companies-house-data-products`
- Catalogue: `https://ckan.publishing.service.gov.uk/dataset/basic-company-data` (verified live; records **"Licence: Creative Commons Attribution"**)

**Licence (and whether it permits our use)**
- The **free** products (Basic Company Data, PSC snapshot, accounts data) are recorded on data.gov.uk as **Creative Commons Attribution**, and CH's open-data programme operates under the **Open Government Licence v3.0**. Attribution required. **Permits our use.**
- **Flag, important:** the **Corporate Dataset** (all statutory information, share allocation) is explicitly *not* open - data.gov.uk records its licence information as *"Supplied under section 47 and 50 of the Copyright, Designs and Patents Act 1988 and Schedule 1 of the Database Regulations (SI 1997/3032)"*. **Do not use the paid Corporate Dataset.** Stick to the free products and the API.
- **One verification step before publishing:** fetch the attribution statement on the actual download page and reproduce it verbatim. data.gov.uk metadata is a catalogue, not the licence.

**Size, format, file or table count**
- Basic Company Data: monthly snapshot, split across **several ZIPs containing CSV**, compiled to end of previous month, available within 5 working days. The UK has millions of live companies; expect multi-GB, tens of millions of rows. **A genuinely large relational dataset, not a toy.**
- PSC: a **daily** snapshot (JSON).
- API: JSON resources - `company-profile`, `officers`, `persons-with-significant-control`, `filing-history` (paginated: `items_per_page`, `start_index`, `total_count`).

**Update frequency; live or snapshot**
**Both, and this is the unique selling point.** Monthly snapshot **plus a real-time streaming feed**, and they are designed to interlock: the docs state the snapshots *"contain the stream `timepoint` at which they were taken"*, and you connect to the stream passing that `timepoint` to resume exactly where the snapshot stopped. **That is literally the snapshot/incremental contract a lakehouse CDC landing job needs, implemented by the publisher.**

**Tables and their relationships**
`company` (1) → `officer-appointment` (1:N) → `person` (1:N; an officer holds appointments at many companies - **the many-to-many**), `company` (1) → `psc` (1:N) → person/RLE (N:M with entities), `company` (1) → `filing-history-item` (1:N, keyed by `transaction_id`). Plus `associated-filings` (**self-referential M:M** on a filing) and `resolutions` (**nested array inside a filing item**). Real hierarchy, real self-reference, real nesting.

**Primary keys, natural and business keys**
- `company_number` is a genuine **business key** - a stable, non-sequential statutory number. Better than a surrogate, and exactly the "natural vs surrogate" modelling discussion the JD implies.
- `transaction_id` is the filing-history natural key. `resource_id` + `resource_kind` identify the resource in the stream.
- `etag` on REST resources is a real HTTP optimistic-concurrency token, useful for incremental pulls.

**Timestamp semantics and timezone behaviour**
Bare `date` on filings; **`event.published_at` is an RFC-3339 date-time with offset** in the stream; `event.timepoint` is a monotonic integer, not a timestamp. Registry dates are *event dates* (when a document was filed), distinct from *knowledge dates* (when CH learned of it) - **that distinction is exactly the late-arriving / ingest-time-vs-business-time problem the JD wants, and it is real here, not simulated.** No DST hazard (UK dates are dates), but `published_at` is a genuine tz-aware field.

**Nested or semi-structured content**
**Yes, and properly.** `annotations[]` (annotation + `date` + description), `associated_filings[]`, `resolutions[]` (each with its own `category`, `description`, `document_id`, `receive_date`, `type`), and `links` objects. **The only candidate in this report with first-class nested structures that carry their own timestamps.** A `struct<...date...>` column with a nested event date is a real Iceberg/Flink/ClickHouse exercise, and nothing else here does it.

**Expected data-quality problems actually present**
- `paper_filed: true/false` - not everything is digital.
- `filing_history_status` is `filing-history-available`; the field is **optional in the schema**, i.e. nullable at the resource level.
- **Deleted resources appear in the stream with `data` absent** - the spec says *"Data may be absent for 'deleted' event types."* A naive consumer assuming `data` is always present will crash. **A real, documented, will-happen bug, not an invented one.**
- `company_number` alone is insufficient without `company_type` - the same number space covers Soc, LLP, and LLP again, so entity type disambiguates.
- The `event.type` vocabulary is **not enumerated** in the docs; you must discover it empirically. A realistic governance problem - the honest response is to document the observed enum.
- The stream **cannot** give a complete copy of the data (their words) - incremental feed only.

**CDC suitability, and whether change events are real or synthesised**
**T2, and a very strong one.** This is the only candidate where the *publisher* emits real, dated, typed change events. The stream envelope carries `event.type`, **`event.fields_changed[]`** (a real field-level change list), `event.published_at`, `event.timepoint`, `resource_kind`, `resource_id`. `fields_changed` is effectively a **field-level change mask** - something Debezium's Postgres connector does not give you at that granularity for free. Events are real, attributable, produced by a real registry absorbing real statutory filings.
- **Honest caveat 1:** these are *API-level* events, not binlog events. No transaction id spanning multiple resources, no before-image (you fetch it or keep your own state), no atomicity across tables. Real changes, weaker transactional story than A1.
- **Honest caveat 2:** needs an API key and a persistent connection. **Max 2 concurrent streaming connections per key**; REST limit **600 requests / 5 min per key**, plus an unpublished IP limit of 2,000 / 5 min, and they reserve the right to ban for repeatedly exceeding limits. A demo that keeps dropping the stream and hammering reconnect is a realistic incident - use it deliberately and document the back-off. Also `416 Range Not Satisfiable` on a stale timepoint.

**Batch suitability**
Excellent. Monthly CSV snapshots are textbook batch. Millions of companies, officers and PSCs is a real bronze→silver→gold job at real volumes.

**Lakehouse and ClickHouse serving suitability**
- **Iceberg:** append-friendly monthly snapshots + MERGE-driven incremental. `fields_changed` gives a cheap, correct way to compute changed columns and drive SCD2.
- **ClickHouse:** good for "incorporations by SIC code and postcode per month" and for the officers-across-companies network query. Low cardinality on `company_type`, high on `postcode` and `sic_code` - decent primary-key choices.

**Realistic analytical questions it answers**
"Which SIC sectors saw the most incorporations per month, and what is time-to-first-accounts?" "How many directors hold appointments at more than N companies?" "What proportion of companies have a registrable PSC vs a PSC notice with no registrable person?" "Which officers were appointed to companies in the same month - an unusual cluster worth investigating?" That last one is a real company-fraud/AML heuristic and makes the demo feel purposeful.

**Expected engineering challenges it forces**
Snapshot+stream resumption with a `timepoint` cursor persisted **transactionally with your Iceberg commit** - crash between the Kafka offset commit and the Iceberg commit and you get duplicates; **exactly-once at the boundary**. Field-level change masks → SCD2. Nested structs with their own timestamps. REST pagination and rate-limit back-off. Credential hygiene (CH's own guideline: keys in env vars, never in the source tree, bound to source IP). Stream disconnection and heartbeat handling (blank lines must be ignored - a real parsing trap).

**Which target-job requirements it demonstrates**
"Debezium CDC → Kafka" ⚠️ (substitute: a real streaming change feed into Kafka - be explicit that it is not Debezium). "Apache Flink real-time streaming" ✅. "Iceberg / Polaris" ✅. "Data governance: catalog organization, access control, data lineage" ✅✅. "Automated data-quality checks" ✅. "Kafka Connect and Flink write into it" ✅. "ClickHouse serving" ✅. "Dagster" ✅ (monthly snapshot + continuous stream is a clean asset-vs-stream asset model). **"Own, operate and harden the streaming platform for reliability, correctness, and cost at scale" ✅✅** - the 2-connection limit, 429 handling, `416` on a stale timepoint, and IP-ban policy give you a real incident postmortem to write. "AWS fundamentals" ✅.

**Relationships to other candidate datasets**
- **Strong pair with B2 (ONSPD):** UK company registered-office postcodes → real UK postcode geography, real admin hierarchies, real easting/northing. `sic_code` is a real business classification. **Together: the most self-consistent pairing in the report** - a live change stream plus a quarterly-changing reference dimension, same country, same government, same licence family.
- **Pairs with A1** as a second, independent streaming source, so you can show a Debezium-derived stream *and* an API-derived stream in the same Kafka topic namespace.
- Does **not** pair with A4 - different countries, no shared key.

---

### A4. Olist - Brazilian E-Commerce Public Dataset

**Dataset**
Olist, Brazil's largest department store on marketplaces: ~100k real orders, 2016–2018, across sellers, products, customers, payments and customer reviews, plus a Brazilian postcode→lat/lon geolocation table.

**Source and URL**
- Primary: `https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce` (verified live; the page renders the licence as `CC BY-NC-SA 4.0`)
- Verified packaged derivative with documented row/table inventory: `https://github.com/datahub-project/static-assets/tree/main/datasets/olist-ecommerce`

**Licence (and whether it permits our use) - FLAGGED, read this**
- **The Kaggle dataset page itself renders the licence as `CC BY-NC-SA 4.0`.** Independently corroborated: the translated derivative on Kaggle states *"Source: Modified from Brazilian E-Commerce Public Dataset by Olist (CC BY-NC-SA 4.0)"*; multiple GitHub repos using it ship a separate `DATA_LICENSE.md` pinning *"Data (Olist Brazilian E-Commerce dataset): CC BY-NC-SA 4.0"* with MIT only for their own code.
- **Two flags, either of which is disqualifying-ish:**
  1. **NC (non-commercial).** A job-seeking portfolio is very likely non-commercial and therefore probably fine - but "probably" is doing real work there, and you would be relying on an interpretation.
  2. **SA (share-alike).** Any *adapted/derived* material - i.e. **your silver and gold Iceberg tables, your transformed Parquet, anything substantially derived** - must be licensed CC BY-NC-SA 4.0. That contaminates the rest of the project.
- **Verdict: usable, but it will constrain the licence of your derived data. Recommendation: do not build the primary on it.** If you use it, ship a `DATA_LICENSE.md`, reproduce the Olist attribution, and NC/SA-propagate the derived tables. Do not silently MIT-licence derived output.

**Size, format, file or table count**
**9 CSVs.** Verified row counts (packaged derivative, independently corroborated by a second profiling repo):

| Table | Rows |
|---|---|
| `olist_customers` | 99,441 |
| `olist_orders` | 99,441 |
| `olist_order_items` | 112,650 |
| `olist_products` | 32,951 |
| `olist_sellers` | 3,095 |
| `olist_order_payments` | 103,886 |
| `olist_order_reviews` | 99,224 (one source reports 104,719 - see DQ) |
| `olist_geolocation` | 1,000,163 |
| `product_category_name_translation` | 71 (one source reports 70) |

Individual files are small - e.g. `olist_customers_dataset.csv` 9.03 MB. **Total well under 100 MB.** It is *small*: a dimensional/reference-and-fact-shaped dataset, not a volume dataset.

**Update frequency; live or snapshot**
**Dead snapshot. 2016–2018, never updated.** Nothing live. Any "recent activity" you show is fiction.

**Tables and their relationships**
`customers (1) → orders (1) → order_items (N) → products (N) / sellers (N)`; `orders (1) → payments (1..N)`; `orders (1) → reviews (1..N)`. `products → product_category_name_translation` (a **lookup table, correctly treated as one**). `geolocation` maps to `customer_zip_code_prefix` / `seller_zip_code_prefix` with **many rows per postcode**. A proper source with three separate one-to-many children off `orders` - a genuine **join-fan-out trap**: joining items + payments + reviews in one query multiplies rows and silently inflates revenue. **That trap is the best thing about this dataset and it is real, not constructed.**

**Primary keys, natural and business keys**
- `order_id` is a real **UUID-style business key**, not a sequence.
- **`customer_id` vs `customer_unique_id`:** `customer_id` is **unique per order** (changes each purchase); `customer_unique_id` is the stable person. **Joining on the wrong one gives silently wrong results rather than an error.** Best natural-vs-surrogate-key teaching example in the report, and a documented property of the data.
- `order_item_id` and `payment_sequential` are per-order sequences. `review_id` is claimed unique but is not (see DQ).
- `geolocation` has **no primary key** - many lat/lon per postcode prefix. The join is explicitly many-to-one and must be aggregated or de-duplicated first.

**Timestamp semantics and timezone behaviour**
**Olist's best-in-class feature.** Five timestamps per order, all naive/local: `order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, plus `order_estimated_delivery_date` and a line-level `shipping_limit_date`. Realistically **Brazil local time (UTC−03:00) with no offset recorded**, and a published profiling pass found **24.1% of customer rows and 33.2% of seller rows lose a leading zero on the zip prefix** when read with a naive parser. So: real multi-stage event time, a **promise-vs-actual pair** that is a first-class SLA dimension, a naive-timestamp-with-known-offset problem, and a reproducible ingest bug. **Materially better timezone/event-time material than TPC-C or TPC-H, which have none.**

**Nested or semi-structured content**
No nested columns. But `review_comment_title` / `review_comment_message` are **free-text Portuguese**, and products carry `product_description_length` (a length metric, not the text). Semi-structured content exists as text, with a real decision about whether to keep it (pushdown, PII).

**Expected data-quality problems actually present - the strongest list in this report**
From an independent full-table profiling pass (verified, per-table):
- **Zip leading zeros lost on read:** 24.1% of `olist_customers`, 33.2% of `olist_sellers`. A *type-inference* bug that silently destroys your geographic join. Real, reproducible, and a perfect first data-quality check.
- **Geolocation is dirty:** 1,000,163 rows for ~20k unique zip prefixes = **26.2% exact duplicates**; **42 points geocoded outside Brazil entirely**; 2,037 city-name groups with inconsistent accent usage; needs a 3-tier outlier correction (zip median → state median → per-zip IQR capping).
- **Products:** 610 **incomplete listings** (category + metadata missing together, filled with the literal string `"unknown"` - a sentinel masquerading as data); **misspelled source columns `product_name_lenght` / `product_description_lenght`** (missing second "th"), a *published-schema* defect you inherit.
- **`olist_order_items` has 2 phantom all-NULL columns** from a trailing-comma artifact in the source CSV. Perfect schema-drift / ragged-CSV lesson.
- 4,634 order-item rows flagged, mostly **freight cost exceeding item price** (economically impossible).
- **Payments:** 2 rows with `payment_installments == 0`; **2,961 orders use split payments** - a second fan-out trap.
- **Reviews:** 789 distinct `review_id`s each linked to **2–3 different orders** - a primary-key violation a naive load silently absorbs.
- **Orders:** 1,429 rows flagged, mostly **carrier date before approval date** (impossible ordering).
- **Lineage/reproducibility:** `olist_order_reviews` is reported as both 99,224 and 104,719 rows by different sources, and the translation table as both 71 and 70. You must pin and record the exact upstream artefact hash. Good governance lesson, bad day for reproducibility.

**CDC suitability, and whether change events are real or synthesised**
**T3 - synthesised, and the honest weak point.** A final-state export with **no version history, no status-transition log, no prior states**. Ironically it is *full of* things that would be updates - `order_status` implies a lifecycle (`created → approved → invoiced → processing → shipped → delivered`, plus `unavailable`, `canceled`), and `order_approved_at` / `order_delivered_carrier_date` / `order_delivered_customer_date` are NULLs that were filled in later - but the export discarded the history. To get CDC you would load the final state and *invent* a replay moving each order through its transitions, inferring intermediate states from the timestamps. **That is a plausible, defensible simulation, and it must be labelled `simulated` in the README, the Dagster asset name, the Iceberg table properties, and the blog post.** A reviewer who spots unlabelled synthetic CDC will discount the whole project. This is exactly the risk the brief asked me to surface.

**Batch suitability**
**Very good.** 1.5M+ rows, real dimensional star, time-phased facts, a real SLA metric (delivery lateness vs promise), a real geographic drill-down. But it is small - Spark tuning at 1.5M rows is theatre unless you scale it, and scaling means synthesising more orders, further weakening the "real data" claim.

**Lakehouse and ClickHouse serving suitability**
- **Iceberg:** comfortable. Partition `orders` by `month(order_purchase_timestamp)`; quarantine the review text. Upserts are pointless (nothing updates), so **Iceberg v1 append-only is sufficient** - which means using Olist as your *only* source undercuts your ability to demonstrate v2 MERGE/equality-delete work. Another reason to pair, not lead. _Corrected 2026-09-27: the phrase "v2 MERGE/equality-delete work" pairs two different mechanisms. Spark's MERGE writes position deletes, not equality deletes; the equality-delete path belongs to the Flink sink. See [ADR-0002](../adr/0002-exactly-once-effect-not-delivery.md)._
- **ClickHouse:** good. `order_status`, `payment_type` (credit card = 78.3% of payment value; also `boleto`, `voucher` - a Brazil-specific payment dimension worth a comment), `customer_state` (27 federative units), `product_category_name_english`. Good `ORDER BY (month, customer_state, order_status)`.

**Realistic analytical questions it answers**
"Which state's customers have the worst delivery lateness versus the estimate?" "What is the true GMV, given split payments and multiple line items - and does the naive join over-count?" "Do sellers shipping from a distant state have systematically worse review scores?" "What share of GMV comes from the top 1% of sellers?" "Which categories have the highest freight-to-price ratio - logistics or pricing problem?"

**Expected engineering challenges it forces**
Fan-out prevention (revenue from line items, not from the items×payments join); dedup/aggregation on a table with no PK; a data-quality rule suite (leading zeros, out-of-country coordinates, impossible date ordering, freight>price, `installments=0`, sentinel `"unknown"`); PII classification (`customer_unique_id` and free-text reviews are PII-adjacent - directly relevant to *"retention/compliance"* and *"access control"*, and a good hook for a GDPR/HIPAA-shaped control); a translation-lookup join that leaves a residual untranslated set; handling misspelled and phantom columns under an explicit contract.

**Which target-job requirements it demonstrates**
"Expert SQL, dimensional/data modeling" ✅✅ (star schema, surrogate-vs-business keys, fan-out). "Automated data-quality checks" ✅✅ (richest genuine defect set in the report - Great Expectations / dbt tests have something real to assert). "Data governance… retention/compliance" ✅ (PII tagging, column access). "Spark batch silver/gold" ✅. "ClickHouse serving" ✅. "Data lineage" ⚠️ (the row-count discrepancy is a concrete lineage problem). "Debezium / Flink" ❌ **unless you synthesise - and then it is a much weaker claim.** "Production experience with an open table format" ⚠️ (append-only v1 only).

**Relationships to other candidate datasets**
- Its own `olist_geolocation` is the postal reference, and it is **too dirty to lean on - better replaced than patched**. Substitute **B3 (GeoNames)**.
- `product_category_name_translation` is a 71-row **flat** lookup - **no hierarchy**. If the story needs hierarchical taxonomy, source one externally; Olist does not provide it.
- Pairs thematically with A1/A2 (commerce) but with no shared key. Structurally with A3 (relational + reference + geography) but not by key.

---

### A5. Sakila (MySQL/PostgreSQL DVD-rental sample database, via jOOQ)

**Dataset**
The Sakila sample database: a fictional video-rental chain, **16 logical tables**, maintained by jOOQ in a multi-engine repository.

**Source and URL**
- `https://github.com/jOOQ/sakila` - **verified via GitHub API: BSD-2-Clause**, last pushed 2026-04-20, 520 stars, 3.8 MB repo
- Schema/insert pairs per engine: `mysql-sakila-db/`, `postgres-sakila-db/` (50,732-byte schema + 7,963,146-byte insert script **and** a 2,661,287-byte `USING COPY` variant), plus `db2-`, `oracle-`, `sql-server-`, `cockroachdb-`, `yugabytedb-`, `sqlite-sakila-db/`
- **I fetched and counted the Postgres schema: 21 `CREATE TABLE` statements, of which 5 are the composite-PK partitions `payment_p1..p5` (range-partitioned `payment`) → 21 − 5 = 16 logical tables.** Confirmed.
- Also: `https://github.com/sakiladb/mysql` (Docker image, BSD-3-Clause), `https://github.com/hibernate/sakila-h2` (Apache-2.0)

**Licence (and whether it permits our use)**
**BSD-2-Clause - the cleanest licence in this report.** Permissive, no copyleft, no NC, no attribution obligation beyond the notice. **Unambiguously permits our use, including commercial.** Note the divergence across mirrors (BSD-2 / BSD-3 / Apache-2.0): **pin one and record it.**

**Size, format, file or table count**
16 logical tables, ~3.8 MB repo, single-file SQL per engine. Standard row counts: `film` 1,000, `actor` 200, `film_actor` 5,462, `film_category` 1,000, `category` 16, `customer` 599, `store` 2, `staff` 2, `inventory` 4,581, `rental` 16,044, `payment` 16,044, `address` 603, `city` 600, `country` 109, `language` 6. **~45k rows total.** The single biggest problem with Sakila as a portfolio dataset.

**Update frequency; live or snapshot**
Static snapshot. No cadence.

**Tables and their relationships**
`country → city → address → customer/store/staff`; `customer → rental → inventory → film`; `film → film_actor → actor` (**many-to-many**: 5,462 links over 200 actors and 1,000 films - ~5.5 actors/film with a power-law tail) and `film → film_category → category` (**M:N**); `customer → payment`. So Sakila has **two** many-to-many bridges and a full four-level geographic hierarchy. **Structurally the best relational shape in the report.**

**Primary keys, natural and business keys**
All surrogate: `film_id`, `actor_id`, `customer_id`, `rental_id`, `payment_id`. Business keys: `film.sku`; `rental_date + inventory_id + customer_id` as a natural composite; `actor.last_name + first_name` as a soft key. `payment` is **range-partitioned on `payment_date`** (hence the 5 `payment_p*` tables) - an unusually good, real partitioning example baked into the source.

**Timestamp semantics and timezone behaviour**
`rental_date`, `return_date`, `payment_date`, `create_date`, and **`last_update` on every one of the 16 tables**. All naive, no timezone, no DST. `rental.return_date` is NULL for open rentals - a genuine nullable-lifecycle column. **`last_update` is `TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP`, so loading Sakila and then mutating any row changes `last_update`** - a real, natural, in-schema UPDATE signal. Small but genuinely useful for a CDC demo.

**Nested or semi-structured content**
**None.** Flat.

**Expected data-quality problems actually present**
Sakila is **clean by construction** - referentially perfect, no NULL keys. Same weakness as TPC-H. The genuine quirks are schema-level: `film.length` is minutes; `rental_rate`/`replacement_cost` are currency with no currency column; **`film.special_features` is a pipe-delimited pseudo-array in a VARCHAR** (`'Trailers|Commentaries|Deleted Scenes|Behind the Scenes'`) - the closest thing to semi-structured data here and a real, if mild, parsing exercise; `payment` is partition-split, so a naive `SELECT *` without partition pruning is a real (small) performance bug. Also: **jOOQ regenerated `rental_rate` and `length` when modernising the dataset, so row values differ from the original MySQL sample** - a genuine cross-source inconsistency if you compare copies. Footnote, not pillar.

**CDC suitability, and whether change events are real or synthesised**
**T3, and the weakest in the report.** There is no workload specification whatsoever, so you would invent every mutation. Sakila gives you *nothing* to replay. Its only CDC value is the `last_update` ON-UPDATE trigger. **~45k rows cannot produce a meaningful change stream** - use Sakila as a smoke test / tutorial tier, not as a source. Say that plainly.

**Batch suitability**
Weak on volume; the queries are the classic teaching set (top-N customers, revenue by category, films never rented, active vs overdue inventory). Useful as a "here is the star schema, done correctly" walkthrough on a readable dataset - real value for a reader who must understand your modelling before they care about your partitioning.

**Lakehouse and ClickHouse serving suitability**
Structurally fine, volumetrically pointless. A 45k-row lakehouse table is a rounding error; you cannot show compaction, partition pruning or cost optimisation on it. **One genuine exception: the money.** `film`↔`film_actor`↔`actor` and `film`↔`film_category` give a clean, correct **join-fan-out** demo where `COUNT(*)` vs `COUNT(DISTINCT film_id)` differ visibly, and `special_features` gives an array-in-a-string column. At this size you can *prove* correctness of the model, which you cannot at 600M rows.

**Realistic analytical questions it answers**
"Which films are never rented, and what does that cost?" "Revenue by category - which category drives the most rentals per dollar of inventory?" "Which actors appear in the most rented films, and does that survive the M:N fan-out?" "Average rental duration; which customers always return late?" "Where are the inventory gaps - films customers wanted that were never in stock?"

**Expected engineering challenges it forces**
Join fan-out and `COUNT(DISTINCT)` discipline across two M:N bridges; parsing a delimiter-separated `VARCHAR` into an Iceberg `array<string>`; temporal NULL handling on `return_date`; a range-partitioned source table and why you probably re-partition in the lakehouse anyway; a deliberate SCD2 decision on `film` (price changes) and on `staff`/`store`.

**Which target-job requirements it demonstrates**
"Expert SQL, dimensional/data modeling" ✅ (best-in-class for *teaching*). "Open table format / lakehouse" ⚠️ (toy scale). "ClickHouse" ⚠️. "Spark/Flink/Debezium" ❌. **Value it for:** a clean, readable, licence-unencumbered 16-table relational reference a reader can diff against. Genuinely valuable, and a five-minute download.

**Relationships to other candidate datasets**
Its `country`/`city` (109/600 rows) is a geographic reference but is **fictional and tiny**. If geography is part of the story, replace it with **B1/B3** and keep Sakila for the M:N shape. `category` (16 rows, flat) is the classic "flat dimension" example; a hierarchical taxonomy must come from elsewhere.

---

### A6. TPC-DS (revision 4.0.0)

**Dataset**
Retail decision-support benchmark with a deliberately awkward schema (24 base tables plus 12+ views), 99 queries, and parallelisable data generation.

**Source and URL**
`https://tpc.org/tpc_documents_current_versions/current_specifications5.asp` - TPC-DS v4.0.0, tools `TPC-DS_Tools_v4.0.0.zip` (official TPC source linked from that page).

**Licence (and whether it permits our use)**
Same TPC permission-with-notice class as A1/A2. Permits portfolio use with attribution. **Cleaner licence situation than TPC-C, because TPC publishes the tools here** - no third-party loader ambiguity.

**Size, format, file or table count**
**24 base tables** (`store, call_center, catalog_page, catalog_returns, customer, customer_address, customer_demographics, household_demographics, inventory, item, promotion, reason, ship_mode, store_returns, time_dim, truck, warehouse, web_page, web_returns, web_site, web_session, catalog_item, inventory_item, date_dim`) plus **~12 views** and the `web_site`/`call_center`/`warehouse` cross-dimension schema. Format: text `.dat` load files + DDL. `dstdgen` shards across threads/rows.

**Update frequency; live or snapshot**
**Snapshot only. Insert-only. No UPDATE, no DELETE.** The `reason` dimension models return reasons but is a static dimension, not a mutation log.

**Tables and their relationships**
Three fact families (`store_sales`, `catalog_sales`, `web_sales`) each with header/line pairs (`store`, `store_returns`, `catalog`, `web_session`, `web_page`, `web_site`) plus three inventory views over `inventory`, `item`, `catalog_item`, `inventory_item`, `warehouse`, `call_center`. Multiple fact tables with **different grains and overlapping keys** (`inv_date_sk`, `item_sk`, `catalog_page_sk` participate in all of them). **Heterogeneous grain is exactly the "design data models" problem the JD names, and it is real here.**

**Primary keys, natural and business keys**
Surrogate skeys throughout, plus real business keys: `item_id`, `customer_id`, `call_center_id`, `catalog_page_id`, return `id`. `date_dim` is a proper **role-playing date dimension** with flags (`ab_flag, holiday_flag, weekend_flag, month_name, quarter_name, year, decade, century, day_of_week`) - the best small date dimension among all candidates, designed for exactly the star-schema demo. `i_item_desc` and the `*_demographics` tables are deliberately wide attribute blobs.

**Timestamp semantics and timezone behaviour**
`date_dim` spans 1900–2100 with `d_date`, `d_day_name` etc.; facts carry `*_date_sk` FKs rather than raw timestamps. **No timezone anywhere.** A date-dimension demo, not a temporal demo.

**Nested or semi-structured content**
None structurally, but `household_demographics` and `customer_demographics` are **code tables where the value is a multi-flag type code** (`income_band` + `credit_rating` + `marital_status` + …) - **semi-structured data hidden inside a scalar column.** Extracting it is a real, unglamorous, realistic task.

**Expected data-quality problems actually present**
- **Sentinel `"null"` strings** are explicitly seeded into many columns, so you must distinguish a SQL NULL from the literal string `"null"` - a classic, real, easy-to-get-wrong ingest defect.
- Multi-fact overlap means naive `UNION ALL` across `store_sales`/`catalog_sales`/`web_sales` silently double-counts.
- Its fame is partly *because* the schema is unpleasant. That is the point, and also the cost: 24 tables + 12 views is a lot of modelling before the interesting engineering.

**CDC suitability, and whether change events are real or synthesised**
**T3 / not applicable.** Insert-only snapshot, no workload spec. **Do not use TPC-DS for the CDC leg.** Use it, if at all, for the awkward-dimensional-modelling leg.

**Batch suitability**
Very good. 99 queries, heterogeneous grains, a reference benchmark for Spark SQL tuning discussions.

**Lakehouse and ClickHouse serving suitability**
Good, and **better than TPC-H on one specific point:** TPC-H's schema is so clean it never forces a decision about overlapping fact grains; TPC-DS does. If your pitch is "expert dimensional/data modeling", TPC-DS is more convincing. If your pitch is "here is a fast serving layer", TPC-H is.

**Realistic analytical questions it answers**
The 99 TPC-DS queries, e.g. "customer demographics vs returns by channel", "which promotions drove catalog sales", "inventory turns by warehouse and item category". Plus: "how do I model three sales channels at different grains without lying about any of them?"

**Expected engineering challenges it forces**
Heterogeneous-grain unification; `date_dim` role-playing; avoiding fan-out across the three sales facts; `NULL` vs `'null'`; fact-table width; classifying 24 tables into facts, conformed dimensions and junk dimensions.

**Which target-job requirements it demonstrates**
"Expert SQL, dimensional/data modeling" ✅✅ (best in report). "Spark batch" ✅✅. "Iceberg/Polaris catalog organization" ✅ (24 tables + 12 views makes catalog layout a real decision). "ClickHouse" ✅. Debezium/Flink ❌.

**Relationships to other candidate datasets**
Supersedes A2 for *modelling* depth and substitutes for it on *volume*; **pick one, not both.** Shares the retail domain with A4, so A4's real data could be mapped onto a TPC-DS-shaped model - but that is a modelling exercise, not an integration, and I would not claim it as one.

---

### A7. Synthea™ Patient Generator

**Dataset**
A synthetic patient-population simulator producing longitudinal EHR-shaped records - patients, encounters, conditions, allergies, medications, immunisations, observations, labs, procedures, care plans - in HL7 FHIR (R4/STU3/DSTU2), C-CDA, CPCDS and CSV.

**Source and URL**
`https://github.com/synthetichealth/synthea` - README verified live; CSV export requires `exporter.csv.export = true`; bulk FHIR ndjson requires `exporter.fhir.bulk_data = true`; run via `./run_synthea [-s seed] [-p populationSize] [state [city]]`.

**Licence (and whether it permits our use)**
`https://github.com/synthetichealth/synthea/blob/master/LICENSE` is **Apache License 2.0** (verified - I read the file). Permissive, patent grant, no copyleft, no NC. **Unambiguously permits our use.**
- **Flag I could not fully resolve:** the repo *code* is Apache-2.0, and the docs stress the data is *"realistic (but not real)"*. I did not locate a separate explicit licence statement for the generated output distinct from the repo licence. Treat the output as Apache-2.0-ish, but **state in the repo that you are relying on the repo licence and that the data is synthetic.** Do not claim the output is CC0.

**Size, format, file or table count**
CSV output is a flat file set (patients, encounters, conditions, observations, medications, immunisations, allergies, careplans, providers, payer_transitions, cost, …); FHIR output is **ndjson/bulk, genuinely nested** (`Patient`, `Encounter`, `Condition`, `Observation` each with nested `identifier`, `code.coding[]`, `period`, `performer[]`). Size is parameterised by `-p populationSize`, so **arbitrarily scalable.** This is the only candidate producing both arbitrary scale *and* genuine nesting.

**Update frequency; live or snapshot**
**Snapshot of a simulated longitudinal history.** Content is deeply temporal (encounters accumulate over a birth-to-death lifecycle) but there is no live feed and no mutation log. A run is a batch.

**Tables and their relationships**
`patients → encounters → (conditions | observations | medications | immunisations | procedures | allergies)`; `providers`, `payers`/`payer_transitions` as reference; `careplans`. Clean clinical many-to-one hierarchies. **And it exports straight to HL7 FHIR** - a nested, code-ful, identifier-bearing interchange format. If you want a genuine semi-structured/JSON ingest path, this is the answer.

**Primary keys, natural and business keys**
Realistic surrogate ids **plus** genuine business keys: `mrn` (medical record number), SSN-shaped identifiers, NPI-shaped provider ids. Deliberately designed to look like a real EHR, which means the keys look like the awkward ones you meet in practice.

**Timestamp semantics and timezone behaviour**
**Strongest suit.** A full birth-to-death lifecycle with encounter start/stop, condition onset/abatement, medication start/stop, immunisation dates - so you get real **interval/event-time** structure, `START`–`END` validity ranges (**the precondition for SCD2 and temporal joins**), and FHIR `dateTime`/period semantics. **Caveat I could not verify: whether Synthea emits explicit timezone offsets.** FHIR `dateTime` permits them. **Verify on a real run before claiming timezone correctness.**

**Nested or semi-structured content**
**Best in the report.** FHIR R4 is `Resource` → `identifier[]` → `code.coding[]` → `period` → `performer[]`, and `CodeableConcept` requires a *list* of codings. CSV mode flattens and loses the nesting - so **use FHIR if you want nesting, CSV if you want joins.** A real, defensible architectural choice you can explain.

**Expected data-quality problems actually present**
- **Everything is synthetic, so there are no accidental quality problems.** You would be manufacturing defects, which is a T3 disclosure again.
- **The structural problems are real:** overlapping validity ranges, conditions that resolve and recur, duplicate-looking observations, and free-text `reason`/`note` blocks that in a real deployment are PII-adjacent.
- **PII-adjacent surface:** names, addresses, SSN/MRN, dates of death. Synthea's data is not derived from real people, which is exactly why it is the right choice to demo a PII/retention control. But **the "HIPAA" you demo would be theatre** - nothing here is covered by a real agreement. Say *"HIPAA-shaped control"*, not *"HIPAA compliance"*.

**CDC suitability, and whether change events are real or synthesised**
**T3.** Output is a final-state file set. To get CDC you would re-run Synthea with a later horizon and diff - a legitimate, interesting technique (**two runs, same seed, different horizon → a real change stream of "what happened between year N and N+1"**) but **derived, not binlog-level**, and reproducibility depends on the seed. Worth an appendix; not a spine.

**Batch suitability**
Very good. FHIR bulk is ndjson and needs care; CSV mode is a normal multi-table batch job.

**Lakehouse and ClickHouse serving suitability**
Good. Natural ClickHouse model: fact `encounter` × dimensions `diagnosis (ICD-10 via FHIR coding)`, `provider`, `payer`, `patient`. Nested `code.coding[]` becomes an `Array(Tuple(system, code, display))` - a real, defensible, ClickHouse-native semi-structured design. **"Flatten FHIR into a star, keep the raw ndjson in bronze" is exactly the two-layer argument a lakehouse portfolio should make.**

**Realistic analytical questions it answers**
"Which conditions are rising fastest in the population, by age band?" "Total cost of care per condition, joined to payer type?" "Which providers see higher-acuity patients, after risk adjustment?" "Care gaps: which patients with a diagnosed condition are not receiving the corresponding medication?"

**Expected engineering challenges it forces**
ndjson bulk ingest at scale; FHIR resource→relational flattening with codings collapsing into a bridge table (a third M:N in the project); validity-range modelling and temporal joins; preserving raw alongside modelled; PII handling.

**Which target-job requirements it demonstrates**
"Apache Spark (batch)" ✅. "Iceberg" ✅. "ClickHouse" ✅ (the `Array(Tuple)` design is a genuine serving-layer talking point). "Proficiency in Python, Java, or Scala" ✅ - **Synthea is a Java application, and the one place in this report where the JD's language requirement is demonstrated by a data tool you actually run rather than a script you wrote.** "Security and compliance frameworks (GDPR, HIPAA, SOC 2)" ⚠️ (HIPAA-shaped only). Debezium/Flink ❌.

**Relationships to other candidate datasets**
Best candidate for the **semi-structured** requirement that nothing else in this list satisfies. No shared domain with A1/A2/A4/A6, so a coherent single story needs A4 or A6 for the commerce side. Synthea has its own (generated) geographic dimension - pair with **B1/B3** if you want real geography.

---

### A8. SEC EDGAR XBRL `companyfacts`

**Dataset**
Every XBRL fact every US public company has ever filed, per company, as JSON - with accession numbers, fiscal periods, `form` type, `filed` date, `frame`, and `start`/`end` dates.

**Source and URL**
`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` - **verified live: Apple's CIK returned HTTP 200 with 3,789,099 bytes in one request.** Submitter index and the EDGAR data policy: `https://www.sec.gov/os/accessing-edgar-data`.

**Licence (and whether it permits our use)**
US federal government works are in the **public domain under 17 U.S.C. § 105**. **Permits our use, unambiguously, with no attribution requirement** (attributing SEC is polite).
- ⚠️ **Operational flag, not licence:** SEC's fair-access policy requires a descriptive `User-Agent` with contact information and throttles anonymous access. My 3.8 MB single-file fetch succeeded, but **polite back-off and a real `User-Agent` are mandatory.** I used a placeholder in testing; you must use a real one.

**Size, format, file or table count**
**One JSON document per company.** Apple's is 3.8 MB; large filers far larger. Enormous file counts if you cover the full EDGAR population, so this is a **selective-crawl** dataset, not a bulk download. Format: `{cik, entityName, facts: {us-gaap: {Concept: {label, description, units: {"USD": [{start, end, val, accn, fy, fp, form, filed, frame}, ...]}}}}` - **four-level nesting with a fact list at the bottom.** The most structurally demanding semi-structured input in this report.

**Update frequency; live or snapshot**
**Incremental quarterly refresh plus ad-hoc filings.** `data.sec.gov` republishes `submissions/CIK##########.json` as filings arrive, and the `filings.files` index itself grows as archives roll off the `filings.recent` window. Filers can and do submit at any time, and a **10-K/A amendment can arrive years after the original fact**, so the stream of change is genuinely irregular rather than clock-driven. **Snapshot-first with a real, unbounded tail of late corrections** - which is exactly the cadence profile a lakehouse incremental job has to be designed around, and the reason long retention is not optional here.

**Tables and their relationships**
Not tables, but a real dimensional model hiding inside: `entity (cik)` → `taxonomy` (`us-gaap`, `dei`, `ifrs-full`) → `concept` → `unit` → `fact` rows. Concepts relate by taxonomy hierarchy (parent/child presentation links) - a genuine classification hierarchy. `dei` gives the entity's *own* reported facts (name, fiscal year end, auditor, filer category, SIC) - a self-describing dimension.

**Primary keys, natural and business keys**
- `cik` = **the natural/business key** (stable 10-digit zero-padded registrant identifier) - the right thing to join on, and the classic **leading-zero trap** if ingested as an integer (Olist's zip bug again, different dataset).
- `accn` (accession number) = **filing identity**. `accn` + `concept` + `unit` + `end` is a natural composite key for a fact.
- **The genuinely interesting one:** the *same* (entity, concept, period) can appear under **different `accn` values** because a 10-K/A amendment restates a previously filed period. **That is a real UPDATE, from a real filer, for a real reason (restatement), arriving years after the original fact.** An SCD-with-correction semantic no synthetic generator reproduces faithfully.

**Timestamp semantics and timezone behaviour**
Facts carry `start`/`end` (period) and `filed` (knowledge date, an ISO date from EDGAR, all-US-Eastern business dates). **The `end`-vs-`filed` gap is the whole point:** a fact about FY2018 might be `filed` in 2019 and restated in 2021. This is the canonical **late-arriving / bitemporal** problem, present in a real primary source. No timezone offsets on the dates (Eastern business dates) - **tz handling is not the win here; bitemporality is.**

**Nested or semi-structured content**
`taxonomy → concept → unit → fact[]` is four levels with heterogeneous shapes per taxonomy. Flattening requires the two-pass approach (explode concepts, then explode facts) - real Spark work.

**Expected data-quality problems actually present - excellent, and all real**
- **Restatements and amendments** (10-K/A, 10-Q/A) produce conflicting values for identical (entity, concept, period). You must implement latest-`filed`-wins or keep the whole history. A great data-quality rule.
- **Dimensional drift:** filers adopt and abandon concepts over time, so "the same" line item is not always the same `us-gaap` concept. Concept mapping is a genuine governance problem, and a real one in practice.
- **Units vary** - same concept in `USD`, `USD/shares`, `pure`. Unit confusion is classic silent corruption.
- **Instantaneous vs duration facts are mixed:** `dei:EntityCommonStockSharesOutstanding` has no `start`; `us-gaap:Revenues` is a duration. Unioning naively is a real bug.
- **Fiscal calendars differ** - a company's FY end is not December 31 for everyone, so calendar roll-ups need `frame`, not `end`.
- **The `dei` facts for the filer itself (auditor, SIC, fiscal year end) are themselves restated** - a dimension that changes over time.
- `filings.recent` is capped; older filings live in year-partitioned files. Missing-archive behaviour is a real completeness bug.

**CDC suitability, and whether change events are real or synthesised**
**T2 - real change at file level.** Every quarterly `submissions/CIK##########.json` refresh adds newly filed documents; the `filings.files` index itself grows; restatements are real corrections to already-published facts. An incremental crawler produces a genuine, dated, real change feed.
- **Honest caveats:** it is a *document-arrival* feed, not a *row-mutation* feed. No before-image, **no delete** (SEC never retracts a filing - it supersedes it), no transaction boundary. The "delete" semantic is **supersession**, which you must implement as a soft delete. **State that.**
- **Having both - a real T1 binlog stream from A1 and a real T2 document feed from A8 - is a strong portfolio story**, because it shows you understand that "change data" is a family of problems, not one.

**Batch suitability**
Excellent. Highly incremental by nature (only new filings since last run), which makes a bronze/silver/gold split natural and makes Dagster materialisation incremental in a way that looks authentic.

**Lakehouse and ClickHouse serving suitability**
- **Iceberg:** the fact table is append-only with natural overwrite semantics (latest `filed` wins) - a clean MERGE-by-business-key story. **Long retention with compaction is justified because restatements arrive years later. This is arguably the best retention/compaction argument in the report, because the late-arriving data is real.**
- **ClickHouse:** `ReplacingMergeTree` keyed on `(cik, concept, end)` ordered by `(end, filed)` is the *textbook* correct design for bitemporal facts, and you can show why `AggregatingMergeTree` or a plain `MergeTree` gives wrong answers.

**Realistic analytical questions it answers**
"What did company X report for revenue in FY2018, and how much did that change after the 2019 amendment?" "Which companies restated revenue in the most recent filings, and by how much?" "Sector-level (SIC) aggregates on a restated basis vs as-originally-filed." "Distribution of `EntityCommonStockSharesOutstanding` by fiscal quarter, given differing fiscal calendars." All four are questions real analysts ask and naive pipelines get wrong.

**Expected engineering challenges it forces**
Four-level JSON flattening in Spark without exploding memory; bitemporal SCD2/MERGE on `(cik, concept, end)` with latest-`filed`-wins; unit normalisation; instantaneous-vs-duration handling; fiscal-calendar normalisation via `frame` vs `end`; polite crawling with back-off and a real `User-Agent`; partial-incremental archive discovery; **a lineage story that is honest about the fact that the source of truth restates itself.**

**Which target-job requirements it demonstrates**
"Apache Spark batch silver/gold" ✅✅. "Apache Iceberg" ✅✅ (MERGE + retention). "Apache Polaris" ✅. "ClickHouse serving" ✅✅ (`ReplacingMergeTree` bitemporal design). "Data governance… lineage, retention" ✅✅ (restatement lineage is *the* lineage story). "Automated data-quality checks" ✅. "AWS fundamentals" ✅. "data lineage (OpenLineage/Marquez)" ✅ - a natural fit. Debezium/Flink ❌.

**Relationships to other candidate datasets**
- The `dei` taxonomy gives every entity a **SIC code**, a real business classification - a genuine (flat) dimension you can enrich with a hierarchical industry taxonomy.
- `dei:EntityAddress` is **not** in `companyfacts`, so **geography is thin here**; you would need a separate SIC-to-location or company-HQ source. Do not over-claim.
- Pairs with A1 (different domain) but pairs **methodologically**: A8 is T2, A1 is T1, and showing both is the argument.

---

### A9. Debezium tutorial "inventory" schema - smoke-test tier only

**Dataset**
Debezium's own 4-table tutorial schema, as shipped in its container-images examples.

**Source and URL**
- `https://github.com/debezium/container-images/blob/main/examples/postgres/3.0/inventory.sql` - **verified live**
- Also `examples/mysql/3.0/inventory.sql`, `examples/mariadb/3.5/inventory.sql`
- **Negative finding worth recording:** the widely-referenced `debezium-postgres-decathlon` (20-table inventory DB) - I checked, and **both `debezium/debezium-postgres-decathlon` and `debezium/debezium-example-data` return HTTP 404 on GitHub as of 2026-09-27.** A full recursive tree listing of `debezium/debezium@main` (`truncated: false`) contains **no `decathlon` path and no `mysql-server` examples directory**. Since the rest of the tree is intact, this is a genuine absence, not a fetch failure. **Do not plan around decathlon - it appears to be gone.**

**Licence**
Debezium is **Apache-2.0**, the same licence as Synthea. Permits our use. **Cleanest in the report alongside A5/A7.**

**Size, format, file or table count**
**4 tables** - `products` (id SERIAL PK, name, description, weight FLOAT), `products_on_hand` (product_id PK + FK, quantity), `customers` (id SERIAL PK, first_name, last_name, **email UNIQUE**), `orders` (id SERIAL PK, `order_date DATE`, purchaser INT FK→customers, quantity, product_id INT FK→products). Schema DDL + small seed inserts. **Dozens of rows.**

**Update frequency; live or snapshot**
Static seed. The tutorial's whole point is that *you* then issue INSERT/UPDATE/DELETE by hand and watch Debezium emit `c`/`u`/`d` with `before`/`after`/`source.lsn`/`source.txId`/`source.snapshot` populated.

**Tables and their relationships**
`customers 1→N orders N→1 products 1→1 products_on_hand`. Two FKs, one unique natural key, one surrogate PK. That is the whole model.

**Primary keys, natural and business keys**
`SERIAL` surrogates throughout; `email` is the one business key and the one **unique constraint** - which is also the **natural-key soft-delete trap**: with an email-based business key, "customer deleted and re-created" produces an UPDATE rather than INSERT+DELETE. A real, commonly-missed upsert correctness issue.

**Timestamp semantics and timezone behaviour**
`orders.order_date` is a bare `DATE`; no `timestamptz` in the base tutorial. Debezium variants add `created_at`/`modified_at TIMESTAMP(6)`. **Debezium serialises Postgres `timestamptz` as microseconds-since-epoch integer** (e.g. `1712934636990657`) in the `after`/`before` payload - a real, documented Debezium output detail. **Worth demonstrating precisely because it is a genuine connector nuance**, but it is a nuance on top of almost no data.

**Nested or semi-structured content**
None. (The MySQL/MongoDB tutorial variants add `enum`, `json` and `geometry` columns to *test* Debezium's type mapping, but the base schema has none.)

**Expected data-quality problems actually present**
**None, deliberately.** 4 tiny clean tables. Its purpose is connector plumbing, not data.

**CDC suitability - T1, and that is the point**
**T1 and real, but at toy scale.** Running a Postgres and watching a genuine `op: "u"` record with a non-null `before` is a *real* Debezium demo, worth doing as the **first commit** to prove the pipeline end-to-end in an afternoon. Not a portfolio headline.

**Batch suitability**
Effectively nil. Dozens of rows; nothing to batch. Present only to prove connectivity.

**Lakehouse and ClickHouse serving suitability**
Effectively nil at this scale. Present only to prove the Debezium -> Kafka -> Flink -> Iceberg -> ClickHouse path works before you swap in a real source. The value is entirely in de-risking, not in the result.

**Realistic analytical questions it answers**
None. It is a plumbing fixture.

**Expected engineering challenges it forces**
Snapshot-then-stream boundary handling; `REPLICA IDENTITY FULL` to get non-null `before` on UPDATE/DELETE; publication vs `schema.include.list` config; connector restart/resume. **The right things to learn first, the wrong things to build a portfolio on.**

**Which target-job requirements it demonstrates**
"Debezium CDC → Kafka" ✅ (smoke test only). "Kafka Connect" ✅. Nothing else.

**Relationships to other candidate datasets**
Nothing shares its schema. Use it as a **Day-1 harness**: get Debezium→Kafka→Flink→Iceberg→ClickHouse working end-to-end on these 4 tables, then swap in A1 or A3 as the real source without changing the pipeline. **That ordering belongs in the README.**

---

### A10. Stack Exchange data dump - **REJECTED**

Assessed in full because it is the most tempting candidate in this angle, and the rejection is instructive.

**Dataset**
Quarterly XML dumps of Stack Exchange: `Posts`, `PostHistory`, `Users`, `Comments`, `Votes`, `Badges`, `PostLinks`, `Tags` (8 tables per site; SEDE exposes ~29).

**Source and URL**
`https://meta.stackexchange.com/questions/401324/announcing-a-change-to-the-data-dump-process`; schema doc at `https://meta.stackexchange.com/questions/2677/database-schema-documentation-for-the-public-data-dump-and-sede`

**Licence - REJECTION REASON 1 (share-alike + a contested access gate)**
- User content is **CC BY-SA 4.0** and the dump is published under **CC BY-SA 4.0**, attribution required.
- **SA is the problem:** adapted/derived works must be shared under the same licence - the same contamination issue as Olist, applied to a dataset everyone wants to use commercially.
- The download flow **requires a site login and a click-through** asserting *"the file is being provided to me for my own use and for projects that do not include training a large language model (LLM)"*, and separately inviting commercial users to "join the socially responsible AI movement." Community legal commentary on Meta documents the argument that imposing non-commercial restrictions on a BY-SA work breaches the "no additional restrictions" clause, and that a *conditional access* arrangement is a different question from a *licence* modification. **Whether or not you side with them, the practical fact is: the terms are actively disputed, and I will not build a portfolio's data provenance on a disputed clause.** SE also moved the dump **off archive.org** at their own request.
- **Verdict: rejected on licence risk, and on being a contested licence at all.**

**Size, format, file or table count**
XML, 7z-compressed, per-site per-quarter. `PostHistory.xml` for a mid-size site was ~130 MB uncompressed in one published listing. Large, but **not automatable unattended** - see below.

**Update frequency; live or snapshot**
Quarterly snapshot. Historical.

**Tables and their relationships**
`Users`, `Posts` (self-referential via `ParentId` for questions/answers), `Comments`, `PostHistory` (→ `Posts`, → `Users`, → `PostHistoryTypes`), `PostLinks` (A→B M:N), `Tags`/`PostTags` (M:N), `Votes`, `Badges`. Genuinely relational, genuinely M:N.

**Primary keys, natural and business keys**
`Id` surrogate; `PostHistoryId` monotonic. Adequate.

**Timestamp semantics and timezone behaviour**
`CreationDate` / `LastActivityDate` / `DeletionDate` (null for live posts) on `Posts`; `CreationDate` on `PostHistory`. **UTC.** And crucially **`PostsWithDeleted` is a real second table holding deleted rows, plus `DeletionDate`** - **the only candidate in the report with genuine DELETEs and a real change history already in the dump.**

**Nested or semi-structured content**
None (flat XML). Post bodies are deeply nested HTML.

**Expected data-quality problems actually present - and this is what makes it tempting**
- **`PostHistory` is a real, publisher-authored change log** with a `PostHistoryTypeId` enum covering edits, rollbacks, vote-based close/reopen, migrations, merges, notices. **A genuine, real, dated, typed change feed sitting in a static file.** Nothing else in this report except A3 offers that without a live connection.
- The `Posts` table is the *current* state; `PostHistory` is the *audit log*. Deriving updates from it is real temporal-reconstruction work.

**CDC suitability - better T2 than I expected, and that is why it is worth writing down**
**T2 in principle.** You could construct a real change stream by ordering `PostHistory` by `CreationDate` and replaying post states; restores, migrations and deletions are all real. **But** that is a *reconstruction* from a quarterly snapshot, not a live stream, and it is closer to A8 (document feed) than to A1. **A good idea attached to a bad licence.** Rejected, with the reasoning recorded so it is reusable.

**Batch suitability**
Good in principle. **Automation is the blocker.**

**Lakehouse and ClickHouse suitability**
Fine. **Irrelevant given the licence decision.**

**Realistic analytical questions it answers**
Everything you would expect from a Q&A corpus; nothing you could not get from a cleaner source.

**Expected engineering challenges it forces**
Login-gated, click-through-gated download → **fails the brief's automation bar outright.** Post-state reconstruction. Deeply nested HTML bodies.

**Which target-job requirements it demonstrates**
Nothing the others don't; the SCD/audit-trail material is genuinely good but reached through a licence you don't want to defend.

**Relationships to other candidate datasets**
None usable. **If you want the "real change log" idea, get it honestly from A3 (publisher stream) or A8 (restatement feed).**

---

## Group B - Reference, dimension and geographic companions

The brief asks for the supporting cast: datasets that should be **looked up, not ingested as facts**. In each case the interesting engineering is the *join*, the *versioning*, and the decision **not** to denormalise them into the fact table.

---

### B1. OurAirports

**Dataset**
A community-maintained catalogue of 85,000+ airports with runways, navaids, frequencies, countries and top-level administrative regions.

**Source and URL**
- Data page (verified live, with current per-file byte sizes and last-modified dates): `https://ourairports.com/data/`
- Data dictionary: `https://ourairports.com/help/data-dictionary.html`
- **Automation:** `https://github.com/davidmegginson/ourairports-data` (GitHub API: **The Unlicense**); direct files at `https://davidmegginson.github.io/ourairports-data/*.csv`. Repo README verified: *"Open-data downloads for OurAirports, updated daily."*

**Licence - the cleanest in the report**
`https://ourairports.com/data/` states: *"All data is released to the Public Domain, and comes with no guarantee of accuracy or fitness for use."* The GitHub repo is **The Unlicense** (confirmed via GitHub API and via the site's JSON-LD context, which cites `https://unlicense.org/`). **Public domain / Unlicense: no NC, no SA, no attribution obligation, no downstream restrictions. Unambiguously permits any use including commercial.** Attribution is invited, not required.

**Size, format, file or table count - 6 CSVs, sizes and dates read from ourairports.com/data on 2026-09-27**

| File | Bytes | Rows (approx) |
|---|---|---|
| `airports.csv` | 12,727,797 | 85,000+ |
| `airport-comments.csv` | 4,680,827 | - |
| `runways.csv` | 3,964,978 | ~50,000 |
| `airport-frequencies.csv` | 1,299,761 | ~40,000 |
| `navaids.csv` | 1,524,946 | ~13,000 |
| `countries.csv` / `regions.csv` | small | ~250 / ~5,000 |

**Total ~24 MB**, UTF-8 CSV, **updated nightly**. CSV only (no Parquet), so this is a genuine CSV→lakehouse job, not a copy.

**Update frequency; live or snapshot**
**Daily, and the freshness caveat is itself the gift.** The repo README warns: *"OurAirports generates the files every day, but GitHub updates the date only when the contents have changed. As a result, files that change rarely, like countries.csv, may show a date weeks or months in the past."* **The dataset ships its own operational caveat: absence of a changed date does not mean absence of change.** A real incremental-ingest bug, documented by the publisher.

**Tables and their relationships**
From the official data dictionary: `runways.airport_ref → airports.id`; `airport-frequencies.airport_ref → airports.id`; `navaids.associated_airport → airports.id`; **`airports.iso_region → regions.code`**; `airports.iso_country → countries.code`; `regions.iso_country → countries.code`; `airport-comments.airport_ref → airports.id`. `airport-comments` is a **high-cardinality one-to-many** (4.7 MB of prose for 85k airports) - a genuine fan-out and a genuine "why is my row count exploding" bug.

**Primary keys, natural and business keys**
The data dictionary is explicit: *"The primary key for interoperability purposes with other datasets is **`ident`**, but the actual internal OurAirports primary key is `id`."* **A documented surrogate-PK vs business-PK distinction, from the publisher, in a real reference dataset - and a live trap:** joining on `ident` is *semantically* right for cross-dataset use but is *not* their star schema's key, so `airport_ref` (an integer) will not match `ident` (a string). **The best natural-key teaching moment in the reference group, and unlike Olist's, documented by the publisher.** Business keys present: `ident` (ICAO), `iata_code` (3-letter, sparse), `gps_code`, `local_code`.

**Timestamp semantics and timezone behaviour**
**None at all.** A pure reference table with no temporal columns - a **Type 1 dimension by construction**. If you need temporal geography, **B2** is where that lives. Say so explicitly: *"our airport dimension is Type 1, and here is why that is a limitation we accept and where we compensate"* beats pretending otherwise.

**Nested or semi-structured content**
`keywords` is a comma-separated synonym list in a scalar. Mild parsing exercise, and a real one - it is the join key to a would-be synonym table.

**Expected data-quality problems actually present**
The publisher states plainly: *"no guarantee of accuracy or fitness for use."* The data shows it:
- **`iata_code` is sparse** (scheduled-service airports only) - an IATA-keyed join drops most rows, silently.
- **Many rows are not real airports** - heliports, seaplane bases, closed fields, private strips, balloon pads. `type` discriminates them, and **not filtering on `type` and `scheduled_service` makes your airport count meaningless.** The most common real mistake with this dataset, and entirely self-inflicted.
- `iso_country` / `iso_region` can be null or malformed for non-ISO entities.
- `elevation_ft` is signed, so some airports sit below sea level - a negative-elevation filter bug.
- Duplicate-ish facilities: one physical airport can appear under multiple `ident`s.
- **No PK on `countries`/`regions` other than the code itself; `regions.code` is ISO-3166-2 and is unique only within a country, so the composite (`iso_country`, `code`) is the key.** A real referential-integrity trap in a dataset everyone treats as trivially clean.

**CDC suitability, and whether change events are real or synthesised**
**T2, weak.** Daily regeneration means a real diff stream exists, but a nightly full-file diff on 24 MB is trivial. `airport-comments` and `navaids` do change in practice (airport data is corrected; nav aids are retired). **Do not overclaim: a scheduled-refresh pattern, not a CDC demo.** It belongs in the batch/MDM leg, demonstrating "Type 1 dimension refresh with change detection and a MERGE" - legitimate and useful.

**Batch suitability**
Excellent. 24 MB, daily, incremental-by-hash is a textbook bronze→silver dimension load, and Dagster asset materialisation with a freshness policy is exactly the right home for it.

**Lakehouse and ClickHouse serving suitability**
- **Iceberg:** MERGE on `id` (or `ident`, if you deliberately choose the business key and document it) daily. Retention is trivially "keep current + a short change log."
- **ClickHouse:** **`airports` is a textbook `Dictionary` or lookup source.** *"Should this be a dimension table, a dictionary, or a replicated table?"* is a real serving-layer design question, and ClickHouse's answer (a `Dictionary` with `LAYOUT(FLAT())`/`HASHED()`, refreshed from S3) is a genuinely good JD-relevant talking point. Low cardinality, never aggregated → **explicitly a lookup, not a fact.**

**Realistic analytical questions it answers**
"Which airports lack an IATA code in their country?" "Which airports have more than one runway over 3,000 m?" "Map revenue by nearest airport using haversine distance." "Which airports are in the same `iso_region` as my top-selling market?"

**Expected engineering challenges it forces**
CSV ingestion with mixed quoting and a comma-in-`keywords` column; **a surrogate-vs-business key decision actually documented as a choice by the publisher**; `LEFT` vs `INNER JOIN` and the silent row loss when `iata_code` is null; the `regions.code` composite-key trap; daily-incremental change detection that **does not trust file mtime, because the publisher tells you not to**; and a documented decision that this is Type 1 while B2 is Type 2.

**Which target-job requirements it demonstrates**
"ClickHouse serving" ✅✅ (dictionary-vs-table decision). "Data governance: catalog organization, access control" ✅. "physical table layout… retention" ✅. "Dagster" ✅. "Automated data-quality checks" ✅. **Not** Debezium/Flink - say so.

**Relationships to other candidate datasets**
- **Pairs with B3 (GeoNames) as a second, independent geographic source:** OurAirports for rich point features, GeoNames for a 4-level hierarchy and a global gazetteer. They overlap (`ident` vs `geonameid`, no shared key) so the honest framing is **"two independent references, cross-validated"**, not "joinable."
- Weakly with A3 (UK airports only) - do not force it.
- Would pay off with a flight/route dataset, which is outside this angle's scope.

---

### B2. UK Postcode Directory (ONSPD) - ONS Geography

**Dataset**
The definitive UK postcode-to-geography directory: ~2.7 million unit postcodes related to statutory, electoral, health and census geographies, with **live and terminated** postcodes, grid references, and a 137-field record specification.

**Source and URL**
- Product page: `https://www.ons.gov.uk/methodology/geography/geographicalproducts/postcodeproducts`
- **User guide (contains the record specification at Annex A - I downloaded and parsed it):** `https://www.ons.gov.uk/file?uri=/aboutus/transparencyandgovernance/freedomofinformationfoi/ukpostcodesandcorrespondinglocalauthorityfebruary2025/onspduserguidefeb2025.pdf`
- Catalogue (verified live, with file sizes): `https://ckan.publishing.service.gov.uk/dataset/ons-postcode-directory-may-2026`
- **Automation:** the Open Geography Portal/ArcGIS hub hosts GeoJSON, KML, Shapefile, GeoPackage, SQLite GDB, XLSX, CSV and a **GeoService REST API** - scriptable.

**Licence - GOOD, WITH ONE REAL EXCEPTION**
From the ONSPD User Guide §3 "Licensing Requirements": *"Our postcode products (derived from Code-Point® Open) are subject to the **Open Government Licence**."* Attribution that must be displayed whenever the data is used:
- *"Contains OS data © Crown copyright and database right [year]"*
- *"Contains Royal Mail data © Royal Mail copyright and database right [year]"*
- *"Source: Office for National Statistics licensed under the Open Government Licence v.3.0"*
- **And the exception:** *"If you also use the Northern Ireland data (postcodes starting with 'BT'), you need a **separate licence for commercial use direct from Land and Property Services**. We only issue a Northern Ireland End User Licence (**for internal business use only**) with the data."*

**Assessment:** OGL v3.0 permits our use (including commercial) for England, Wales, Scotland, the Channel Islands and the Isle of Man, with attribution. **The Northern Ireland `BT` postcodes are a genuine restriction.** For a portfolio this is a non-issue *if you either (a) exclude `BT` postcodes, or (b) keep them and state the restriction.* **Recommendation: exclude `BT` postcodes from published silver/gold tables and document that you did, with the reason.** That is a better answer than shipping a licence-restricted subset silently. Note also that the data.gov.uk catalogue records the licence as *"No Licence Provided"* - a catalogue-metadata gap. **The authoritative licence is in the User Guide, not the catalogue.**

**Size, format, file or table count**
From the live catalogue entries: the **multi-CSV zip is 235 MB**; the **hosted table is 2.31 GB** (which includes the spatial formats). Formats: **TXT (fixed record length, no text qualifiers)**, CSV (variable length, quoted), plus GeoJSON/KML/Shapefile/GeoPackage/SQLite GDB/XLSX and a REST API. **~2.7M live postcodes plus terminated ones. Table count: 1 very wide record, 137 fields** (the User Guide record specification lists ~137 numbered fields). Effectively a **degenerate star: one fact-ish entity and ~20+ conformed geography dimensions at wildly different grains.** A multi-CSV variant split per postcode area exists purely so Excel can open it - the User Guide says the single CSV is *"incompatible with certain standard spreadsheet packages."*

**Update frequency; live or snapshot - the standout feature**
**Quarterly, and the freshness is layered:**
- Issued **quarterly** (February, May, August, November) per the product page.
- Postcode data is **received monthly from Royal Mail**; the ONSPD is current *"to the 3rd Friday of the previous month"* and *"includes both live and terminated postcodes."*
- Administrative areas are as of *"the preceding May"*; health areas are *"the latest known."*
- **So within one release you have three different as-of dates for different column groups.** A real, publisher-documented, multi-temporal-snapshot dimension - precisely what breaks naive as-of joins. **The best genuine bitemporal-flavoured reference data under a clean licence, and it beats anything you would synthesise.**

**Tables and their relationships**
One very wide postcode record plus **lookup files** linking GSS 9-character codes to statutory area names. All relationships are *many postcodes → one area*: postcode → LSOA → MSOA → local authority district → unitary/upper-tier → region → ITL/NUTS → parliamentary constituency → European electoral region → health board/authority/ICB/PCN → country. The User Guide notes `NUTS` was **renamed to `ITL` from May 2021** with updated content - a documented schema change in a live dataset.

**Primary keys, natural and business keys - the best in the report**
- `PCD` (7-character postcode) is the business key, with `PCD2` (8-char, 5th char always blank) and `PCDS` (variable-length) as convenience variants of the *same* natural key. **Three representations of one business key in one record** - a superb, real, very common normalisation problem.
- **And there are explicit temporal fields, which I verified directly in the record specification:**
  - **`DOINTR`** - *"Date of introduction, YYYYMM. The most recent occurrence of the postcode's date of introduction."*
  - **`DOTERM`** - *"Date of termination, YYYYMM. If present, the most recent occurrence of the postcode's date of termination, **otherwise: null = 'live' postcode**."*
  A **published, first-class SCD2 temporal dimension with a null-as-live semantic.** No synthesiser would produce it; a government postal registry does, because postcode reuse is a real operational problem.
- The record spec also states the directory retains *"all terminated ('closed') postcodes that have not been subsequently re-used by Royal Mail"* - so a postcode can be **terminated and later re-introduced**, with `DOINTR`/`DOTERM` recording *"the most recent occurrence"* of each. **A genuine versioned-entity-with-supersession problem in a reference dimension, from a primary source.**

**Timestamp semantics and timezone behaviour**
`DOINTR`/`DOTERM` are **`YYYYMM` - month granularity, not dates.** Consequences you must handle and can demonstrate: (a) you cannot order events within a month, so as-of joins are only month-precise; (b) month-granularity keys partition poorly and make poor Iceberg partition expressions without a derived surrogate; (c) comparing `YYYYMM` strings works lexicographically *only* for four-digit years and breaks on null. **Calendar months, no timezone component - there is no tz story here at all, so do not claim one.** Grid references are in `BritishNationalGrid` (EPSG:27700) and Northern Ireland uses `Ireland 1965 / Irish Grid` (EPSG:29902) - a genuine **multi-CRS** problem, an often-omitted geographic-engineering concern.

**Nested or semi-structured content**
The TXT variant is a **fixed-record-length file with no text qualifiers** - positional parsing with no CSV quoting at all, an underrated exercise. No nested structures.

**Expected data-quality problems actually present - and they are documented, which is even better**
The User Guide has an explicit **Data Quality** section, so the publisher's caveats *are* the demo:
- *"No warranty is given by [ONS] as to the accuracy or completeness of the SPD - omissions and inaccuracies."*
- Inaccuracies arise from **"straddling"** (a postcode split across two geographies) and **"wrong assignments (imputation)"** - both real, both named.
- **Explicitly: "the use of the ONSPD to allocate individual addresses to geographies might be imprecise because of the effects of straddling and wrong assignments."** *The authoritative source tells you its own joins are lossy.* A wonderful, honest thing to build a DQ rule around.
- Fields are **blank for the Channel Islands and Isle of Man** and for postcodes without a grid reference - pervasive NULLs with a documented reason.
- **"Frozen" geographies:** some health-area codes remain a *'frozen' geography*; some remain *"as they were in 2001"*. **Different column groups are frozen at different historical vintages**, so joining them naively mixes 2001 and 2021 boundaries.
- **Boundary splits:** the guide documents a case of *"Postcode Assigned to both English and Scottish 2001 Census OAs"* and ~0.54M postcodes in England and Wales that are *"new postcodes since"* a given date - genuine non-2001 geography.
- **`PCD`/`PCD2`/`PCDS` inconsistencies:** 2nd–4th characters may be blank in the outward code; the 5th is always blank in PCD2. Blank-position normalisation is mandatory.
- Spreadsheet-breaking file size - a reminder that "just open it in Excel" is a production strategy failure.
- No warranty + imputation = **you must decide and document how you treat a postcode that straddles two LSOAs.** Max population share, or fan out with weights? That decision belongs in the README.

**CDC suitability, and whether change events are real or synthesised**
**T2 - the strongest T2 in the reference group.** Quarter-over-quarter diffing of the ONSPD produces a **real, dated, attributable change feed with real inserts, real updates and real terminations**, because the publisher explicitly retains terminated postcodes and explicitly records introduction/termination months. **The change stream is real, derived from real data, and documented as such - you are not inventing anything, you are differencing a government registry across its own published quarterly releases.**
- **Honest caveats, all of which you must state:** (a) granularity is monthly, not transactional; (b) a difference across releases does not tell you *which* release introduced the change without scanning all intermediate releases, so **a full quarter-by-quarter replay is required for a correct audit trail** - a real cost you can demonstrate you paid; (c) the three as-of dates within one release mean a naive three-way diff will attribute a change to the wrong cause; (d) no transaction log and no before-image beyond the previous file.
- **Having both a real T1 binlog stream (A1) and this real T2 file-diff stream is the best argument for this dataset in the whole report.**

**Batch suitability**
Excellent. 235 MB quarterly, 2.7M rows, 137 columns, a well-defined delta. Bronze-append + silver-MERGE (Type 2) + gold-snapshot on a quarterly clock is a clean, believable Dagster asset graph with real idempotency questions.

**Lakehouse and ClickHouse serving suitability**
- **Iceberg: excellent, and the SCD2 use is textbook.** `silver.onspd_postcode` as a Type 2 table keyed on `PCD` with validity from `DOINTR` to `coalesce(DOTERM, '9999-12')` is exactly right, and the MERGE-heavy, delete-free, update-heavy write profile is a **completely different Iceberg workload from A1's** - which is good, because you exercise both.
- **Physical layout:** partitioning on a derived `date_part_year(DOTERM)` or on the `PCD` outward-code prefix is a genuine, defensible decision with measurable consequences. **137 columns makes column pruning a real, demonstrable optimisation** - excellent material for *"design physical table layout to balance write throughput, query performance, and storage cost."*
- **ClickHouse: good.** Postal geography is naturally a **lookup** (a postcode is never a fact). The `ReplacingMergeTree`/dictionary decision applies again, and the **two-CRS problem** means you must decide whether to store BNG easting/northing and Irish Grid separately or reproject - a concrete, checkable serving-layer decision.

**Realistic analytical questions it answers**
"How many of our registered offices are in England versus Scotland, using the correct 2021 boundary vintage?" "Which customer postcodes terminated in the last two quarters - churn signal or data artefact?" "What is our exposure by local authority district and NHS ICB?" "Are we missing customers in areas that only exist in the *previous* ONSPD release, and what do we owe them?" "How many of our addresses are affected by a postcode straddling two LSOAs, and what is our exposure under each allocation policy?" That last one is a data-governance question with a real business answer.

**Expected engineering challenges it forces**
Fixed-width vs CSV parsing and blank-position normalisation; a **Type 2 dimension built from a real, published, month-granularity temporal pair**, with `DOINTR`/`DOTERM` monotonicity and re-introduction handling; a **three-as-of-date** temporal alignment problem; a **multi-CRS** decision; 137-column pruning; straddling/fan-out policy; `PCD`/`PCD2`/`PCDS` key normalisation; an OGL attribution block in the gold models; correct handling of a licence-restricted subset (`BT`).

**Which target-job requirements it demonstrates**
"Data models and physical table layout" ✅✅. "Data governance: catalog organization, **data lineage**, retention/compliance" ✅✅ (versioned releases + licence-restricted subset + attribution is a complete governance story). "Automated data-quality checks" ✅✅ (the publisher's caveats become your test suite). "ClickHouse serving" ✅. "Dagster" ✅. "Apache Polaris" ✅. "Apache Iceberg" ✅✅. "Spark batch" ✅✅. **Flink** ⚠️ (you *could* implement the quarterly diff as a Flink job over the two Parquet releases - worth doing, and honest, because it is a batch-over-two-snapshots job, not a true stream). **Debezium** ❌ - do not pretend.

**Relationships to other candidate datasets**
- **Its best partner is A3 (Companies House).** `company.registered_office_address.postcode → ONSPD.PCD → all the geographies and the grid reference`, plus the BNG easting/northing directly. **Same country, same government, same licence family, and A3 supplies a real change stream while B2 supplies a real changing dimension.** Together they are the most coherent cross-candidate story in this report, and A3's registered-office postcodes make the geography *matter* rather than decorate.
- Second-best: **B3 (GeoNames)**, which has its own GB postal file and a `GB_full.csv` variant, as an independent cross-check. Different licence family (CC BY vs OGL), genuinely different provenance (crowd-sourced vs statutory).

---

### B3. GeoNames

**Dataset**
A global geographical database: 11M+ unique features, 13M alternate names, organised into 9 feature classes and 645 feature codes, with a 4-level administrative hierarchy and a separate postal-code file covering ~100 countries.

**Source and URL**
- `https://download.geonames.org/export/` (verified live)
- `https://download.geonames.org/export/dump/readme.txt`
- `https://download.geonames.org/export/zip/readme.txt`
- **Verified live file sizes/timestamps:** `allCountries.zip` ≈ 402 MB, last modified 2026-09-24 03:53 UTC; `export/dump/GB.zip` 3,639,090 bytes, modified 2026-09-27 02:41 UTC; `export/zip/GB.zip` (postal) 330,960 bytes, modified 2026-09-27 02:54 UTC. Also `cities500.zip`, `cities1000.zip`, `cities5000.zip`, `cities15000.zip`, `hierarchy.zip`, `countryInfo.txt`, `featureCodes_en.txt`, `admin1CodesASCII.txt`, `admin2Codes.txt`.

**Licence - CLEAN, with named third-party attributions**
`https://download.geonames.org/export/` states, verified: *"This work is licensed under a **Creative Commons Attribution 4.0 License**"*, and in the same terms list: *"**commercial usage is allowed**"*, *"You should give credit to GeoNames when using data or web services with a link or another reference to GeoNames"*, and *"The Data is provided 'as is' without warranty or any representation of accuracy, timeliness or completeness."* The **postal** `readme.txt` carries the same CC BY statement.
- **Third-party attributions you must honour** (from `https://sws.geonames.org/about.html`): *"Ordnance Survey OpenData gazetteer: Contains Ordnance Survey data Crown copyright and database right 2010"*; *"Contains public sector information licensed under the Open Government Licence v1.0"*; *"postal codes: Contains Royal Mail data Royal Mail copyright and database right 2010"*; plus NGA/US Board on Geographic Names, USGS GNIS, GeoNames Austria.
- **Assessment:** CC BY 4.0 with commercial use explicitly allowed. **Permits our use, including commercial, with attribution.** The embedded OS / Royal Mail / USGS sub-licences are **naming-and-attribution obligations, not use restrictions.** **Recommendation: scope your geography to a country whose upstream sub-licences you can name cleanly, and print the full attribution block.** If you take the global `allCountries.zip`, inherit and print the OS/NGA/USGS attributions.

**Size, format, file or table count**
**~402 MB compressed for `allCountries.zip`** (11M+ features), plus `alternateNames.zip` ~193 MB and an `alternateNamesModified/...zip` variant, plus per-country subsets (`GB.zip` 3.6 MB - a very reasonable scoped download) and ~100 per-country postal zips. Format: **tab-delimited UTF-8 plain text, no header, fixed column order** - positional, documented in `readme.txt` with per-column types. Effective tables: `geoname`, `alternateNames`, `countryInfo`, `admin1Codes`, `admin2Codes`, `hierarchy`, `featureCodes`, `userTags`, plus a separate `postal` table. **8–9 tables.**

**Update frequency; live or snapshot**
**Daily.** The dump server timestamps files daily (my own `Last-Modified` headers show 2026-09-24/27). *"A daily GeoNames database dump can be downloaded in the form of a large worldwide text file (allCountries.zip)."* So a daily snapshot with a real diff - but again, **T2 weak: a nightly gazetteer diff is a change-detection exercise, not a CDC demo.**

**Tables and their relationships**
`geoname` (PK `geonameid`) → self-referential `hierarchy(parentId, childId, type)`, plus `admin1`/`admin2`/`admin3`/`admin4` code columns on the row itself. `geoname ↔ alternateNames` is a **1:N with enormous fan-out** (13M alternate names over 11M features, concentrated on cities). `countryInfo` (`ISO`, `ISO3`, `ISO-Numeric`, `fips`, `country`, `capital`, `area`, `population`, `continent`, `tld`, `CurrencyCode`, `CurrencyName`, `Phone`, `Postal Code Format`, `Postal Code Regex`, `Languages`, `geonameid`, `neighbours`, `EquivalentFipsCode`) is a genuine small reference table. `featureCodes` is the **taxonomy**: 9 classes, 645 codes.

**Primary keys, natural and business keys**
`geonameid` is a stable integer PK. Business keys: `(country code, admin1 code, admin2 code, name)`; the postal readme defines the natural key as (country code, postal code, admin name1, admin code1, …). **The `adminX code` fields are documented as FIPS codes that are "subject to change to ISO code"** with a stated exception list (ISO for US/CH/BE/ME; **UK and Greece have an extra level between country and FIPS code**). **A documented, real key-semantics change inside one dataset** - a killer detail for a dimension-modelling conversation and a real bug source. `fips` in `countryInfo` is deprecated in favour of `iso`/`geonameid`, with `EquivalentFipsCode` provided for migration. Another documented deprecation.

**Timestamp semantics and timezone behaviour**
**None.** A pure present-tense spatial reference with no temporal columns. **Type 1 by construction, like B1. Do not claim otherwise.** (Precisely why B2 is valuable *alongside* it.)

**Nested or semi-structured content**
None. Tab-delimited, flat, documented. The nearest thing: `alternateNames.isolanguage` encodes type in the language tag - `post` (postal codes), **`iata`, `icao`**, `faac` (airport codes), `fr_1793`, `und`, `link`, `wkdt` (Wikidata ID). **`alternateNames.isolanguage IN ('iata','icao')` is a ready-made cross-reference to OurAirports' `iata_code`/`ident`** - a genuine, documented join key between two independent reference datasets. A nice find, worth using.

**Expected data-quality problems actually present**
- The publisher disclaims all accuracy/timeliness/completeness warranties, and the data shows it: duplicate and near-duplicate features, coordinates at longitude ±180 / latitude ±90 from rounding, populated places with population 0, `admin4` populated for almost nobody, and **`neighbours` in `countryInfo` hard-coded as a denormalised string** (adjacency is not a relation - a normalisation opportunity).
- **Postal codes: "for CA, NL and UK only the first part of the codes"** in `allCountries.zip`; full codes only in `CA_full.csv.zip` / `GB_full.csv.zip` / `NL_full.csv.zip`. **Using `allCountries.zip` for UK postal data silently truncates your postal keys.** Specific, documented, very easy to hit.
- Postal coverage is "nearly 100 countries" and is added *only when the national postal service publishes under a compatible licence* - **uneven by design**, so a global postal model has holes you must measure.
- The `admin1 code` FIPS→ISO migration and the UK/Greece extra-level exception mean **country-specific join logic is unavoidable.** Not a defect - a real-world referential-integrity wart a naive global star schema gets wrong.
- Duplicate feature rows and features with identical coordinates at different `geonameid`s (a common pattern: a city and its airport, or a city and a nearby hamlet).

**CDC suitability, and whether change events are real or synthesised**
**T2 weak**, same as B1. One nice angle: GeoNames is **crowd-sourced and wiki-editable** (*"edit names (wiki) for registered users"*), so changes are genuine human corrections with a real rationale. A nice narrative, **not** a CDC demo. Keep this dimension in the batch leg.

**Batch suitability**
Excellent, and 402 MB is a real download. **Per-country scoping (`GB.zip` = 3.6 MB) is the smart move:** it makes the pipeline fast *and* bounds the upstream attribution surface. Positional tab parsing is a genuine (if easy) exercise. `hierarchy.zip` is a self-referential adjacency list - a recursive-CTE / closure-table modelling exercise, a real and portable skill.

**Lakehouse and ClickHouse serving suitability**
- **Iceberg:** MERGE on `geonameid`, daily. Strong candidate for **`hierarchy.zip` as adjacency list → closure table** - a legitimately interesting silver-layer transformation.
- **ClickHouse:** `geoname` is 11M rows of low-cardinality, never-aggregated reference data - the same **dictionary-vs-table** decision as B1, at larger scale, which makes the comparison worthwhile. `featureCodes` is a 645-row hierarchy that should be a **tiny replicated table or dictionary**, not a fact. **Point lookup by `(country_code, admin1_code, name)` is a dictionary key; ClickHouse's `hashed` dictionary with a composite key is the right answer and a good one to justify.**

**Realistic analytical questions it answers**
Every "where" question: "how many customers are in administrative areas we have never seen revenue from?" "which markets sit in a time zone we have not modelled?" "reverse-geocode our warehouse locations to a consistent admin2 level", "join our `iata_code` list to canonical airport records". The 4-level hierarchy lets you roll a metric up to continent → country → admin1 → admin2 and check the roll-up is additive - **it is not additive for admin3/admin4, which is itself a lesson.**

**Expected engineering challenges it forces**
Positional, headerless, unquoted tab parsing with documented column order; a documented FIPS→ISO key migration with a per-country exception list; the postal truncation trap; self-referential hierarchy → closure table; a big fan-out join to `alternateNames` that must be pre-aggregated (**the classic "my row count exploded" moment, and it is real here**); **a documented decision to scope by country to bound both download size and upstream attribution obligations**; and the discipline of treating an "as is, no warranty" dataset with a real DQ suite rather than trusting it.

**Which target-job requirements it demonstrates**
"Expert SQL, dimensional/data modeling" ✅ (closure table, hierarchy, composite keys, documentation-driven join logic). "ClickHouse serving" ✅✅ (dictionary design at meaningful scale). "Data governance: catalog organization" ✅. "Automated data-quality checks" ✅. "Apache Spark" ✅ (400 MB tab files, a fan-out join, a closure-table build). "Dagster" ✅. "Apache Iceberg" ✅. "Data lineage" ✅ (documented column order and code-migration provenance). **Debezium/Flink** ❌.

**Relationships to other candidate datasets**
- **Pairs with B1 (OurAirports) on `alternatenames.isolanguage IN ('iata','icao')` → `airports.iata_code` / `airports.ident`.** A real, documented, cross-dataset join key between two independently-licensed public-domain/CC-BY sources. **The single most defensible cross-reference join in the reference group.**
- **Pairs with B2 (ONSPD)** as an independent check on UK geography - different licence family (CC BY vs OGL), genuinely different provenance, and B2/B3's `GB_full.csv` gives the full postal codes B3 truncates in `allCountries.zip`. A **three-way geographic reconciliation** (GeoNames admin1 vs OurAirports iso_region vs ONSPD regions) is a real data-governance exercise with a real deliverable: *they will disagree, and finding out where and why is the deliverable.*
- Can attach to **A4 (Olist)** to replace its dirty `olist_geolocation` (26.2% duplicates, 42 points outside Brazil). **Strong recommendation: do exactly that** - but be honest that it is an *enrichment*, not a *repair*: you cannot recover lost Brazilian zip prefixes truncated on read, so the leading-zero DQ check must run **before** any enrichment attempt.

---

### B4. HUD–USPS ZIP Code Crosswalk Files

**Dataset**
Quarterly allocation files relating 5-digit USPS ZIP codes to Census geographies (tract, county, county subdivision, CBSA, CBSA division, congressional district) in both directions, each row carrying residential/business/other/total address ratios.

**Source and URL**
`https://www.huduser.gov/portal/datasets/usps_crosswalk.html` (verified live; returned HTTP 202 on HEAD, i.e. live and working). Twelve file types. Data dictionary: `https://www.huduser.gov/datasets/usps/usps_data_dictionary.pdf` (verified live). **API:** `https://www.huduser.gov/portal/dataset/uspszip-api.html` and `https://www.huduser.gov/hudapi/public/usps` (verified, with a documented request/response schema including `res_ratio`, `bus_ratio`, `oth_ratio`, `tot_ratio` and a `quarter` parameter).

**Licence - CLEAN, with an attribution request**
The files come from HUD's Office of Policy Development and Research, derived from **USPS vacancy data** - a **US federal government work → public domain**. A verified third-party integration doc states: *"The crosswalk files are produced by a U.S. federal agency and are in the public domain. HUD requests attribution to the HUD–USPS ZIP Code Crosswalk Files."* **Public domain: permits any use including commercial, no restrictions.** Attribution is requested, not required - grant it.
- ⚠️ **Upstream nuance worth knowing and stating:** the data dictionary says HUD receives ZIP+4 extracts from USPS *"Under the license agreement with USPS, HUD must aggregate these data at the Census Tract level before distributing them to the public."* So you are downstream of a public-domain publication of aggregated data. Fine for a portfolio; you could not get ZIP+4 detail from here.

**Size, format, file or table count**
**12 file types** (ZIP→tract/county/subdivision/CBSA/CBSA-division/congressional-district, plus the six inverses). Format: **`.xls`/`.xlsx`** in the bulk download (the ICPSR record lists `File Layout: .xls`), with CSV/JSON via the API. Row counts: ~41,000 US ZIP codes in ZIP→county; ZIP→tract is much larger (~150,000–180,000 rows) because a ZIP can straddle many tracts. **Tens of MB - a pure reference dataset.**

**Update frequency; live or snapshot - and the cadence has a real reason**
**Quarterly, "snapshot in time at the close of a quarter."** Published *"by the end of the month following the quarter"* (aim: Q4 by end of January, Q1 by end of April). The *reason* matters: the files are *"derived from data in the quarterly USPS Vacancy Data… updated quarterly, making them highly responsive to changes in ZIP code configurations"*, and HUD's own FAQ says **"As addresses are created or removed, this changes the ratios in the associated geographies."** **The ratios are themselves a slowly-changing measure, not a static mapping** - a real SCD2 *measure*, not just attributes. Very few reference datasets give you that.

**Tables and their relationships**
ZIP ↔ geography, **many-to-many, with weights** - the highest-cardinality many-to-many in the report. From the FAQ: *"Each record in the Crosswalk File represents a geography that intersects with a particular ZIP Code. For example, if you are reviewing a ZIP to County file, if a ZIP Code appears twice then it intersects with two counties."* Published examples: ZIP 03870 splits across tracts `33015066000` (0.42% residential) and `33015071000` (99.58%); tract `01001020200` splits across ZIPs `36008` (2.72%) and `36067` (97.28%). **The relationship is explicitly not invertible** - HUD states the ZIP→Tract file cannot be used to go Tract→ZIP; you must use the Tract→ZIP file.

**Primary keys, natural and business keys**
`ZIP` (5-char) is the business key. Composite natural key per file: `(ZIP, TRACT|COUNTY|CBSA|…)`. Geography side: 11-digit GEOID (state FIPS + county FIPS + tract), 5-digit county FIPS, 5-digit CBSA, 4-digit congressional district. **The API's own docs warn that GEOID is `51059461700` (11 digits) and county GEOID is `51600` (5 digits)** - identifier widths vary by entity, and a naive `INT` cast loses leading zeros. **Another leading-zero trap, same family as Olist's zips and SEC's `cik`. Leading zeros are the recurring hazard of this entire angle, and you should say so.**

**Timestamp semantics and timezone behaviour**
`year` + `quarter` in the API response; no timestamps, no timezone. **The vacancy-age fields are the real temporal payload:** `AVG_VAC` (average days vacant), `VAC_3`, `VAC_3TO6`, `VAC_6TO12`, `VAC_12TO24`, `VAC_24TO36`, `VAC_36` - all in days, **all ageing every quarter**. And the genuinely valuable prior-state fields: **`PQV_IS` ("Previous quarter vacant currently in service")**, `PQV_NOSTAT`, `PQNS_IS`, `PQNS_NOSTAT`. **Literal previous-period values carried in the current file - an embedded, real, quarter-over-quarter comparison, handed to you by the publisher.** A rare gift and a great way to build a "did the crosswalk improve or degrade this quarter" model.

**Nested or semi-structured content**
None structurally. But the four ratio columns are a **weight vector** - semi-structured in spirit, awkward in a star schema. A single (ZIP → county) row is **not a fact about a county; it is a fraction of a ZIP attributed to a county.** Getting this into a dimensional model requires an explicit, documented **allocation decision** rather than a key.

**Expected data-quality problems actually present - outstanding, and mostly documented by HUD itself**
- **Ratios do not sum to 1.00:** *"the sum of each ratio column for each distinct ZIP code may not always equal 1.00 (or 100%) due to rounding issues."* **The publisher tells you your allocation weights don't reconcile.** A perfect DQ rule with a documented tolerance.
- **<1% of active ZIPs are missing:** *"there may be some 5-digit USPS ZIP codes that will not be included… Less than 1% of the total number of active 5-digit ZIP codes in the country are excluded."* **Known, quantified referential gaps in your reference table.** A foreign-key coverage check is mandatory.
- **PO-Box-only ZIPs absent by design:** *"ZIP codes that only serve Postal Boxes (PO Boxes) will not appear in the files."* A business customer list full of PO Boxes will lose rows on an inner join. Real, quantified, documented.
- **Geocoding retries change the data:** the data dictionary says ~1% of ZIP+4 records don't geocode, and *"With each new quarterly extract, HUD makes an attempt to geocode the non-geocoded ZIP+4 records from the previous extract… This accounts for the variance in the number of records in the aggregate tract-level files from quarter to quarter. Users should be aware of this when measuring change between quarters."* **A direct warning that quarter-over-quarter row-count change is confounded by geocoding improvements, not only real change.** Any "how many ZIPs changed" metric is therefore confounded. Enormous, quotable honesty.
- **ZIPs are not geographies:** *"ZIP Codes do not align with political or administrative boundaries. ZIP Codes frequently cross county, city, and town jurisdictions. ZIP Codes may also potentially cross state borders."* The dataset's own documentation tells you not to treat it as one.
- **No names:** *"the underlying data used to create the Crosswalk Files does not contain USPS Recommended City Names."*
- **Geography vintage changes:** 2012Q1–2022Q4 use **2010 Census** geographies; 2023Q1 onward use **2020 Census** geographies. **A 2022Q4→2023Q1 diff is not a real change - it is a schema/version change.** A genuine, dated, documented SCD *schema* break, and a classic production incident you can write up.
- **Non-invertibility** is the subtlest and most damaging: a wrong-direction join produces plausible-looking wrong numbers.

**CDC suitability, and whether change events are real or synthesised**
**T2, and specifically a *measure*-level change stream, which is rarer than a row-level one.** Real quarterly changes: new ZIPs, retired ZIPs, re-geocoded ZIPs, and **changed ratio values** with quarter stamps. Real, attributable, with the confounders documented.
- **Honest caveats:** (a) quarterly, not transactional; (b) no before-image beyond the prior file; (c) the 2010→2020 Census vintage break makes one specific diff uninterpretable, and you must handle it as a **schema migration rather than data change** - that is *the* engineering content of this dataset; (d) row-count variance is confounded by geocoding retries, so change metrics must be normalised. **Do not claim binlog CDC.**

**Batch suitability**
Excellent. Small, quarterly, well-defined delta, with a genuine version break to handle. A Dagster asset with a version-aware model is a clean, honest design.

**Lakehouse and ClickHouse serving suitability**
- **Iceberg: Type 2 on `(ZIP, GEOID)` with the ratio columns as a Type 2 *measure*** - a MERGE-heavy, delete-free, update-heavy table. **Exactly the Iceberg v2 upsert profile, and a completely different profile from A1's.** That contrast is valuable. Partition by `year*10 + quarter` (a small, finite partition space - a real decision, and it makes Iceberg time-travel genuinely useful).
- **ClickHouse: excellent.** "Revenue by county" with ZIP-level allocation is a textbook **`SummingMergeTree` with weighted columns** or a weighted dimension `JOIN` - and ClickHouse's answer to "how do I attribute an event to N geographies with weights" is a real, teachable design decision. `LowCardinality` on `county`; `ReplacingMergeTree` on the crosswalk keyed by `(ZIP, GEOID, version)`.

**Realistic analytical questions it answers**
"How much of our US revenue is in each county, given that 40% of our customers have a ZIP that straddles two counties?" "Which counties gained residential addresses quarter-over-quarter, and is that real growth or a HUD geocoding retry?" "What is our exposure in counties that changed Census vintage, and is the change comparable at all?" "Which ZIPs are predominantly PO-Box-only and therefore invisible in this file?" Every one has a real, surprising answer.

**Expected engineering challenges it forces**
A weighted many-to-many allocation model that reconciles to 100% (or documents that it can't, to a stated tolerance); a **geography-vintage schema migration**; reference-coverage monitoring with a known <1% gap; a documented policy for the non-invertible crosswalk; `.xls`/`.xlsx` ingestion; leading-zero-safe identifiers across three width conventions; a **confound-aware change-detection metric**. Also: encoding/line-ending handling for federal-published files - unglamorous and always real.

**Which target-job requirements it demonstrates**
"Data models and physical table layout" ✅✅. "Automated data-quality checks" ✅✅ (every HUD-documented caveat becomes a test). "Data governance: catalog organization, **lineage**, retention" ✅✅ (the vintage break is a lineage story). "ClickHouse serving" ✅✅ (weighted allocation, `SummingMergeTree`, dimension `JOIN`). "Apache Iceberg" ✅✅ (Type 2 measures, time-travel, compaction). "Dagster" ✅. "Spark" ✅. **Flink** ⚠️ (quarterly diff in Flink, honestly labelled as batch-over-snapshots). **Debezium** ❌. **Multi-region/cross-account** ❌.

**Relationships to other candidate datasets**
- **The natural US counterpart to B2 (ONSPD)** - same problem, same solution shape (Type 2 dimension, weighted allocation, quarterly cadence), different country and licence family (public domain vs OGL). **Comparing the two is a genuinely strong portfolio move: you show you understand the pattern, not one country's file.** If you build only one, build B2 and mention B4 as the US analogue you deliberately scoped out.
- **Note the gap honestly:** neither attaches cleanly to a primary source in this list, because **no candidate primary source is US-ZIP-keyed.** If US geography matters you need a US primary source outside this angle's scope. **Do not manufacture a join to make it fit.**

---

### B5. data.gov.my (Malaysia's national open-data portal)

**Dataset**
Malaysia's national open-data portal: a catalogue with per-dataset APIs and Parquet outputs. Included because the target role is in **Cheras, Kuala Lumpur** - local relevance is a real asset in a portfolio sent to a Malaysian employer.

**Source and URL**
`https://data.gov.my/data-catalogue` (verified live; the page's embedded JSON exposes a `link_parquet` field per dataset, plus a `meta_license` field, and a `"link_parquet"` in each dataset record). API pattern `https://api.data.gov.my/...` returned 301 on my probe - follow redirects; the API is reachable but the path needs the current form.

**Licence - GOOD AT THE PORTAL LEVEL, BUT PER-DATASET**
Verified from the portal's own embedded metadata: *"This data is made open under the **Creative Commons Attribution 4.0 International License (CC BY 4.0)**."* CC BY 4.0 permits our use including commercial, with attribution. **Permits use.**
- **Flag: the portal default is not the dataset licence.** The page's own field list includes `meta_license` ("License") **per dataset**, and the portal's description fields distinguish datasets *"suitable for API access"* from those that are not, with an explicit note that for the rest *"please use the provided download link as shown in the above section."* **So you must read `meta_license` for each specific dataset you pick, not the portal's blanket CC BY 4.0.** A dataset with a different or missing `meta_license` is a stop sign. This is the same class of risk as Olist, and it is why "check the licence, don't inherit it" is the rule.

**Size, format, file or table count**
Per dataset. **Parquet is a first-class output** (`link_parquet`), which is genuinely useful - it means you can point a lakehouse job straight at Parquet rather than writing a CSV ingest for the reference layer. Row counts are modest (population and similar series are small), and one observed example is a regulatory list of approved pharmaceutical products by NPRA/MOH.

**Update frequency; live or snapshot**
Varies by dataset. Observed records carry a `"last_updated"`-style timestamp of the form `"2026-09-25 23:59"`, which suggests a **dated nightly batch** for some series rather than a true live API. **Verify per dataset** - and note the end-of-day `23:59` convention, which is itself a small data-quality observation about a publisher's truncation choice.

**Tables and their relationships**
Weak. Most data.gov.my datasets are **single flat tables** - a demographic series, a list of registered entities, a facility list. There is a handful of genuinely multi-table candidates (e.g. `population` by year/sex/age/state, `prescriptions` by drug/ingredient) but **none of them is a normalised relational model with real foreign keys.**

**Primary keys, natural and business keys**
Per dataset. Typical: a code column (e.g. `code`/`code_desc`) plus a year or date column. **No surrogate/natural key tension, no composite keys, no many-to-many.** This is its fundamental limitation.

**Timestamp semantics and timezone behaviour**
`YYYY-MM-DD HH:MM` strings, and Malaysian local time (MYT, UTC+08:00) with **no offset recorded** in the data. So: a naive timestamp in a single-offset country, no DST, no tz field. Adequate for a simple dimension, nothing more.

**Nested or semi-structured content**
None. Flat tables. Some datasets publish a companion data dictionary (`meta_definition`, `meta_source`, `meta_url`, `meta_data_type`) alongside the data - a governance nicety, not nesting.

**Expected data-quality problems actually present**
Not verified. My probe of the catalogue page surfaced dataset *descriptions* and field lists, not data profiles. I am **not** going to invent defect counts. Expect the ordinary: label-level changes between years, `code_desc` label drift, and demographic series that do not sum to published totals. **These must be measured, not assumed.**

**CDC suitability, and whether change events are real or synthesised**
**T2 at best, and probably T3.** Nightly batch refreshes of a flat table give a real diff, but a flat single-table refresh is the weakest possible change feed. There is no transactionality, no fan-out, no deletes.

**Batch suitability**
Fine for a small dimensional or contextual table. Not a workload.

**Lakehouse and ClickHouse serving suitability**
Reasonable as a **small lookup** - Malaysian state/division codes, drug/ingredient reference. Parquet output makes ingestion trivial. Nothing here justifies a fact table.

**Realistic analytical questions it answers**
Localisation only: "what are our Malaysian state-level reference labels and codes?" "How do we describe our footprint in Malaysian administrative terms?" That is a demo garnish, not an analytical workload.

**Expected engineering challenges it forces**
Very little beyond reading `meta_license` per dataset, following the API's redirect/path conventions, and documenting the MYT assumption. **Honestly: this dataset will not force any of the JD's engineering requirements. Include it as a localisation detail, and do not inflate its role.**

**Which target-job requirements it demonstrates**
"Stay current with the lakehouse ecosystem" ⚠️ (barely). "Collaborate with data analysts, product teams" ⚠️ (domain authenticity). **Nothing in the technical requirements.** Its value is narrative: *the portfolio is built by someone who knows the local data landscape.* That is a real, if small, differentiator for this specific job posting.

**Relationships to other candidate datasets**
- Could sit alongside **A8 (SEC EDGAR)** as a second public-domain-ish source, but shares no keys and no domain.
- **The real opportunity is a MY primary source**, not this reference. If you wanted a genuinely local OLTP story you would need a Malaysian transactional dataset - and the honest answer is that I did not find one that is relational, FK-rich, licence-clean and automatable. **That is a real finding, not a gap I am papering over.**

---

## Rejected candidates and risk register

Assessed and **rejected**, with the reason. Recorded so the reasoning is reusable and so a reviewer can see what was considered.

| Candidate | Verdict | Reason |
|---|---|---|
| **Stack Exchange data dump** | **REJECTED** | CC BY-SA 4.0 **share-alike** on derived works, plus a **login-gated, click-through-gated** download whose terms are **actively disputed on Meta**. Fails the automation bar and the licence bar. (Full write-up in A10.) |
| **Olist (Kaggle)** | **FLAGGED - use only as a secondary, never as the primary** | **CC BY-NC-SA 4.0**: non-commercial *and* share-alike, which propagates to your derived silver/gold tables. Contaminates the project licence. (A4.) |
| **OpenStreetMap / .osc history dumps** | **REJECTED** | **ODbL - share-alike.** Irony: the OSM *history* dump is a genuine, real, full-revision change feed (arguably the best real change stream on the public internet) and ODbL still makes it unusable for a permissively-licensed portfolio. **This is the single most frustrating rejection in the report** and worth naming as such. |
| **OpenFlights (airports/routes/planes)** | **REJECTED** | **ODbL - share-alike.** Also partly derived from OurAirports, so B1 gives you the licence-clean subset anyway. |
| **Open Food Facts** | **REJECTED** | **ODbL - share-alike** for the product database. Would otherwise have been a strong high-cardinality product/taxon candidate. |
| **MusicBrainz** | **REJECTED** | Core release data is **CC0**, but **supplementary data is CC BY-NC-SA** - a **split licence with an NC limb**. Split licences are exactly the trap this report is warning about: you cannot tell from a single "CC0" label that part of the schema is NC. |
| **Wikidata** | **REJECTED on volume, not licence** | **CC0** (genuinely clean) and the full revision history *is* a real change stream - but the dump is enormous and the JSON is deeply nested with almost no tabular structure. Engineering effort goes into parsing, not into the lakehouse story. |
| **Yelp Dataset Challenge / Netflix Prize** | **REJECTED** | Custom **non-commercial EULA** with registration click-through. Not publishable, not automatable unattended. |
| **Ergast / Jolpica F1 database** | **REJECTED - licence unverified** | I could not verify an explicit, current licence from a primary source. The original project went unmaintained. **Rule applied: an unverified licence is a rejection, not a caveat.** |
| **Kaggle, as a class** | **SYSTEMIC RISK, not a rejection** | Most Kaggle datasets are published under **"Other (specified in description)"**, which frequently means no clear terms at all. The Olist case is the *good* outcome - a recognisable CC licence. **Never assume a Kaggle dataset is CC0. Read `meta_license`/the dataset page every time.** |
| **ClickBench `hits` dataset** | **OUT OF SCOPE for this angle** | Genuinely useful for ClickHouse serving benchmarks, but it is a single flat web-analytics table with **no foreign keys, no relationships and no business key problem.** It is the wrong shape for this angle. |

### Standing risks in the recommended set

| Risk | Where | Mitigation |
|---|---|---|
| Share-alike contamination of derived data | Olist, Stack Exchange, OSM, OpenFlights, OFF, MusicBrainz | **Excluded from the recommended set.** Do not let a share-alike dataset touch your gold layer. |
| Non-commercial restriction | Olist (NC), Stack Exchange (contested), Yelp/Netflix (EULA) | **Excluded from the recommended set.** |
| Non-OSS permission notice | TPC-C, TPC-H, TPC-DS | Acceptable. Reproduce the TPC notice verbatim in the repo. |
| Licence-restricted subset inside an otherwise open dataset | ONSPD Northern Ireland (`BT`) - LPS internal-use-only | **Exclude `BT` postcodes from published gold tables; document the exclusion and its reason.** |
| Login-gated / click-through-gated download | Stack Exchange, HUD bulk files | Stack Exchange: rejected. **HUD bulk is a free HUD User login; the API is token-based. Automate via the API, or cache the `.xlsx` and document that it is a manual step.** |
| Rate limits / IP bans | Companies House (600 req/5 min per key; 2,000/5 min per IP; 2 streaming connections; IP ban for reconnect abuse) | Exponential back-off, single long-lived connection, persist the `timepoint` cursor. **The incident write-up is a feature, not a bug.** |
| Fair-access / `User-Agent` policy | SEC EDGAR | Real contact `User-Agent`, polite throttling. Non-negotiable. |
| Missing licence file on a code mirror | `databricks/tpch-dbgen` (GitHub API: `license: None`) | Use the official `TPC-H_Tools_v3.0.1.zip` from tpc.org. |
| Stale/removed upstream resource | **`debezium-postgres-decathlon` and `debezium-example-data` both return HTTP 404 (verified 2026-09-27)** | **Do not plan around decathlon.** Pin every dependency to a commit and add a link-check in CI. |

---

## Ranked shortlist (five)

**1. TPC-C v5.11.0 driven against a live Postgres - the streaming spine.**
*Licence:* TPC permission-with-notice, attribution required. *Size:* 9 tables; `W=10` ≈ 3M rows, `W=100` ≈ 30M rows; no TPC-official loader, so budget a build step. This beats every runner-up because it is the **only** candidate that yields **genuinely real binlog-level CDC** without you inventing a single event. The spec publishes the exact DML of all five transactions, so a New-Order gives you a 4-table transactional fan-out with a real `UPDATE` of a counter column; Delivery gives you a `DELETE` plus **two NULL→value `UPDATE`s** - the single most important Iceberg/Flink upsert case; Payment gives you another `UPDATE`; and 1% of New-Orders roll back, so your stream contains real aborted transactions. Nothing else in the report can be defended against *"where did those update and delete events actually come from?"* The runner-up (Companies House) publishes *real* change events, but at API level: `fields_changed` is a wonderful field-level change mask, yet there is no transaction spanning multiple tables, no before-image, and no atomicity - so the "single database transaction" story the JD cares about is missing. The runner-up also fails on two counts TPC-C wins on: TPC-C's composite primary keys (`(o_id,ol_number)`, `(s_i_id,s_w_id)`) force you to get Iceberg equality-deletes-on-composite-keys right, which is a genuine correctness trap that a UUID-keyed JSON feed never tests; and TPC-C's `NEW_ORDER` insert-then-delete lifecycle is the natural parable for compaction and retention. Its real costs - no timezone handling, no semi-structured columns, no accidental data-quality defects - are costs the runners-up also do not fix.

**2. UK Companies House - REST API + Streaming API + monthly/daily snapshots - the second, independent change stream.**
*Licence:* free products under OGL v3.0 / recorded as CC Attribution on data.gov.uk; the paid Corporate Dataset is Crown copyright under s.47/50 CDPA and is **not** usable. *Size:* millions of live companies; monthly multi-file CSV zip, daily PSC JSON, plus paginated JSON APIs. This beats TPC-H because it delivers something TPC-H structurally cannot: **a real publisher emitting real, dated, typed change envelopes**, with `event.type`, **`event.fields_changed[]`**, `event.published_at`, `event.timepoint` and `resource_kind` - and with **snapshots that carry the `timepoint` they were taken at**, so you resume the stream exactly where the snapshot stopped. That is the snapshot/incremental contract a lakehouse CDC landing job needs, implemented by the publisher rather than by you. It is also the only candidate with **first-class nested structures that carry their own timestamps** (`resolutions[]`, `annotations[]`), a documented **`data`-absent-on-delete** stream case that will genuinely crash a naive consumer, and a first-class reliability story: 600 requests/5 min per key, 2 concurrent streaming connections, `416` on a stale timepoint, and an IP-ban policy for reconnect abuse - which hands you a real incident postmortem. Against Olist it wins decisively: Olist's CDC is **synthesised from a dead 2016–2018 snapshot** and its CC BY-NC-SA licence would propagate to your gold tables, whereas Companies House is clean and genuinely live.

**3. UK ONSPD (ONS Postcode Directory) - the reference dimension that makes geography load-bearing.**
*Licence:* OGL v3.0, attribution required (OS / Royal Mail / ONS statements); **Northern Ireland `BT` postcodes are internal-business-use-only and must be excluded or separately licensed.** *Size:* 235 MB multi-CSV zip / 2.31 GB hosted table; ~2.7M live + terminated postcodes; **one record with 137 fields**; TXT fixed-width and CSV. This beats OurAirports and GeoNames on one decisive axis: **it is the only reference dataset here with a published, first-class SCD2 temporal pair** - I verified `DOINTR` ("date of introduction, YYYYMM") and `DOTERM` ("date of termination, YYYYMM, **null = 'live' postcode**") directly in the ONSPD record specification, and the directory explicitly retains terminated postcodes that have not been re-used. So quarter-over-quarter diffing produces a **real** change stream of real inserts, real updates and real terminations - T2, not T3 - from a clean-licence statutory source. It also has three different as-of dates *within a single release* (postcodes as of the 3rd Friday of the previous month, admin areas as of the preceding May, health areas as of latest known), which is a temporal-alignment problem no synthesised dimension reproduces; a **two-CRS problem** (EPSG:27700 vs Irish Grid); a `NULL`-means-live semantic; three representations of one business key (`PCD`/`PCD2`/`PCDS`); and - best of all - **the publisher's own Data Quality section is your test suite**, including the line *"the use of the ONSPD to allocate individual addresses to geographies might be imprecise because of the effects of straddling and wrong assignments."* The authoritative source admitting its own joins are lossy is the best material in this report for the "automated data-quality checks" and "governance" requirements. It beats the alternatives because OurAirports and GeoNames are **Type 1** with no temporal dimension at all, and because ONSPD alone has 137 columns, which makes **column pruning a demonstrable physical-layout optimisation** and gives a real MERGE-heavy, delete-free Iceberg v2 write profile that is the deliberate contrast to TPC-C's churn.

**4. TPC-H 3.0.1 (or TPC-DS 4.0.0) at SF100 - the batch, serving and physical-layout leg.**
*Licence:* TPC permission-with-notice, attribution required. *Size:* 8 tables; verified DuckDB pre-generated sizes - `sf100` 26 GB, `sf300` 78 GB; `dbgen` available, DuckDB's `tpch` extension available (with DuckDB's own caveat that its generated data *"has small differences from the official TPC-H specification"*). This beats choosing the *reference* datasets as #4 because it is the only candidate that earns **"ClickHouse serving layer… query performance tuning"** with numbers a reviewer can check: 22 published queries with **published expected answers** at SF 0.01/0.1/1, and ClickHouse publishes TPC-H results routinely, so your serving-layer numbers are **comparable to published figures** rather than self-invented. At SF100, `lineitem` is 600M rows and the `lineitem`→`partsupp` **composite-key** join is a real shuffle hazard, `o_orderdate` range partitioning and `l_orderkey` sort order are decisions with measurable before/after, and the answers give you an assertion oracle. Pick **TPC-DS instead if your pitch is "expert dimensional/data modeling"** - its heterogeneous fact grains (`store_sales` / `catalog_sales` / `web_sales` at different grains over shared keys) force a grain-unification decision TPC-H's clean schema never will. It is honestly the *weakest* of the shortlist on this angle's own terms, and the README must say so: **TPC-H is insert-only, produces no UPDATEs or DELETEs, and has no NULLs at all**, so it is a performance fixture, not a quality fixture, and **any data-quality defects you demo on it are ones you manufactured.**

**5. SEC EDGAR XBRL `companyfacts` - the bitemporal "restatement" leg.**
*Licence:* **US public domain (17 U.S.C. § 105)** - the cleanest licence of all sixteen candidates, with no attribution requirement. *Size:* one JSON document per company (Apple's is 3.8 MB, verified live); a selective crawl, not a bulk download. This beats the remaining options - GeoNames, OurAirports, Sakila, Synthea, TPC-DS, the HUD crosswalk - because it is the only candidate in the report that hands you a **genuine, real-world UPDATE semantic that no synthesiser reproduces faithfully**: the same (entity, concept, period) reappearing under a **different `accn` value** because a 10-K/A amendment **restated a previously filed period**, years after the original fact. That is real business change with a real reason and real attribution. Combined with `end` (period) versus `filed` (knowledge date), it is the canonical **bitemporal** problem in a primary source, and it produces the best retention-and-compaction argument in this report - *because the late-arriving data is real*, not contrived. It also yields the cleanest serving-layer answer of any candidate: ClickHouse's `ReplacingMergeTree` keyed on `(cik, concept, end)` ordered by `(end, filed)` is the textbook correct design, and you can demonstrate **why** a plain `MergeTree` silently returns wrong answers. It is T2, not T1, and it must be labelled as a *document-arrival* feed with **no deletes - supersession instead**, which you implement as a soft delete. Its honest gap: `EntityAddress` is not in `companyfacts`, so **geography is thin**, and it must be crawled politely with a real `User-Agent`.

**Explicitly not in the shortlist, and why:** Olist (NC + SA licence propagation, and T3 CDC), Stack Exchange (SA + login gate + disputed terms), OSM/OpenFlights/Open Food Facts (ODbL share-alike), MusicBrainz (split CC0 / CC BY-NC-SA), Sakila (BSD-2 but 45k rows and no workload - a five-minute smoke test, not a headline), Synthea (Apache-2.0 and the best semi-structured source available, but wholly synthetic with no real change events and no shared domain with the commerce spine), the HUD crosswalk (public domain and outstanding, but the *strongest* version of this report's second-best idea and it needs a US primary source that does not exist in this angle), and data.gov.my (CC BY 4.0 and locally relevant, but flat single tables that force no engineering at all).

---

## Target-job requirements still undemonstrated by this angle

Stated plainly, because a gap you name is a gap you can argue about; a gap you hide is a gap a reviewer finds.

**Not demonstrated by ANY candidate here:**

| JD requirement | Why this angle cannot cover it |
|---|---|
| **"Solid AWS fundamentals: S3, IAM, VPC/networking, and RDS"** | *Partially* covered: RDS Postgres is the natural CDC source for TPC-C and S3 is where Iceberg lands. **IAM, VPC and networking are infrastructure, not data.** They need to be demonstrated by the Terraform/EKS/Prometheus side of the project, not by a dataset. **This is the single largest gap in the whole proposal and it belongs to another workstream.** |
| **"Multi-region and/or cross-account data platform experience"** | No dataset can demonstrate this. It requires a genuinely cross-region, cross-account S3/Polaris/EKS topology. **Structurally impossible from data selection.** |
| **"Security and compliance frameworks (GDPR, HIPAA, SOC 2, etc.)"** | Partially and *only as theatre*. Olist gives PII-adjacent columns (real Brazilian consumer data shape); Synthea gives an explicitly non-real patient record set. **Neither is actually in scope of GDPR or HIPAA.** You can build a column-level access-control and PII-tagging layer over them, which is a real control - but you must describe it as a *"GDPR-shaped control over PII-flagged columns"*, never as GDPR compliance. **Real compliance evidence comes from the governance/IaC workstream.** |
| **"Observability stacks (Prometheus, Grafana, Alertmanager)"** | Entirely an infrastructure concern. **No dataset contributes.** The *existence* of the Companies House 429/416/IP-ban behaviour gives you real metrics to plot, which is the only contribution available from this angle - and it is a good one. |
| **"Cost optimization for cloud data/streaming platforms"** | The Iceberg/ClickHouse layout and retention decisions (compaction on TPC-C's `NEW_ORDER`, Type 2 retention justified by SEC restatements arriving years later, column pruning on ONSPD's 137 fields) all *informing* a cost argument. **No candidate produces a cost figure you can trust**, because cloud prices change and your own account differs. |
| **"Proficiency in at least one of Python, Java, or Scala"** | Synthea is Java and running it is the strongest instance in this angle. Everything else is pipelines *you* write, which is the same requirement as every other workstream. |
| **"Excellent communication and stakeholder-management skills"** | **No dataset contributes.** Belongs to the documentation, ADRs and write-up workstream. |

**Demonstrated only weakly, and honestly labelled as such:**

| JD requirement | What this angle can honestly show |
|---|---|
| **"Automated data-quality checks"** | Strong from **Olist** (real, verified defects) and **ONSPD** (publisher-documented defects) - but **Olist's licence keeps it off the primary path.** TPC-C and TPC-H have **no genuine quality defects**, so if you exclude Olist you must **not** claim this requirement is met by your data. **This is the sharpest tension in the whole angle and you should surface it in the proposal rather than let a reviewer find it.** |
| **"Data governance: catalog organization, access control, data lineage"** | ONSPD's three-as-of-dates + versioned releases + the `BT` licence restriction + SEC's restatement lineage are a strong, concrete story. But **"access control" in the Polaris/column-policy sense is an engineering deliverable, not a data property.** |
| **"Apache Flink (real-time upserts / streaming)"** | **Genuinely demonstrated** by TPC-C (T1). **Only approximated** by Companies House (T2, API-level) and by Flink-over-two-Parquet-releases (batch mislabelled as stream - do not do it). **Saying which is which is mandatory.** |
| **"Debezium CDC → Apache Kafka"** | **Fully demonstrated by TPC-C only.** Every other candidate is a substitute and must be labelled one. |
| **"Apache Spark (batch silver/gold)"** | Demonstrated by TPC-H/TPC-DS (26–78 GB, checkable answers) and by ONSPD (235 MB, 137 columns). **A5 (Sakila) and A9 (the 4-table tutorial) do not count at their sizes.** |

**The honest one-paragraph version to put in the proposal:**
*This angle gives you a real, spec-defined, licence-clean OLTP workload that produces genuine binlog-level change events; a second, independent, publisher-emitted change stream over a statutory registry; a published SCD2 postal dimension with a null-as-live semantic and three as-of dates; a checkable 26–78 GB analytical set for batch and serving; and a public-domain bitemporal financial-fact source with real restatements. It does not, and cannot, give you AWS IAM/VPC, multi-region/cross-account, genuine GDPR/HIPAA evidence, Prometheus/Grafana, or stakeholder communication. Those five are infrastructure, compliance and communication deliverables, and they must be sourced from the platform and governance workstreams. The data angle's one unresolved weakness is data quality: the two datasets with genuinely broken data (Olist, and any source messy enough to matter) either carry a share-alike/non-commercial licence or are too clean - so either accept a "DQ checks on a synthetic-defect model, clearly labelled" position, or put ONSPD's publisher-documented defects at the centre of the DQ story, which is cleaner and licence-safe and is what I recommend.*

---

## Sources consulted (all primary unless noted)

**Discovery indexes (indexes only, not evidence):** `https://github.com/awesomedata/awesome-public-datasets` (README.rst, master) · `https://github.com/sindresorhus/awesome` (Big Data section)

**Primary sources:**
- TPC: `tpc.org/tpc_documents_current_versions/current_specifications5.asp` · `tpc.org/tpc_documents_current_versions/pdf/tpc-c_v5.11.0.pdf` · `github.com/databricks/tpch-dbgen` (GitHub API: no licence file)
- DuckDB TPC-H: `https://www.duckdb.org/docs/current/core_extensions/tpch` (verified pre-generated DB sizes, and the spec-fidelity caveat)
- Debezium: `https://github.com/debezium/container-images/blob/main/examples/postgres/3.0/inventory.sql` · full recursive tree of `debezium/debezium@main` (negative finding: no `decathlon` path) · GitHub API 404 checks on `debezium-postgres-decathlon` and `debezium-example-data` (both 404, 2026-09-27)
- Companies House: `developer.company-information.service.gov.uk` · `developer-specs.company-information.service.gov.uk/streaming-api/` (stream schema, `fields_changed`, `timepoint`) · `.../guides/rateLimiting` · `gov.uk/guidance/companies-house-data-products` · `ckan.publishing.service.gov.uk/dataset/basic-company-data` (verified live)
- ONSPD: `ons.gov.uk/methodology/geography/geographicalproducts/postcodeproducts` · ONSPD User Guide PDF (downloaded and text-extracted; record specification Annex A, licensing §3, data-quality section) · `ckan.publishing.service.gov.uk/dataset/ons-postcode-directory-may-2026` (235 MB / 2.31 GB)
- OurAirports: `ourairports.com/data/` (licence, file sizes, dates) · `ourairports.com/help/data-dictionary.html` (`ident` vs `id`) · `github.com/davidmegginson/ourairports-data` (Unlicense, daily-update caveat)
- GeoNames: `download.geonames.org/export/` · `/export/dump/readme.txt` · `/export/zip/readme.txt` · `sws.geonames.org/about.html` (upstream attributions) · live `Last-Modified`/`Content-Length` on `allCountries.zip`, `dump/GB.zip`, `zip/GB.zip`
- HUD: `huduser.gov/portal/datasets/usps_crosswalk.html` · `huduser.gov/portal/dataset/uspszip-api.html` · `huduser.gov/hudapi/public/usps` · `huduser.gov/datasets/usps/usps_data_dictionary.pdf`
- Olist: `kaggle.com/datasets/olistbr/brazilian-ecommerce` (verified live, licence rendered as CC BY-NC-SA 4.0) · `github.com/datahub-project/static-assets/tree/main/datasets/olist-ecommerce` (row counts, schema, DQ) · independent full-table profiling (DQ findings and per-table defect counts)
- Sakila: `github.com/jOOQ/sakila` (GitHub API: BSD-2-Clause) · `raw.githubusercontent.com/jOOQ/sakila/master/postgres-sakila-db/postgres-sakila-schema.sql` (fetched and counted: 21 `CREATE TABLE` → 16 logical)
- Synthea: `github.com/synthetichealth/synthea` README · `.../blob/master/LICENSE` (Apache-2.0, read)
- SEC: `data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json` (HTTP 200, 3,789,099 bytes) · `sec.gov/os/accessing-edgar-data`
- Stack Exchange: `meta.stackexchange.com/questions/401324/...` · `meta.stackexchange.com/questions/2677/...`
- data.gov.my: `https://data.gov.my/data-catalogue` (verified live; parsed embedded JSON for licence text, `link_parquet`, `meta_license`)

**Licence risk decisions referenced:** CC BY-NC-SA 4.0 (Olist) · CC BY-SA 4.0 (Stack Exchange) · ODbL (OSM, OpenFlights, Open Food Facts) · CC0 + CC BY-NC-SA split (MusicBrainz) · CC BY 4.0 (GeoNames, data.gov.my) · OGL v3.0 (ONSPD, with the Northern Ireland LPS carve-out) · Unlicense / public domain (OurAirports) · US public domain (HUD, SEC) · Apache-2.0 (Synthea, Debezium) · BSD-2/3 (Sakila variants) · TPC permission-with-notice (TPC-C, TPC-H, TPC-DS) · s.47/50 CDPA (**not open** - Companies House Corporate Dataset, excluded)

**Negative findings worth carrying forward:** `debezium-postgres-decathlon` and `debezium-example-data` are both **404**; `databricks/tpch-dbgen` has **no licence file**; `databricks` TPC-H mirror vs DuckDB `tpch` extension have documented spec-fidelity differences; the ONSPD's Northern Ireland `BT` subset is **not** covered by the OGL; the Companies House **Corporate Dataset** is not open data.

