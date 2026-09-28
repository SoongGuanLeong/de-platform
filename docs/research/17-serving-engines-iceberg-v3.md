# 17 - Serving engines that read Apache Iceberg v3: Doris 4.1, Trino 480+, StarRocks, and the ClickHouse baseline

**Date of research:** 2026-09-28. All evidence accessed 2026-09-28 unless stated.
**Scope:** which engines can read, and where relevant write, Apache Iceberg format-version 3 (v3) deletion vectors (DVs), and which of those are serving stores rather than query engines, so that the serving-layer choice can be compared against ClickHouse.
**Question answered:** can Apache Doris 4.1 read and write Iceberg v3 DVs on a released version, what governance features does it ship, and is it a serving store; does Trino 480+ read and write v3 and is it only a query engine; does StarRocks fail fast on v3 DVs and is issue #75621 real; and is any other locally runnable serving store (not a query engine) able to read Iceberg v3 DVs on a released version.
**Exact versions read:** Apache Doris **4.1.0** (released 2026-04-16) and the 4.1.x line up to **4.1.4** (released 2026-09-07); Trino **480** (released 2026-03-24) and **483** (released 2026-07-17); StarRocks `main` and `branch-4.1` as of 2026-09-28; ClickHouse `master` as of 2026-09-28.

This document re-verifies the claims in the ticket against primary sources: the projects' own release notes, documentation source files, and issue/PR trackers. It does not repeat the ClickHouse DV investigation in depth, which is covered by the parallel ClickHouse research; it uses the ClickHouse finding only as the baseline the others are compared against.

---

## 1. Summary

| | Apache Doris 4.1 | Trino 480+ | StarRocks | ClickHouse (baseline) |
|---|---|---|---|---|
| Reads Iceberg v3 DVs | **Yes**, since 4.1.0 [S2], [S3] | **Yes**, since 480 [S10], [S11] | **No**, fails fast [S15], [S16] | **Not on the pinned LTS**: 26.8 LTS hard-fails on a Puffin DV; read support lands in 26.10 / 27.3 [S25] |
| Writes Iceberg v3 DVs | **Yes**, via UPDATE/DELETE/MERGE INTO, since 4.1.0 (experimental) [S2], [S3] | **Yes**, since 480 (documented as experimental) [S10], [S11] | No, and v3 DML is explicitly rejected [S16], [S18] | No [S21], [S25] |
| Type | Serving store (own storage engine) [S6] | Query engine, no storage [S12] | Serving store | Serving store |
| Row Policy | Built-in `CREATE ROW POLICY` [S5] | Not an engine feature | Not assessed here | Not assessed here |
| Column Permission | Built-in `GRANT Select_priv(col)` [S5] | Not an engine feature | Not assessed here | Not assessed here |
| Data Masking | **Apache Ranger only**, since 2.1.2 [S5] | Not an engine feature | Not assessed here | Not assessed here |
| Licence | Apache-2.0 [S8] | Apache-2.0 [S14] | Apache-2.0 [S20] | Apache-2.0 |
| Governance | ASF top-level project, graduated 2022-06-16 [S8] | Trino Software Foundation, independent non-profit [S14] | Linux Foundation project [S20] | Company-backed (ClickHouse Inc) |
| Single container on 12 CPU / 14 GB | Yes, as the official all-in-one CI/dev image [S7] | Yes, as a JVM, but it is not a serving layer [S12] | Not reached (fails on capability first) | Baseline |

The load-bearing result: **Apache Doris 4.1 is the only released, locally runnable, open-source serving store that both reads and writes Iceberg v3 deletion vectors.** Trino 480+ also reads and writes v3, but it is a query engine with no storage of its own, so it cannot stand in for ClickHouse as a serving layer. StarRocks does not read v3 DVs at all: it fails fast, and the read-support work is still an unmerged pull request.

---

## 2. Apache Doris 4.1

### 2.1 Version and release date

- **4.1.0** is the release that introduced Iceberg v3 read and write. The project's own release entry is published **2026-04-16** [S4].
- The line is maintained: **4.1.4** is the current release, published **2026-09-07** [S4]. The Apache release catalogue lists the 4.1 branch as released [S4b].
- The 4.1.0 release note states the capability directly: "Doris now fully supports INSERT, UPDATE, DELETE, and MERGE INTO operations for Iceberg V2 and V3 formats, and also supports many new features in the Iceberg V3 standard, such as Deletion Vector and Row Lineage" [S2].
- The Iceberg feature page states: "Apache Doris reads and writes V2 position and equality deletes, and V3 deletion vectors (Puffin) are supported since 4.1" [S1].

### 2.2 Reads and writes v3 deletion vectors

The Iceberg catalog reference is the most precise primary source, and it separates read from write:

- **Read:** "Supports reading Deletion Vector (Since 4.1.0)" [S3].
- **Write:** for `DELETE`, "for V2 format tables, the system writes Position Delete files; for V3 format tables, the system writes Puffin-format Deletion Vectors files" [S3]. `UPDATE` and `MERGE INTO` use the same mechanism: "using Position Delete files for V2, and Puffin-format Deletion Vectors for V3" [S3]. The page adds that on a V3 table "the system not only uses Puffin-format Deletion Vectors to replace the original Position Delete data, but also automatically adjusts the lineage lifecycle attributes (`_last_updated_sequence_number`)" [S3].
- The same page labels all three of `DELETE`, `UPDATE` and `MERGE INTO` on Iceberg as "an experimental feature, supported since version 4.1.0" [S3]. That is a caveat, not a blocker, but it should be recorded: Doris's v3 row-level DML is experimental in the same way Trino's is (Section 3).
- Related v3 features: row lineage is "an experimental feature, supported since version 4.1.0" [S3]; v3 column default values are supported "since version 4.1.4" [S3].
- The feature page's key-terms section says "Doris reads V1 through V3 and writes V2 by default. V3 writes need format version 4.1+" [S1], which means v3 write requires Doris 4.1 or later.

Code-level confirmation exists in the Doris backend: the tree contains an Iceberg deletion-vector reader (`be/src/format/table/deletion_vector_reader.cpp`, `iceberg_delete_file_reader_helper.cpp`) and an Iceberg delete sink that tracks "the number of rows after merging the old deletion vector and position delete" (`be/src/exec/sink/viceberg_delete_sink.h`), and the thrift definitions carry v3 DV fields ("For deletion vector (V3): offset of the DV blob within the Puffin file", "6 & 7 : iceberg v3 deletion vector") [S9]. The reader is described as materialising "an Iceberg deletion vector as one buffer", which is an implementation limit worth noting for very large DVs [S9].

### 2.3 Row Policy, Column Permission, Data Masking

All three exist, but only two are built into Doris; masking depends on Ranger [S5]:

- **Row Policy:** built in. "For a user configured with a Row Policy, Doris automatically appends the predicate defined in the Row Policy to the query." Created with `CREATE ROW POLICY ... ON <table> AS RESTRICTIVE TO <user> USING (<predicate>)` [S5].
- **Column Permission:** built in, but only for `Select_priv`. Grant with `GRANT Select_priv(col1,col2) ON ctl.db.tbl TO user1` [S5].
- **Data Masking:** **Apache Ranger only.** "Starting from version 2.1.2, Doris supports setting masking policies on columns through Apache Ranger Data Masking. This is currently the only supported configuration path" [S5]. So masking requires deploying and integrating Ranger, which is an external service and an additional footprint.
- Limitation to record: none of the three take effect for the default `root` and `admin` users [S5].

So the answer is: Row Policy and Column Permission are built-in; Data Masking is via Apache Ranger, not built-in.

### 2.4 Serving store or query engine

Doris is a real serving store with its own storage engine, not a federating query engine:

- Its own storage writes "through a structure similar to LSM-Tree, and continuously merges small files into large ordered files through compaction in the background. Compaction handles operations such as deletion and updating" [S6]. That is the MergeTree-like model the question asks about.
- It has first-class table models: Duplicate, Aggregate, and Unique Key, where "The Doris Unique Key Model guarantees the uniqueness of Key columns and supports UPSERT and deduplication" [S6]. A Unique Key Merge-on-Write table is the recommended shape for high-concurrency primary-key point queries and wide-table top-N [S6].
- Its Iceberg support is additive: the same cluster "serves dashboards" and also reads and writes Iceberg, joining Iceberg facts with Doris warehouse tables in one MPP plan [S1].

That is the structural difference from Trino: Doris has somewhere to serve from; Trino has to read the lakehouse every time.

### 2.5 Local footprint on 12 CPU / 14 GB

There are two documented footprints, and they disagree, which matters here:

- **Production guidance** [S7]: general server memory is "CPU cores x 4 GB" minimum, "CPU cores x 8 GB" recommended; per component, FE minimum 16 GB and BE minimum "CPU cores x 4 GB". A 12-core host therefore implies 48 GB minimum by that formula, and even the co-located dev/test table lists Frontend 8 GB plus Backend 16 GB, i.e. 24 GB, as the minimum for 1 FE + 1 BE on one server. **By its own production guidance, a 12 CPU / 14 GB host is below every Doris minimum.**
- **CI/dev footprint** [S7b]: the official all-in-one image runs "1 FE + 1 BE in one container, healthy in about 20 s" via `docker run apache/doris:all-in-one-4.1.3`. It is explicitly "an e2e / CI test fixture", and its memory is "tuned down for CI runners: FE heap `-Xmx2048m`, the BE-side JNI heap `-Xmx1024m`, and BE `mem_limit = 40%`". On a 14 GB host that is roughly 2 GB FE heap plus about 5.6 GB BE limit, which fits. The doc warns that all three all-in-one modes "are test / development environments, not production deployments: memory is tuned down to CI runner and workstation sizes, the single container has a single replica, and nothing is persisted by default". For reference, the multi-node and compute-storage separated compose clusters are heavier: a full compute-storage separated cluster "takes around 9 GB" and the doc advises giving Docker Desktop "12 GB or more" [S7b].

**Conclusion for the host:** Doris runs in a single container on a 12 CPU / 14 GB host only in its documented CI/dev fixture mode, with a single replica and no persistence by default. It does not meet Doris's own production minimums at that size. If the platform treats ClickHouse as a single-container demo serving store, Doris can occupy the same slot, but only as a demo, and the platform should say so rather than imply a production-grade deployment.

### 2.6 Licence and governance

Apache-2.0 [S8]. Apache Doris graduated from the Apache Incubator to an ASF top-level project on **2022-06-16** [S8b], so governance is foundation-based (ASF), not company-backed.

---

## 3. Trino 480+ (and current 483)

### 3.1 Reads and writes v3

- Release **480 (24 Mar 2026)** contains: "Add support for creating, writing to or deleting from Iceberg v3 tables. (#27786, #27788)" [S10]. The same release adds v3 column default values (#27837), v3 support in the `optimize`, `expire_snapshots` and `remove_orphan_files` procedures (#27836), and v3 row lineage (#27836) [S10].
- The current Iceberg connector documentation (Trino 483) states for `format_version`: "Optionally specifies the format version of the Iceberg specification to use for new tables; `1`, `2`, or `3`. Defaults to `2`. Version `2` is required for row level deletes. **Version `3` support is experimental. Row-level updates and deletes on version `3` tables use deletion vectors.** The `add_files` and `add_files_from_table` procedures are not supported on version `3` tables, and writing to encrypted tables is not supported. Version `3` is required for tables containing `VARIANT` columns." [S11]
- So Trino 480+ does read and write v3 DVs, and it says so plainly. It is also the engine that StarRocks's own feature request names as an engine "which already write[s] and read[s] V3 DV" [S15], which is independent corroboration.
- Current release is **483 (17 Jul 2026)** [S13].

### 3.2 Query engine, no serving store

Trino's own definition: "Trino is a distributed SQL query engine designed to query large data sets distributed over one or more heterogeneous data sources" [S12]. It has no storage engine, no local table store, and no serving layer of its own. Trino materialized views are stored as tables in a configured catalog (for example Iceberg), not in a Trino-owned serving store, and they are a query-acceleration feature rather than a latency-serving layer.

**Conclusion:** Trino 480+ cannot replace ClickHouse as a serving layer. It can read and write the same Iceberg v3 tables, which makes it useful as an interactive/federated query engine over the lakehouse, but every query reads object storage and delete metadata; it has nothing analogous to ClickHouse's MergeTree storage and local materialised tables. The correct framing is that Trino and ClickHouse are complementary, not substitutes.

### 3.3 Licence and governance

Apache-2.0 [S14]. Governance is the **Trino Software Foundation**, "an independent, non-profit organization", registered in Delaware, not the ASF and not a single vendor [S14b]. Foundation-based.

---

## 4. StarRocks: fails fast, and the read fix is not shipped

### 4.1 The cited issue is real, and its status is closed without a fix

- Issue **#75621**, "Support reading Iceberg V3 tables with Deletion Vectors", was opened **2026-07-01** and closed **2026-07-03** [S15]. It carries the label `type/feature-request` and no milestone.
- Its body states the failure exactly: "Today StarRocks cannot read a V3 table once any row-level delete has been applied, the scan planner fails fast with 'Iceberg V3 Deletion Vectors are not supported', so `SELECT` on such a table errors out entirely. This blocks interoperability with other engines, which already write and read V3 DV, and forces users to keep another engine around just to query tables that StarRocks otherwise supports." [S15]
- **Important correction to the ticket's framing:** the issue being closed is not evidence that StarRocks supports v3 DVs. The issue has **no comments**, **no linked pull request**, and **no referenced commit**; its timeline shows only a label, a cross-reference, two subscriptions, and the close [S15b]. A duplicate, #75620, was closed two days earlier on 2026-07-01 [S15c].

### 4.2 The fail-fast is deliberate, merged code

- PR **#70242**, "[Enhancement] Fail-fast for unsupported Iceberg V3 features", was merged to `main` on **2026-04-10** [S16].
- It was backported as PR **#71527** to `branch-4.1` on the same day, with the label `version:4.1.1` [S16]. So the "Iceberg V3 Deletion Vectors are not supported" error is intended behaviour that shipped in the 4.1.1 patch line, not an accident.

### 4.3 Read support is still unmerged

- PR **#75541**, "[Feature] Support reading Iceberg V3 deletion vectors", was **closed unmerged** on 2026-07-03 [S17].
- PR **#76228**, "[Feature] Support reading Iceberg v3 merge-on-read deletion vectors", is **still open** (opened 2026-08-07; last activity 2026-09-25) [S18]. It carries `documentation` and `PROTO-REVIEW`.
- The umbrella issue #60956, "Add support for Apache Iceberg V3 Table Specification", is still open (opened 2026-04-06) [S18b].
- There is also an open bug-fix PR #76552, "[BugFix] Reject row-level DELETE on non-V2 Iceberg tables at plan time" (2026-09-25, label `4.1`), which reinforces that StarRocks is still tightening the v3 rejection path rather than enabling it [S18c].

**Conclusion:** StarRocks fails fast on Iceberg v3 deletion vectors on released versions, the cited issue number is correct, and there is no released version that reads them. Any statement that StarRocks reads v3 DVs would be wrong today.

### 4.4 Licence and governance

Apache-2.0. The project describes itself as "A Linux Foundation project" [S20], contributed by CelerData, so governance is foundation-based (Linux Foundation) with a vendor origin.

---

## 5. Other serving stores

The question is specifically for a **serving store** (its own storage, able to serve queries with sub-second latency), not a query engine, that reads Iceberg v3 DVs on a **released** version and runs locally.

| Candidate | Reads v3 DV? | Serving store? | Local, released? | Verdict |
|---|---|---|---|---|
| Apache Doris 4.1 | Yes [S1], [S3] | Yes [S6] | Yes, single container [S7b] | The only qualifying OSS serving store |
| ClickHouse | Not on a released LTS as of 2026-09-28: 26.8 LTS reads v3 metadata but hard-fails on a Puffin DV [S25] | Yes | Yes | The baseline being compared; see the ClickHouse research [S25] for the exact version boundaries |
| StarRocks | No, fails fast [S15], [S16] | Yes | Yes, but capability missing | Rejected on capability |
| Databend | No evidence found [S22] | Yes (own storage) | Yes | Not counted; no DV/Puffin code or doc found |
| Dremio | Yes, read and write, but **Dremio Cloud** [S23] | Query engine with reflections, company-backed | No, managed cloud service | Fails "local, open-source serving store" |
| Databricks | Yes, via Unity Catalog [S24] | Managed warehouse, company-backed | No, managed | Fails "local, open-source serving store" |

Notes on the two non-local entries:

- **Dremio:** Dremio announced full read and write support for Iceberg v3 including deletion vectors on 2026-04-03, with a follow-up on 2026-04-27 stating "Deletion vectors are available on Iceberg v3 tables in Dremio Cloud today" [S23]. Dremio Cloud is a managed service, and Dremio is a query engine with reflections rather than an OSS serving store, so it does not meet the local single-container constraint.
- **Databricks:** "Use Apache Iceberg v3 with Unity Catalog to enable deletion vectors, VARIANT, row lineage, geospatial data types" (docs dated 2026-09-11) [S24]. Managed, proprietary, not locally runnable as an OSS container.

**Answer to the question:** apart from Doris, no locally runnable open-source serving store that reads Iceberg v3 DVs on a released version was found. The ClickHouse baseline is more nuanced than a single flag and was corrected by the parallel ClickHouse research [S25]: ClickHouse 26.8 LTS **does** read Iceberg v3 metadata (v3 reading predates 26.8, PR #107377 backported as far as 26.3.18.25), and it fails only when the current snapshot carries a Puffin deletion vector, with the hard error `BAD_ARGUMENTS "Position deletes are supported only for parquet format"` (`PositionDeleteTransform.cpp` at v26.8.13.2-lts). DV read support is merged to `main` (PR #110781, 2026-09-17, labels `can be tested` and `pr-experimental`) and is expected to reach a released line in ClickHouse 26.10 (Experimental, non-LTS, expected late October 2026) or the 27.3 LTS (expected late March 2027) [S25]. ClickHouse does not write DVs [S21], [S25].

---

## 6. Recommendation for the serving layer

- **If the requirement is "a released, local, open-source serving store that reads and writes Iceberg v3 DVs":** Apache Doris 4.1 is the only candidate that meets all four clauses. Its read support is since 4.1.0, its write support (UPDATE/DELETE/MERGE INTO writing Puffin DVs) is since 4.1.0 and is labelled experimental, and Row Policy and Column Permission are built in. Data Masking requires Apache Ranger, which is an extra service.
- **If the requirement is "a serving layer to replace ClickHouse":** Trino is not a candidate regardless of its v3 support, because it is a query engine with no serving store [S12]. StarRocks is not a candidate because it cannot read v3 DVs at all [S15], [S16].
- **The honest caveat to carry into the ADR:** Doris's v3 DML is documented as experimental [S3], exactly as Trino's v3 support is [S11]. A platform claim of production-grade Iceberg v3 write through Doris would overstate the project's own documentation.
- **Footprint caveat:** Doris's production minimums (FE 16 GB, BE cores x 4 GB) exceed a 12 CPU / 14 GB host; only the documented CI/dev all-in-one container fits, with one replica and no persistence by default [S7], [S7b]. If the host is fixed at 14 GB, Doris is a demo-tier serving store there, not a production one.

---

## 7. What I could not verify, and known discrepancies

- **Doris 4.1.0 date.** The GitHub release entry for 4.1.0 is published 2026-04-16 [S4], and the 4.1 feature page is dated 2026-05-11 [S1]. Community articles about the 4.1 launch are dated between 2026-04-27 and 2026-05-11. I used the project's own release entry (2026-04-16) and did not find an ASF announce email to confirm a separate GA date.
- **Doris all-in-one image and v3 DV.** I did not run the all-in-one container, so I cannot confirm from first-hand execution that the 4.1.3 image reads or writes v3 DVs; the claim rests on the 4.1 documentation and release notes [S1], [S2], [S3], plus the backend code [S9]. The single-container memory figures are the image's documented defaults, not measured.
- **ClickHouse detail (resolved by the parallel research).** The ClickHouse DV read merge (PR #110781, merged 2026-09-17) carries the labels `can be tested` and `pr-experimental` [S21]. The parallel ClickHouse research [S25] establishes the version boundary: 26.8 LTS reads v3 tables without Puffin DVs but hard-fails on a Puffin DV entry, and DV read is expected in 26.10 (Experimental, non-LTS, expected late October 2026) or 27.3 LTS (expected late March 2027). I did not independently verify those two forward-looking release expectations; they are the ClickHouse research's findings.
- **Databend.** Code search across `databendlabs/databend` for deletion-vector and Puffin terms returned no matches [S22]. That is an absence of evidence, not proof of absence; I did not read Databend's full Iceberg implementation.
- **Dremio OSS.** I did not verify the current maintenance status of any open-source Dremio distribution; the finding that Dremio is not a local OSS serving store rests on the v3 support being described as a Dremio Cloud feature [S23].
- **No benchmarks.** I ran no engine, so I state no throughput, latency, or recall numbers. All statements are structural (what a project documents, what its code does, what its tracker says).

---

## Sources

All accessed 2026-09-28 unless stated. "Doris docs" means the `apache/doris-website` repository at branch `master`.

| ID | Source | URL | Date |
|---|---|---|---|
| S1 | Apache Doris docs, Iceberg feature page (`docs/key-features/iceberg.mdx`): "V3 deletion vectors (Puffin) are supported since 4.1"; "Doris reads V1 through V3 and writes V2 by default. V3 writes need format version 4.1+"; write path stages "deletion vectors when rewriting" | https://github.com/apache/doris-website/blob/master/docs/key-features/iceberg.mdx | last_update 2026-05-11 |
| S2 | Apache Doris 4.1.0 release note (`releasenotes/v4.1/release-4.1.0.md`): "Doris now fully supports INSERT, UPDATE, DELETE, and MERGE INTO operations for Iceberg V2 and V3 formats, and also supports many new features in the Iceberg V3 standard, such as Deletion Vector and Row Lineage" | https://github.com/apache/doris-website/blob/master/releasenotes/v4.1/release-4.1.0.md | 4.1.0 |
| S3 | Apache Doris Iceberg catalog reference (`docs/lakehouse/catalogs/iceberg-catalog.mdx`): "Supports reading Deletion Vector (Since 4.1.0)"; DELETE/UPDATE/MERGE INTO write "Puffin-format Deletion Vectors files" on V3; all three "experimental feature, supported since version 4.1.0"; V3 default values since 4.1.4 | https://github.com/apache/doris-website/blob/master/docs/lakehouse/catalogs/iceberg-catalog.mdx | 2026-09-28 |
| S4 | Apache Doris GitHub releases: "Apache Doris 4.1.0 Release" published 2026-04-16; "Apache Doris 4.1.4 Release" published 2026-09-07 | https://github.com/apache/doris/releases | 2026-04-16 / 2026-09-07 |
| S4b | Apache Release Catalog, Apache Doris 4.1: branch status released, latest artifact 4.1.4 dated 2026-09-10 | https://release-catalog.apache.org/doris/4.1/artifacts.json | 2026-09-10 |
| S5 | Apache Doris docs, Data Access Control (`docs/admin-manual/auth/authorization/data.md`): Row Policy built-in; Column Permission built-in for `Select_priv`; "Data masking depends on Apache Ranger"; masking via Ranger "Starting from version 2.1.2" | https://github.com/apache/doris-website/blob/master/docs/admin-manual/auth/authorization/data.md | 2026-09-28 |
| S6 | Apache Doris docs: compaction (`docs/admin-manual/trouble-shooting/compaction.md`): "Doris writes data through a structure similar to LSM-Tree ... through compaction in the background"; Unique Key model (`docs/table-design/data-model/unique.md`) "guarantees the uniqueness of Key columns and supports UPSERT and deduplication" | https://github.com/apache/doris-website/blob/master/docs/admin-manual/trouble-shooting/compaction.md | 2026-09-28 |
| S7 | Apache Doris docs, environment check (`docs/install/preparation/env-checking.md`): memory minimum "CPU cores x 4 GB", recommended "CPU cores x 8 GB"; FE minimum 16 GB, BE "CPU cores x 4 GB"; dev/test co-located Frontend 8 GB + Backend 16 GB | https://github.com/apache/doris-website/blob/master/docs/install/preparation/env-checking.md | 2026-09-28 |
| S7b | Apache Doris docs, All-in-One Image (`community/developer-guide/all-in-one-image.md`): "1 FE + 1 BE in one container, healthy in about 20 s" via `docker run apache/doris:all-in-one-4.1.3`; "test / development environments, not production deployments"; "FE heap `-Xmx2048m` ... BE `mem_limit = 40%`"; compute-storage separated cluster "takes around 9 GB" | https://github.com/apache/doris-website/blob/master/community/developer-guide/all-in-one-image.md | 2026-09-28 |
| S8 | `apache/doris` repository metadata: licence Apache-2.0 | https://github.com/apache/doris | 2026-09-28 |
| S8b | ASF announcement, "The Apache Software Foundation Announces Apache Doris as a Top-Level Project", 2022-06-16 | https://news.apache.org/foundation/entry/the-apache-software-foundation-announces81 | 2022-06-16 |
| S9 | Apache Doris backend code: `be/src/format/table/deletion_vector_reader.cpp`, `be/src/format/table/deletion_vector.h`, `be/src/format/table/iceberg_delete_file_reader_helper.cpp`, `be/src/exec/sink/viceberg_delete_sink.h`, `gensrc/thrift/DataSinks.thrift` ("For deletion vector (V3): offset of the DV blob within the Puffin file"), `gensrc/thrift/PlanNodes.thrift` ("6 & 7 : iceberg v3 deletion vector") | https://github.com/apache/doris | 2026-09-28 |
| S10 | Trino release 480 (24 Mar 2026): "Add support for creating, writing to or deleting from Iceberg v3 tables. (#27786, #27788)"; v3 column default values (#27837); v3 table procedures (#27836); v3 row lineage (#27836) | https://github.com/trinodb/trino/blob/master/docs/src/main/sphinx/release/release-480.md | 2026-03-24 |
| S11 | Trino Iceberg connector docs (483): `format_version` "1, 2, or 3"; "Version 3 support is experimental. Row-level updates and deletes on version 3 tables use deletion vectors." | https://github.com/trinodb/trino/blob/master/docs/src/main/sphinx/connector/iceberg.md | 2026-09-28 |
| S12 | Trino overview: "Trino is a distributed SQL query engine designed to query large data sets distributed over one or more heterogeneous data sources." | https://trino.io/docs/current/overview.html | 2026-09-28 |
| S13 | Trino release 483 (17 Jul 2026) | https://github.com/trinodb/trino/blob/master/docs/src/main/sphinx/release/release-483.md | 2026-07-17 |
| S14 | `trinodb/trino` repository metadata: licence Apache-2.0 | https://github.com/trinodb/trino | 2026-09-28 |
| S14b | Trino Software Foundation: "Its governance is controlled by the Trino Software Foundation (TSF). The TSF is an independent, non-profit organization" | https://trino.io/foundation.html | 2026-09-28 |
| S15 | StarRocks issue #75621, "Support reading Iceberg V3 tables with Deletion Vectors": opened 2026-07-01, closed 2026-07-03, label `type/feature-request`; body states the scan planner "fails fast with 'Iceberg V3 Deletion Vectors are not supported'" | https://github.com/StarRocks/starrocks/issues/75621 | opened 2026-07-01, closed 2026-07-03 |
| S15b | StarRocks issue #75621 timeline: no comments, no linked PR, no commit; events are label, cross-reference (issue #75541), two subscriptions, close | https://api.github.com/repos/StarRocks/starrocks/issues/75621/timeline | 2026-09-28 |
| S15c | StarRocks issue #75620, "Support reading Iceberg V3 tables with Deletion Vectors (Puffin DV)": opened 2026-07-01, closed 2026-07-01 | https://github.com/StarRocks/starrocks/issues/75620 | 2026-07-01 |
| S16 | StarRocks PR #70242, "[Enhancement] Fail-fast for unsupported Iceberg V3 features", merged 2026-04-10; backport PR #71527 to `branch-4.1` merged 2026-04-10 (label `version:4.1.1`) | https://github.com/StarRocks/starrocks/pull/70242 | 2026-04-10 |
| S17 | StarRocks PR #75541, "[Feature] Support reading Iceberg V3 deletion vectors", closed unmerged 2026-07-03 | https://github.com/StarRocks/starrocks/pull/75541 | 2026-07-03 |
| S18 | StarRocks PR #76228, "[Feature] Support reading Iceberg v3 merge-on-read deletion vectors", open, opened 2026-08-07, last activity 2026-09-25 | https://github.com/StarRocks/starrocks/pull/76228 | 2026-08-07 |
| S18b | StarRocks issue #60956, "Add support for Apache Iceberg V3 Table Specification", open, opened 2026-04-06 | https://github.com/StarRocks/starrocks/issues/60956 | 2026-04-06 |
| S18c | StarRocks PR #76552, "[BugFix] Reject row-level DELETE on non-V2 Iceberg tables at plan time", open, 2026-09-25 | https://github.com/StarRocks/starrocks/pull/76552 | 2026-09-25 |
| S20 | `StarRocks/starrocks` repository metadata: licence Apache-2.0; description "A Linux Foundation project" | https://github.com/StarRocks/starrocks | 2026-09-28 |
| S21 | ClickHouse issue #107502, "Support reading Iceberg v3 deletion vectors": opened 2026-06-15, closed 2026-09-17; body "ClickHouse currently supports Iceberg position/equality delete files, but Iceberg v3 deletion vectors are still listed as unsupported"; linked PR #110781 merged 2026-09-17, labels `can be tested`, `pr-experimental`, `comp-datalake`; writing DVs out of scope | https://github.com/ClickHouse/ClickHouse/issues/107502 | opened 2026-06-15, closed 2026-09-17 |
| S22 | `databendlabs/databend` code search for deletion-vector and Puffin terms returned no matches; repository active (last push 2026-09-28) | https://github.com/databendlabs/databend | 2026-09-28 |
| S23 | Dremio, "Dremio Adds Apache Iceberg V3 Support" (2026-04-03) and "Iceberg Deletion Vectors: The Better Way to Delete Rows" (2026-04-27): "Deletion vectors are available on Iceberg v3 tables in Dremio Cloud today" | https://www.dremio.com/blog/dremio-advances-the-modern-iceberg-lakehouse-with-iceberg-v3-support/ | 2026-04-03 / 2026-04-27 |
| S24 | Databricks docs, "Use Apache Iceberg v3 features": enable deletion vectors, VARIANT, row lineage, geospatial data types with Unity Catalog | https://docs.databricks.com/aws/en/iceberg/iceberg-v3 | 2026-09-11 |
| S25 | Parallel research, ClickHouse v3 read support: 26.8 LTS reads v3 metadata but fails on a Puffin DV with `BAD_ARGUMENTS "Position deletes are supported only for parquet format"` (`PositionDeleteTransform.cpp` at v26.8.13.2-lts); v3 reading predates 26.8 (PR #107377 backported to 26.3.18.25); DV read expected in 26.10 (Experimental, non-LTS, expected late Oct 2026) or 27.3 LTS (expected late March 2027) | docs/research/16-clickhouse-iceberg-v3-read.md | 2026-09-28 |
