# 09 - Technical inventory of the prior Olist repository

**Source:** `github.com/SoongGuanLeong/data_pipelines_batch_stream_vector`
**Commit inspected:** `6f371903`, the repository's HEAD at the time of the inventory.
**Clone:** shallow, depth 50, read-only. No credentials were guessed and nothing outside a scratch directory was written.
**Method:** static inspection only. No container was started, so where behaviour could not be proven from source the report says so.
**Date:** 2026-09-27.

**Provenance.** This is the working inventory that the salvage ticket ([#5](https://github.com/SoongGuanLeong/de-platform/issues/5), under map [#9](https://github.com/SoongGuanLeong/de-platform/issues/9)) treats as its evidence. It was produced during the map's charting work and originally lived only in the tool's session store, which is not durable. It is committed here verbatim apart from this header, so that the reuse decision in [ADR-0006](../adr/0006-reference-only-reuse-and-provenance.md) rests on a document a reader can open.

**One correction to the report's legal reading.** Section (i) concludes that copying the code is not permitted, because the repository carries no LICENSE file. That is true for third parties: under the Berne Convention an unlicensed public repository is all-rights-reserved, and the copyright holder is the repository's author, so the owner may reuse the code freely. The decision this repository adopts is stricter and rests on different reasoning. [ADR-0006](../adr/0006-reference-only-reuse-and-provenance.md) makes the prior repository reference-only on engineering grounds, not legal ones.

---

# Technical inventory: `SoongGuanLeong/data_pipelines_batch_stream_vector`

**Clone status: SUCCESS.** Shallow clone (`--depth 50`) into `/tmp/opencode/olist-inventory` succeeded. `gh auth status` confirms authenticated as `SoongGuanLeong` with `repo` scope; the repo is **public** (`"license": null`, 0 stars, 0 forks). No credentials were guessed and nothing outside `/tmp/opencode` was written.

Analysis is static only. No containers were started. Where I cannot prove behaviour from source, I say so explicitly.

---

## (a) What is actually there

**Totals:** 167 files / 54 dirs, 7.2 MB (6.5 MB of which is `docs/` PNGs). 34 screenshots in `docs/`.

### Directory tree (excl. `.git`)

```
.
├── .github/workflows/CI.yml
├── .gitignore                    (19 L)   .python-version (1 L)
├── Makefile                      (120 L)
├── README.md                     (93 L)
├── main.py                       (6 L — prints "Hello from data-pipelines-batch-stream-vector!")
├── pyproject.toml                (7 L)
├── configs/batch/                api.yaml(0L*) general.yaml(7) gold.yaml(63)
│                                 kafka.yaml(10) raw.yaml(27) spark_jobs.yaml(16)
├── data/raw/olist/.gitkeep       (dataset gitignored; 0 CSVs committed)
├── docs/
│   ├── architecture/{gold/,images/,legacy/,schema/}
│   │   ├── gold/scd2_implementation_strategies.md      (276 L)
│   │   ├── improvement_plan_team_lead.md              (185 L)
│   │   ├── stage_a1_file_placement_map.md              (163 L)
│   │   ├── legacy/{completion_roadmap.md(223), project_stats.md(149)}
│   │   └── schema/{original_schema.md(138), star_schema.md(154)}
│   └── operations/{connectors/,polaris/,runbooks/,spark_pipeline_checklist.md}
├── infra/
│   ├── bootstrap/  01_init_db.sh(12) 16_polaris_bootstrap.sh(247) 16_polaris_bootstrap.sh.bak(164)
│   ├── connectors/ deploy_connector.sh(47) olist-postgres-connector.json(32) update-example.json(27)
│   ├── docker/
│   │   ├── cdc_stack/docker-compose.yaml               (161 L)
│   │   ├── lakehouse_stack/docker-compose.yaml          (214 L)
│   │   ├── lakehouse_stack/spark/{Dockerfile(39), pom.xml(74), .gitignore, conf/*}
│   │   └── lakehouse_stack/trino/etc/{config,node,jvm}.properties, catalog/polaris.properties
│   ├── observability/elk/{docker-compose.yaml(62), filebeat/, logstash/}
│   └── sql/  02..14, eleven numbered .sql files (916 L total)
├── jobs/  __init__.py  batch/build_bronze.py  (160 L — TRUNCATED, see §e)
├── notebooks/batch/  17 .ipynb (6,701 L) numbered 18..33 + _utils/17_services_integration_check.ipynb
└── src/pipeline/batch/  51 .py files
    ├── common/   avro_utils, config_loader, file_utils, metadata_utils,
    │             spark_sql_magic, storage_utils, transform_utils, watermark, writers
    ├── gold/     scd2.py, helper.py, dq.py, dims/{customers,sellers,products,date},
    │             facts/{orders,order_items,order_payments,order_reviews}
    ├── monitoring/dq_metrics.py
    └── silver/   transform/ (9 modules)  dq/ (10 modules)  transform/checklist.md
```
\* `configs/batch/api.yaml` reports 0 newlines but is 1 line of content.

### Languages / line counts (this checkout, raw `wc -l`)

| ext | files | lines |
|---|---|---|
| `.py` | 54 | 2,718 |
| `.ipynb` | 17 | 6,701 |
| `.md` | 18 | 2,137 |
| `.sql` | 11 | 916 |
| `.yaml` | 9 | 569 |
| `.sh` | 3 | 309 |
| `.json` | 2 | 61 |
| `.toml` | 1 | 8 |

The owner's own `scc`-generated stats in `docs/architecture/legacy/project_stats.md` (pre-rearrangement) report: Python 47 files / 2,472 lines / 1,630 code; Jupyter 17 / 6,613; Markdown 17 / 1,610; SQL 11 / 910; YAML 11 / 623; Shell 3 / 308; Makefile 119. Total 12,695 lines. **This is a small repo — roughly 11k lines of code, of which ~44% is notebook JSON and ~21% is markdown.**

### Build / config files present

| Type | Present? | Path |
|---|---|---|
| docker-compose | **Yes ×3** | `infra/docker/cdc_stack/`, `infra/docker/lakehouse_stack/`, `infra/observability/elk/` |
| Makefile | **Yes** | `Makefile` (120 L, 18 targets) |
| pyproject.toml | **Yes but empty** | `pyproject.toml` — `dependencies = []`, `requires-python = ">=3.14"`, `description = "Add your description here"` |
| requirements.txt | **No** | — |
| pom.xml | **Yes** | `infra/docker/lakehouse_stack/spark/pom.xml` (7 runtime deps, must be `mvn`d manually) |
| `.env` / `.env.example` | **NO — ABSENT ENTIRELY** | `.gitignore` ignores `.env` and `*.env`; no example file exists. This is a hard blocker, see §e |
| Helm charts | **No** | 0 matches repo-wide |
| Terraform | **No** | 0 matches repo-wide |
| CI | Minimal | `.github/workflows/CI.yml` (50 L): `ruff check src` + `ast.parse` on `src/**/*.py`. **No tests, no build, no container, no notebooks.** |
| Pre-commit / linter config | **No** | no `ruff.toml`, no `[tool.ruff]` in pyproject, no `.pre-commit-config.yaml` |

---

## (b) Component inventory and state

| Component | State | Evidence |
|---|---|---|
| **PostgreSQL** | Present, **host-installed, not containerised.** 3 PG instances: your local OLTP, `postgres:14.21` for Apicurio, `postgres:16.11-bookworm` for Polaris. README: "Assumption: PostgreSQL is already installed and running on your local machine." | `infra/sql/02..14`, `01_init_db.sh`, compose `cdc_stack:56`, `lakehouse_stack:122` |
| **Debezium** | **Real and complete.** `quay.io/debezium/connect:3.4`, pgoutput, `ExtractNewRecordState` unwrap SMT, `delete.handling.mode=rewrite`, Avro→Apicurio. Auto-deployed by `connector-init` (alpine/curl) service. | `cdc_stack:77`, `olist-postgres-connector.json`, `deploy_connector.sh` |
| **Kafka (KRaft)** | **Real.** `apache/kafka:4.1.1`, single-node `broker,controller`, `1@kafka:9093`, rf=1. ZooKeeper **not** used. | `cdc_stack:8-28` |
| **Apicurio** | **Real.** Registry `3.1.6` + UI `3.1.6`, Postgres-backed, CORS for `:8888`. AKHQ reads it via Confluent-compat `/apis/ccompat/v7`. | `cdc_stack:33,67,142` |
| **AKHQ** | Real, `tchiotludo/akhq:0.26.0` | `cdc_stack:128` |
| **PySpark** | **Real, but version-unpinned in the wrong places.** Image `apache/spark:4.0.1-scala2.13-java21-python3-r-ubuntu`; pip line adds `pyspark==4.0.1`. **Not declared in `pyproject.toml` (`dependencies = []`).** | `spark/Dockerfile:1,27` |
| **Iceberg** | **Real.** `iceberg-spark-runtime-4.0_2.13:1.10.1` via Maven; `format-version=3`, zstd parquet, `write.target-file-size-bytes=134217728` (128 MB), `days()` hidden partitioning on bronze and `ds` on silver. | `spark/pom.xml:33-37`, notebooks 20/21/23 |
| **Polaris** | **Real and the most considered piece.** `apache/polaris:1.2.0-incubating` + `polaris-admin-tool` for schema bootstrap, relational-jdbc persistence on Postgres, RBAC (principal `spark_user` → principal-role `spark_role` → catalog-role `catalog_admin` on `learning_catalog`), full OAuth2 client-credentials flow, 247-line bootstrap script. | `lakehouse_stack:95-162`, `16_polaris_bootstrap.sh` |
| **MinIO** | **Real.** `minio/minio:RELEASE.2025-09-07T16-13-09Z-cpuv1` + `mc` sidecar that creates bucket `olist-ecommerce`. | `lakehouse_stack:11,27,46` |
| **Trino** | **Real, wired, never exercised.** `trinodb/trino:480`, Iceberg REST catalog → Polaris, `fs.native-s3.enabled=true` → MinIO. **No Trino query exists anywhere in the repo.** | `lakehouse_stack:190-205`, `trino/etc/catalog/polaris.properties` |
| **Dagster / Airflow** | **ABSENT.** Zero Dagster. "airflow" appears once, as a passing prose comment in notebook 21. Orchestration is a **Jupyter notebook** (`33_orchestration.ipynb`) using `nbclient.NotebookClient`. | grep repo-wide |
| **dbt** | **ABSENT.** 0 code matches (only 3 false positives inside PNG binaries). |
| **Prometheus / Grafana** | **ABSENT.** 0 matches. Observability is **ELK only** (`elasticsearch/kibana/logstash/filebeat` `8.19.11`), and it is very likely not actually ingesting (§e). |
| **Kubernetes / Helm / Terraform** | **ABSENT.** 0 matches. |
| **Flink** | **ABSENT.** 1 match, `README.md:10`: "realtime streaming pipeline (require flink to get ms latency)" — a plan, not code. |
| **ClickHouse** | **ABSENT.** 0 matches. |
| **Vector DB** | **ABSENT.** 0 matches for milvus/qdrant/chroma/pinecone/weaviate/pgvector. `README.md:11` lists "vector db pipeline" as a bare bullet with no link. |
| **Data quality** | **Real, home-grown, ~2 files' worth of depth.** 11 DQ modules: `silver/dq/{common_dq,customers,orders,products,sellers,order_items,order_payments,order_reviews,geolocation,product_category_name}_dq.py` + `gold/dq.py`. Metrics land in `monitoring.dq_metrics` (Iceberg, partitioned by `pipeline_stage, source_table`). **No framework** — no Great Expectations, no Soda, no dbt tests. **Metrics are recorded but never gate anything**: no threshold, no severity, no fail-fast, no alert. | `src/pipeline/batch/silver/dq/`, `monitoring/dq_metrics.py` |
| **Lineage** | **ABSENT as tooling.** "lineage" appears only in `spark_pipeline_checklist.md` and `completion_roadmap.md` as future work. `pipeline_audit` (`monitoring.pipeline_audit`) is a run log, not lineage. No OpenLineage, Marquez, DataHub, OpenMetadata. |
| **kafka-connect (sink)** | **Declared but unconfigured.** `confluentinc/cp-kafka-connect:8.1.1` in the lakehouse compose, Confluent AvroConverter → Apicurio ccompat. **No sink connector JSON exists.** README says "(attempting iceberg kafka sink connector)". | `lakehouse_stack:166-186` |
| **Iceberg Kafka sink connector** | **NOT PRESENT.** README §Batch claims the pipeline reaches MinIO "via iceberg kafka sink connector". No such connector config in the repo. The actual MinIO write path is **Spark Structured Streaming** (`readStream` → `foreachBatch`), not a Kafka sink. README is wrong here. |

---

## (c) The data pipeline paths, end to end

**Scripts: 17 notebooks + 51 `src/` modules + 1 dead job + 11 SQL + 3 shell.** The critical structural fact: **the pipeline is orchestrated by notebooks, and `src/` holds only gold + silver-transform logic.** Notebook 21's own comment: *"usually combined with scheduler/airflow to save compute"*. The owner confirms it in `docs/operations/runbooks/33_orchestration.md`: *"the logics in the notebooks are not written for production. Proper python pipeline script is to be implemented in the jobs folder after we confirm we can run the notebooks once from start to end."*

### Path 0 — OLTP bootstrap (host Postgres, `make setup-postgres`)
`Makefile:114` chains 11 targets, gated by `check-tools`, `check-sql`, `check-dataset`:
`init-db`(→`01_init_db.sh`, `CREATE DATABASE olist`) → `create-schema`(`02`, `CREATE SCHEMA oltp`) → `create-tables`(`03`, 9 tables) → `add-fks`(`04`) → `add-indexes`(`05`) → `create-staging`(`06`, 9 staging tables) → `load-staging`(`07`, `\copy` 9 Olist CSVs) → `load-tables`(`08`, INSERT…SELECT in FK order) → `create-publication`(`09`, `CREATE PUBLICATION olist_pub FOR TABLE` 7 tables) → `prep-cdc`(`10`).

OLTP tables: `oltp.{customers, sellers, products, orders, order_items, order_payments, order_reviews, product_categories, geolocations_enrichment}`.
Publication covers 7 of 9 — `product_categories` and `geolocations_enrichment` are deliberately excluded (they take the batch/lookup path instead). Good design.

### Path 1 — CDC: Postgres → Kafka → Bronze
```
oltp.* --Debezium(pgoutput, slot olist_slot)--> kafka topic olist.oltp.<table>
   --Apicurio AvroConverter--> artifact olist.oltp.<table>-value  [schema per topic]
```
- **Job A — `notebooks/batch/20_bronze_cdc_ddl.ipynb`** (`olist-bronze-cdc-ddl`): for each of 7 topics, `fetch_avro_schema()` from Apicurio → synthesise an empty DF through `from_avro` to derive the schema → `writeTo(...).tableProperty("format-version","3")` … `.partitionedBy(F.partitioning.days("spark_ingest_ts"))`. Creates `polaris.bronze.<topic>` and `polaris.bronze.<topic>_dlq`.
- **Job B — `notebooks/batch/21_bronze_cdc_ingestion.ipynb`** (`olist-bronze-cdc-ingestion-backfill`): `spark.readStream.format("kafka")` with `subscribePattern = olist.oltp\..*` (dynamic), `startingOffsets=earliest`, `checkpointLocation = s3a://olist-ecommerce/checkpoints/bronze/all_topics`, `trigger(availableNow=True)` — i.e. **micro-batch, correctly labelled as such in the README**. `foreachBatch(write_batch)` loops all 7 topics, `from_avro(..., {"mode":"PERMISSIVE"})`, splits `valid_df` / `dlq_df` (null `data`), appends to `bronze.<topic>` (`mergeSchema=true`) and `bronze.<topic>_dlq`, and writes per-partition offset audit rows to `bronze.<topic>_audit`.

Produces: `polaris.bronze.{customers,orders,products,sellers,order_items,order_payments,order_reviews}` + `_dlq` + `_audit`, partitioned `days(spark_ingest_ts)`.

### Path 2 — Raw + lookup → Bronze
- **Job C — `19_raw_ingestion.ipynb`** (`olist-raw-ingestion`): boto3 uploads `/opt/spark/data/raw/olist/*` → MinIO `s3a://olist-ecommerce/raw/<file>`, checksum-deduped via `polaris.raw.raw_ingestion_metadata` (md5, `days(upload_ts)`).
- **Job D — `22_bronze_lookup_ddl_ingestion.ipynb`** (`olist-bronze-lookup-ddl-ingestion`): reads 2 CSVs directly and `mode("overwrite").saveAsTable` → `polaris.bronze.geolocation`, `polaris.bronze.product_category_name`; idempotency via `polaris.bronze.lookup_ingestion_metadata`. Schemas declared inline in `configs/batch/raw.yaml:lookup_tables`.

### Path 3 — Bronze → Silver
- **Job E — `23_silver.ipynb`** (`olist-silver`): the biggest notebook (1,226 L).
  - `read_bronze_incremental(t)` — `WHERE spark_ingest_ts > (SELECT MAX(spark_ingest_ts) FROM silver.<t>)`.
  - `normalize_cdc` — `__op:'r'→'c'`, `__ts_ms→cdc_ts_ms`, `cdc_ts = to_timestamp(ts_ms/1000)`, `ds = to_date(cdc_ts)`.
  - `normalize_decimal_structs` — detects Avro `{scale:int, value:binary}` decimal structs, converts via `conv(hex(value),16,10)/pow(10,scale)` → `DecimalType(18,6)`. This is a genuinely non-obvious piece of work.
  - `drop_kafka_metadata` — drops `kafka_*`, retains `spark_ingest_ts`/`batch_id` as the watermark.
  - `apply_table_specific_transform` → dispatch dict `TABLE_TRANSFORMS` in `silver/transform/__init__.py` (9 entries).
  - `apply_schema_drift` — additive-only `ALTER TABLE ADD COLUMN`; raises on column removal.
  - `collect_table_dq_metrics` → `monitoring.dq_metrics`; `log_pipeline_audit` → `monitoring.pipeline_audit`.
  - CDC path: `writeTo(...).using("iceberg").tableProperty("format-version","3")…partitionedBy("ds")` then `append()` or `create()`.
  - Lookup path: `mode("overwrite")`.

Produces: `polaris.silver.{customers, orders, products, sellers, order_items, order_payments, order_reviews, geolocation, product_category_name}` — 9 tables, partitioned by `ds`.

### Path 4 — Silver → Gold (8 tables, this is the best code in the repo)
Notebooks `24`–`32`, each importing from `src/pipeline/batch/gold/`. Uniform skeleton: `get_last_commit_ts(TARGET)` (via `<table>.snapshots` metadata table) → if `None`, full rebuild + `overwrite_table`; else `get_effective_watermark(last_commit, buffer_hours=6)` → `get_changed_*_ids` → if empty, skip; else `build_incremental_*` + `replace_by_key`.

| Notebook | Produces | Grain / key |
|---|---|---|
| `24` | `gold.dim_customers_scd2` | SCD2 on `customer_id`; geo-enriched |
| `25` | `gold.dim_sellers_scd2` | SCD2 on `seller_id`; geo-enriched |
| `26` | `gold.dim_products_scd2` | SCD2 on `product_id`; EN-category joined |
| `27` | `gold.dim_date` | 2010-01-01…2049-12-31, `date_sk=yyyyMMdd` |
| `28` | *(mutates the 3 SCD2 dims)* | one-time `effective_from` backfill |
| `29` | `gold.fact_orders` | `order_id` |
| `30` | `gold.fact_order_items` | (`order_id`,`order_item_id`) |
| `31` | `gold.fact_order_payments` | (`order_id`,`payment_sequential`) |
| `32` | `gold.fact_order_reviews` | `review_id` |

**Total tables produced: 5 namespaces / ~45 tables** (raw:1, bronze: 7 CDC ×3 + 2 lookup + 1 metadata = 24, silver: 9, gold: 8, monitoring: 2).

### Path 5 — Consumption
Trino is wired and stopped there. No query, no view, no materialized view, no dashboard anywhere in the repo. `docs/architecture/legacy/completion_roadmap.md` §5–§8 plan DBeaver + Power BI + DAX; none of it exists.

### Are the scripts real or stubs?
- **Real, working-shaped:** notebooks 18–27, 29–33; all 9 silver transforms; all 10 DQ modules; all 8 gold builders; `writers.py`; `watermark.py`; `transform_utils.py`; all 11 SQL files; both debounce connector scripts; the Polaris bootstrap.
- **Stub / dead:** `jobs/batch/build_bronze.py` (truncated, see §e); `main.py` (hello-world); `.python-version`/`.env` absent.
- **Partly real:** `writers.write_table()` (`common/writers.py:133`) — the "unified entrypoint" — is **never imported by anything** and not in `common/__init__.py`'s `__all__`. The notebooks call the three primitives directly. Dead code.

---

## (d) Iceberg / Polaris specifics

**Table properties** (consistent across bronze notebook 20 and silver notebook 23):
```
format-version               = 3
write.format.default         = parquet
write.parquet.compression-codec = zstd
write.target-file-size-bytes = 134217728   (128 MB)
```
**Partitioning:**
- bronze: `F.partitioning.days("spark_ingest_ts")` — Iceberg **hidden partitioning**. This is the right choice and the notebook says why: *"iceberg hidden partitioning - we'll use this column as watermark to filter latest ingestion"*.
- silver: `PARTITIONED BY (ds)` (plain column).
- `polaris.raw.raw_ingestion_metadata`: `PARTITIONED BY (days(upload_ts))`.
- `monitoring.dq_metrics` / `monitoring.pipeline_audit`: `PARTITIONED BY (pipeline_stage, source_table)`.
- **gold: no partitioning at all.** Every `overwrite_table()` call is a flat unpartitioned Iceberg table. Defensible at Olist scale (~100k orders), indefensible as a default.

**SCD2 handling.** `src/pipeline/batch/gold/scd2.py` is 44 lines and is the cleanest module in the repo:
```python
apply_scd2(df, business_key, surrogate_key, effective_from_col="cdc_ts", tie_breaker_col="spark_ingest_ts")
  W.partitionBy(bk).orderBy(effective_from_col, tie_breaker_col)
  effective_from = cdc_ts
  effective_to   = lead(cdc_ts) over w
  is_current     = effective_to.isNull()
  <sk>           = sha2(concat_ws("||", bk, effective_from), 256)
```
`build_temporal_scd2_join_condition()` builds the fact→dim predicate `(fact.key == dim.key) & (fact_ts >= dim.effective_from) & ((fact_ts < dim.effective_to) | dim.effective_to.isNull())` — textbook, correct, and reused by all 4 fact builders.

Three design notes worth carrying forward:
1. **Surrogate key is a deterministic `sha2(bk || effective_from)`, not a sequence.** Pros: reproducible, backfill-safe, no coordination. Cons: 64-char hex, opaque, not join-order-friendly, and *invalidated* by the bootstrap backfill (§e).
2. **Version tie-break is `cdc_ts, spark_ingest_ts`** — CDC timestamp first, ingest timestamp as deterministic tiebreaker. Correct for same-millisecond collisions.
3. **The `is_current` + `effective_to` recompute is a full recompute of all versions for a changed key**, not a "close the old row / insert the new row" delta. That is Approach A (stateless selective rebuild) in `docs/architecture/gold/scd2_implementation_strategies.md` (276 L, a genuinely good design doc that also explicitly says *"Keep current stateless SCD2 … Avoid MERGE until scaling demands it"*).

**MERGE / UPSERT.** Three writers exist in `common/writers.py`:
- `overwrite_table` — `.mode("overwrite")`. Used by 24, 25, 26, 27, 29, 30, 31, 32.
- `replace_by_key(spark, df, target, key_columns)` — writes `{target}_staging_{uuid4}`, then `DELETE FROM target t WHERE EXISTS (SELECT 1 FROM staging s WHERE t.k=s.k …)` then `INSERT INTO target SELECT * FROM staging`, then `DROP` in `finally`. Composite-key aware, uuid-namespaced so concurrency-safe. **This is the workhorse and it is good.** Used by every incremental dim/fact notebook.
- `merge_into` — `MERGE INTO … WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *` against a **fixed** staging table name `{target}__staging` (no uuid). Docstring correctly warns it is stateful and non-concurrent-safe. **Currently uncalled.**
- `overwrite_partitions` — `option("overwrite-mode","dynamic")`. **Currently uncalled.**

**Compaction / snapshot expiry / orphan cleanup: COMPLETELY ABSENT.** No `rewrite_data_files`, no `rewrite_manifests`, no `expire_snapshots`, no `remove_orphan_files`, no `rewrite_position_delete_files` anywhere in the repo. `completion_roadmap.md` §6 and `improvement_plan_team_lead.md` C3 both list this as Phase-C work. The only compaction-adjacent settings are the two tuning knobs in `spark-defaults.conf` (`commit-retry-num-retries 8`, `commit-retry-total-timeout-ms 300000`).

**Schema evolution.** Two independent mechanisms, both real:
1. Iceberg `mergeSchema=true` on bronze appends (notebook 21).
2. `apply_schema_drift()` in notebook 23: set-difference incoming vs existing columns; `ALTER TABLE ADD COLUMN` for new; **raises `Exception(f"Destructive schema change detected: {missing_cols}")`** for dropped columns. Additive-only by policy.
3. `spark.sql.iceberg.schema.auto-evolution.enabled=true` (`spark-defaults.conf:47`).
4. **Verified end-to-end in the repo:** `infra/sql/14_test_schema_evolution.sql` does `ALTER TABLE oltp.customers ADD COLUMN loyalty_level` → INSERT → DELETE → `DROP COLUMN`, and `docs/operations/connectors/enable_apicurio.md` §5 documents confirming the new column appeared in Apicurio as version 2 with screenshots. This is a genuinely validated capability.

**Time travel: not used.** `get_last_commit_ts()` reads `MAX(committed_at)` from `<table>.snapshots` — the *metadata* table, not a time-travel query. There is no `VERSION AS OF`, no `TIMESTAMP AS OF`, no `snapshot-id` reference, no `branch`/`tag`, no `set_current_snapshot`. Iceberg's time-travel capability is entirely untapped.

**Polaris specifics.** Catalog `learning_catalog` (`INTERNAL`, `allowedLocations=["s3a://olist-ecommerce/"]`, `default-base-location=s3a://olist-ecommerce/`), created by `16_polaris_bootstrap.sh:127`. Spark side (`spark-defaults.conf:11-22`): `spark.sql.defaultCatalog=polaris`, `spark.sql.catalog.polaris.type=rest`, `uri=http://polaris:8181/api/catalog`, `io-impl=org.apache.iceberg.aws.s3.S3FileIO`, `rest.auth.type=oauth2`, `oauth2-server-uri=http://polaris:8181/api/catalog/v1/oauth/tokens`. Trino side (`trino/etc/catalog/polaris.properties`): identical REST/OAuth2 wiring plus `fs.native-s3.enabled=true` → MinIO. Spark and Trino are correctly pointed at the *same* catalog. Bootstrap is fully automatable and idempotent-by-intent.

---

## (e) Honest quality assessment

**Does it run? Unverifiable from static inspection** — I did not start containers, per instructions. But I can prove it *cannot* run as documented, on Linux, without manual undocumented steps. Four independent hard blockers:

### Blocker 1 — `docker compose up -d --build` fails at the Spark image build
`infra/docker/lakehouse_stack/spark/Dockerfile:29`:
```dockerfile
COPY target/jars/* /opt/spark/jars/
```
`infra/docker/lakehouse_stack/spark/target/` **does not exist** (the dir contains only `.gitignore`, `Dockerfile`, `conf/`, `pom.xml`), and `spark/.gitignore` contains exactly `/target/jars/`. The jars must be produced by a manual, undocumented `mvn -q dependency:copy-dependencies -DoutputDirectory=target/jars -DincludeScope=runtime` — the instructions exist only as a **comment block in `pom.xml:1-10`**, not in the README. README step 6 says only `docker compose up -d --build`. **This is a guaranteed first-run failure.**

### Blocker 2 — no `.env` file, and the README never mentions one
Both composes require environment variables that have no default:
- `cdc_stack`: `${APICURIO_USER}`, `${APICURIO_PASSWORD}`, `${APICURIO_DB}`
- `lakehouse_stack`: `${MINIO_ROOT_USER}`, `${MINIO_ROOT_PASSWORD}`, `${POLARIS_USER}`, `${POLARIS_PASSWORD}`, `${POLARIS_DB}`

`.gitignore` excludes `.env`/`*.env` and **no `.env.example` / `.env.template` exists anywhere** (verified by exhaustive find). Docker Compose substitutes empty strings for unset vars. The README's 8-step Quickstart never says "create a .env". **Second guaranteed failure.**

### Blocker 3 — `host.docker.internal` will not resolve on Linux
`infra/connectors/olist-postgres-connector.json:5` sets `"database.hostname": "host.docker.internal"` (Debezium runs in a container, Postgres is on the host). **Neither compose file declares `extra_hosts: - "host.docker.internal:host-gateway"`.** Docker Engine on Linux does not provide this alias by default (Docker Desktop on macOS/Windows does). Since the user's stated environment is Linux + systemd, **the connector will not resolve its database host.** Also note `update-example.json:3` uses a *comma*-separated `table.include.list` while the live connector uses *regex* `oltp\.(…)` — the two examples disagree on format.

### Blocker 4 — `04_add_FKs.sql` is not idempotent
`ALTER TABLE oltp.orders ADD CONSTRAINT fk_order_customer …` with no existence guard (contrast `05_add_indexes.sql`, which correctly uses `CREATE INDEX IF NOT EXISTS`). **A second `make setup-postgres` fails.** Separately, `08_load_tables.sql:17-31` inserts into `oltp.geolocations_enrichment` with **no `ON CONFLICT` and no primary key** while every other insert has one — re-running duplicates every geolocation row.

### Committed secrets (all in a public repo)
| Secret | Location |
|---|---|
| **PostgreSQL password `"961015"`** | `infra/connectors/olist-postgres-connector.json:8` |
| Same password, again | `infra/connectors/update-example.json:6` |
| **Polaris OAuth2 client credential** `cfb8bb63f60c4c5f:060344899beb204c98c85b4384b5ca72` | `infra/docker/lakehouse_stack/spark/conf/spark-defaults.conf:21` |
| **A second, different Polaris client credential** `2cf28f5ef53c3d37:911df0d69c81730f9dc22b4afb71e14b` | `…/spark/conf/spark-defaults.conf.bak:21` |
| MinIO creds `minioadmin:minioadmin` | `spark-defaults.conf:27-28,36-37`; `19_raw_ingestion.ipynb` cell 10 |
| Polaris bootstrap `POLARIS,admin,password123` | `lakehouse_stack:109`; `16_polaris_bootstrap.sh:17`; `TRINO_POLARIS_CREDENTIAL: admin:password123` (`lakehouse_stack:201`) |

Root cause of the credential leak is mechanical, not careless: `16_polaris_bootstrap.sh:46` does `cp "$SPARK_DEFAULTS_PATH" "${SPARK_DEFAULTS_PATH}.bak"` on every run, and `.gitignore` does not exclude `*.bak`. The script **rewrites a tracked file in place with a freshly minted secret**, so running the documented `make init-polaris` step dirties the working tree and the next `git add -A` publishes a live credential. **This is a repeatable secret-exfiltration mechanism, not a one-off mistake.** Also, `python-version "3.10"` in CI vs `requires-python = ">=3.14"` in `pyproject.toml`, and `datetime.utcnow()` (deprecated 3.12+) in notebook 23 cell 28.

### Real logic bugs (verified by reading the code)

1. **`jobs/batch/build_bronze.py` is truncated at line 160.** File ends mid-module: no `run_ingest`, no `run_lookup`, no `main()`, no `if __name__`. `parse_args()` advertises modes `ingest`/`lookup`/`all` that nothing implements. `python jobs/batch/build_bronze.py` executes literally nothing. This is the file the owner's own roadmap names as backlog item #1.
2. **`jobs/batch/build_bronze.py:145` — invalid SQL.** Inside a raw `spark.sql()` DDL string: `PARTITIONED BY (F.partitioning.days(batch_ts))`. That is a DataFrameWriterV2 API call pasted into SQL text. Copy-paste from the notebook's `.partitionedBy(...)`. Would raise a parse error on any invocation.
3. **Notebooks 30, 31, 32 are missing a `return` in the first-run branch.** Compare `24`/`25`/`26`/`29` (correct, they `return`) with `30_gold_fact_order_items` cell 8, `31_gold_fact_order_payments` cell 8, `32_gold_fact_order_reviews` cell 8: after `overwrite_table(df, TARGET_TABLE)` inside `if last_commit_ts is None:`, control **falls through** to `get_effective_watermark(None, …)` → returns `None` → `get_changed_*_ids(spark, None)` returns **all** keys → the full incremental path then runs too. First execution of these three facts does a full rebuild **and then a full incremental rebuild** over the whole table.
4. **`28_gold_dims_bootstrap.ipynb` cell 6 corrupts SCD2 history.** ```python
   F.when(F.col("effective_from") > baseline_ts, baseline_ts).otherwise(F.col("effective_from"))
   ``` clamps **every** version row to `2010-01-01`, not just the first. All Olist `cdc_ts` are 2016–2018, so **every row of `dim_customers_scd2` / `dim_sellers_scd2` / `dim_products_scd2` collapses to `effective_from = 2010-01-01`**, producing `effective_to` values of `2010-01-01` on non-final rows and multiple rows per business key sharing one `effective_from`. That is precisely the state the project's own validators flag: `validate_scd2_customers` computes `invalid_intervals` (`effective_from >= effective_to`) and `multiple_current_rows`. Those validators run in notebooks 24/25/26 — which execute *before* 28 in the orchestration list, so nothing catches it. It also silently invalidates every `customer_sk`/`seller_sk`/`product_sk`, since `sk = sha2(bk || effective_from)`.
5. **`silver/transform/order_payments.py:26-27` — dead code.** `df.dropna(subset=["order_id"])` immediately followed by `df.fillna("not_defined", subset=["order_id"])`. The `fillna` can never fire. Triple-dead: `payment_type` (the column that actually needed a default) is instead coerced to `"N/A"` three lines later.
6. **`19_raw_ingestion.ipynb` — the logged S3 path is a lie.** `upload_raw_file()` uploads to `object_key = f"{RAW_FOLDER}/{file_path.name}"` → `s3a://olist-ecommerce/raw/olist_customers_dataset.csv`, but returns/logs `get_spark_path(...)` → `s3a://olist-ecommerce/raw/csv/load_date=2026-05-03/olist_customers_dataset.csv` (see `storage_utils.py:14`). `polaris.raw.raw_ingestion_metadata.path` therefore points at a nonexistent object, and the `load_date=` partition the helper fabricates is never materialised.
7. **`23_silver.ipynb` cell 30 — `output_rows = input_rows`.** The audit row for every CDC table reports output = input without measuring output. The audit trail is untrustworthy exactly where you'd rely on it.
8. **Watermark can stall permanently.** `read_bronze_incremental` filters on `MAX(spark_ingest_ts) FROM silver.<t>`. The silver transforms **filter rows out** (e.g. `transform_orders` drops non-enum `order_status`, `transform_reviews` drops out-of-range `review_score`). If a batch's newest bronze row is dropped, the watermark never advances and that range is re-read forever. No watermark is stored outside the data table.
9. **`21_bronze_cdc_ingestion.ipynb` writes `{topic}_audit` but notebook 20 never creates it.** Only the dead `build_bronze.py:132` has `create_audit_table`. The audit tables get created implicitly by `saveAsTable`, unpartitioned and outside the declared DDL contract.
10. **`22_bronze_lookup_ddl_ingestion.ipynb` cell 12 — invalid SQL.** `spark.sql(f" FROM {full_table} ").show(5)`. Same class of error in `19_raw_ingestion.ipynb` cell 15: `spark.sql(f" FROM {table_name} ").show()`. Both are *runtime* failures in "Sanity Check" cells — the cells most likely to be run first while debugging.
11. **Namespace inconsistency in the metadata tables.** `configs/batch/raw.yaml` lists `raw_metadata_table` and `lookup_metadata_table` adjacently, but 19 writes to `polaris.raw.raw_ingestion_metadata` while 22 writes to `polaris.**bronze**.lookup_ingestion_metadata`.
12. **ELK almost certainly collects nothing.** Spark logs mount at `lakehouse_stack:88` (`../shared-logs:/opt/spark/logs`); filebeat reads `filebeat.yml:3-4` → `paths: [/logs/*.log]`. Spark writes to `$SPARK_HOME/logs/<appId>/*.log` — i.e. **subdirectories**, which a non-recursive `*.log` glob does not match. Also `logstash.conf:7-9` has an empty `filter {}` block, so raw Spark log text lands in Elasticsearch unsplit. The whole observability stack is decorative as wired.
13. **`avro_utils.fetch_avro_schema` can return `None`.** The `for` loop body handles 200 / 4xx / 5xx but has no `else`; on a 3xx or 204 the loop iterates and, on the 5th attempt, falls off the end returning `None`. `json.dumps(None)` → `"null"` → `from_avro` fails with an unreadable error. Also annotated `-> str` but returns `response.json()` (a `dict`).
14. **Missing `requests` dependency.** `avro_utils.py:1` imports `requests`; `Dockerfile:27` installs `notebook boto3 findspark pyspark PyYAML nbclient nbformat jupyter-client ipykernel` — no `requests`. PyPI metadata for `pyspark 4.0.1` confirms its hard deps are only `py4j==0.10.9.9` (+ extras). Whether the `apache/spark` base image happens to ship it is **unverifiable from static inspection**; flagging as a likely `ImportError` on a clean image.
15. **`silver/dq/__init__.py:25`** — `__all__ = ["collect_common_dq_metrics", "write_dq_metrics"]` but `write_dq_metrics` is never bound in that module's namespace. `from …silver.dq import *` would raise `AttributeError`. The notebooks sidestep it with explicit submodule imports.
16. **Gold notebooks never create `monitoring.dq_metrics`.** 23_silver creates it; 24–32 call `write_dq_metrics(…, "monitoring.dq_metrics")` and depend on that side effect. Undeclared cross-notebook ordering dependency (it happens to hold, since 23 precedes 24).

### Repo hygiene

- **No `TODO`/`FIXME`/`XXX`/`HACK` anywhere** (grepped all code + docs). The repo's incompleteness is invisible to a grep — you have to read it.
- **Zero tests.** No `tests/`, no `test_*.py`, no `conftest.py`, no fixtures. CI is lint + AST-parse only. 2,718 lines of PySpark transformation logic with no test coverage at all.
- **CI is thin and version-fragile.** `.github/workflows/CI.yml` runs `pip install ruff` (**unpinned**) then `ruff check src` + an `ast.parse` loop. It **only covers `src/`** — notebooks, `jobs/`, and `infra/` are entirely unchecked, which is why bugs 1, 2, 10, and 15 went unnoticed. Verified: `ruff check src --isolated --select E4,E7,E9,F` (ruff's documented default) → *"All checks passed"*, and all 5 most recent GitHub Actions runs report `success`. But the repo ships **no `[tool.ruff]` config**, so the effective rule set is whatever ruff defaults to that month — bare `ruff check src --isolated` on ruff 0.16.9 reports **54 errors** (40×`I001`, 5×`RUF022`, plus `UP006`/`RUF010`/`BLE001`/`RET501`/`PLR1711`). `ruff check src --select ALL` → **618 findings**. The green buildmark is an artifact of an unpinned tool, not a real quality gate.
- **3 committed `.bak`/leftover files:** `infra/bootstrap/16_polaris_bootstrap.sh.bak`, `spark/conf/spark-defaults.conf.bak`, `spark/.gitignore`.
- **Committed secrets, hardcoded absolute paths, dead code** as enumerated above. `config_loader.load_config()` defaults `folder="/opt/project/configs/batch"` — a container-only path, so `src/` is not importable outside the Spark container without passing an argument.
- **Docs are LLM-flavoured and partly stale.** `docs/operations/spark_pipeline_checklist.md` is a generic 15-section template that ends mid-voice with *"If you want, next step: I'll convert this into a 'project structure template'…"* — an unedited assistant response committed as documentation. `docs/architecture/improvement_plan_team_lead.md` and `docs/architecture/legacy/completion_roadmap.md` are candid AI code reviews, both largely accurate. `stage_a1_file_placement_map.md` has a heading `## 2) Exact mapping from current repo` with **no content** before jumping to `## 2.1`. Runbook 12's link to `../connectors/12_deploy.sh` is dead. `docs/operations/polaris/polaris_setup_101.md` links to `../../scripts/16_polaris_bootstrap.sh` and `../docker/17_minio_spark_iceberg_polaris/spark/conf/spark-defaults.conf` — both pre-rearrangement paths that no longer exist. Runbook `11` and `12` use Windows backslash paths (`../../../infra\docker\…`) that won't resolve on Linux. The Postman collection link in `polaris_setup_101.md` is malformed (`https://.postman.co/workspace/…` — missing the user segment) and dead. `33_orchestration.md`'s H1 is a copy-paste of `17_test_minio_spark_iceberg_polaris.md`.
- **README self-contradiction on tooling.** `README.md:6`: *"developed entirely with free tools—**no Claude, no Cursor**—only ChatGPT Free"*. Git log: *"update repo to let codex check"*, *"update repo to feed into codex"*, *"update to let codex check progress"* (commits `4e920de`, `e75d7ce`, `64edf3b`, `ab8decb`), and PR #1 is from branch `codex/task-title`. Codex (OpenAI) was clearly used. The claim is stale at best.
- **`main.py` is a `uv init` hello-world** that prints the package name. The whole `pyproject.toml` is `uv init` boilerplate with `dependencies = []` and `description = "Add your description here"`.

**Net read:** the *design thinking* is well above the repo's *engineering maturity*, and the owner knows it — `improvement_plan_team_lead.md` says so in plain terms: *"The biggest gap is engineering maturity (repeatability, testability, and operational robustness), not conceptual understanding."* The gold layer's incremental impact-propagation logic in `facts/order_items.py:127-189` (union of impacted orders from direct order changes ∪ customer-dimension ripple ∪ product changes ∪ seller changes, then narrow the dimension filters to only the impacted keys) is genuinely thoughtful work that most portfolio projects do not have. The gaps are mechanical: no tests, notebook-as-orchestrator, no `.env`, no maintenance jobs, committed secrets.

---

## (f) Reusable asset inventory

**Salvage as-is or near-as-is:**

| Asset | Path | Why keep it |
|---|---|---|
| CDC stack compose | `infra/docker/cdc_stack/docker-compose.yaml` | Debezium 3.4 + Kafka 4.1.1 KRaft + Apicurio 3.1.6 + AKHQ, all correctly cross-wired, correct single-node rf/ISR settings, auto-deploys the connector via alpine/curl. Genuinely hard to get right and clearly got right. |
| Lakehouse stack compose | `infra/docker/lakehouse_stack/docker-compose.yaml` | MinIO + Spark + Polaris + Polaris-Postgres + Trino + kafka-connect, correct `depends_on: service_healthy`, external `data-pipeline-net`, `mc` bucket bootstrap. Structure is sound. |
| Trino Polaris catalog | `…/trino/etc/catalog/polaris.properties` | 15 lines that correctly point Trino at Polaris over OAuth2 and at MinIO over native-S3. Copy this pattern. |
| Spark catalog config | `…/spark/conf/spark-defaults.conf` | The Polaris REST + OAuth2 + `S3FileIO` + MinIO triple, plus `schema.auto-evolution`, AQE, and Iceberg commit-retry settings. Genuinely useful reference; **strip the credential on line 21 first.** |
| Polaris bootstrap script | `infra/bootstrap/16_polaris_bootstrap.sh` | 247 lines of real RBAC + OAuth2 client-credentials automation against the Management API, with a multi-shape jq fallback for the credentials response and credential sync into Spark config. The most valuable single script here. |
| Iceberg JAR pom | `…/spark/pom.xml` | The 7-dependency, Spark-4-compatible Iceberg/S3/Avro/Postgres runtime set, with version-coordination comments. Correct pins. |
| **SCD2 core** | `src/pipeline/batch/gold/scd2.py` | 44 lines, two functions, textbook-correct `lead()` interval construction with a deterministic tiebreaker and a reusable temporal-join predicate. Highest code-quality-to-size ratio in the repo. |
| **`replace_by_key` writer** | `common/writers.py:27-71` | uuid-namespaced staging table, composite-key-aware `DELETE … WHERE EXISTS` + `INSERT`, `finally: DROP`. Concurrency-safe and correct. This is the pattern to standardise on. |
| **Incremental impact propagation** | `gold/facts/{orders,order_items,order_payments,order_reviews}.py` (`*_incremental`) | The changed-key → impacted-orders → impacted-items → narrowed-dimension-filters cascade, with the non-obvious fix at `orders.py:91-95` (*"Without this, an updated order for an unchanged customer can produce null customer_sk"*). This is the hardest logic in the repo and it is right. |
| Silver transform toolkit | `common/transform_utils.py` (72 L) | `flatten_structs`, `normalize_column_names`, `remove_control_characters`, `convert_accents` (Portuguese-aware translate for the Olist data) — small, dependency-free, immediately reusable. |
| Avro decimal normaliser | `23_silver.ipynb` cell 12 | Schema-introspecting `{scale:int, value:binary}` → `DecimalType(18,6)` conversion. Solves a genuinely annoying Avro/Spark problem; promote to `src/` as you lift it. |
| Schema-drift guard | `23_silver.ipynb` cell 20 | Additive-only `ALTER TABLE ADD COLUMN` with hard failure on column removal. 25 lines, right policy, reusable. |
| Incremental reader | `23_silver.ipynb` cell 8 | `spark_ingest_ts` watermark vs `MAX()` in the target. Correct pattern (fix the stall edge case from §e-8). |
| Iceberg table-property baseline | notebooks 20 & 23 | `format-version=3` + zstd + 128 MB target files + `days()` hidden partitioning, stated once and applied consistently. Copy verbatim. |
| OLTP DDL + staging + load | `infra/sql/02`–`08` | 916 lines of real, working Postgres bootstrap: staging schema, FK-ordered load, `ON CONFLICT DO NOTHING`, CDC-targeted indexes, publication. Reusable as a template. |
| Debezium connector config | `infra/connectors/olist-postgres-connector.json` | Correct pgoutput + `ExtractNewRecordState` + Avro/Apicurio converter set. **Replace the password and the hostname field.** |
| Silver DQ modules | `src/pipeline/batch/silver/dq/` (10 files) | Consistent metric-collector convention; `common_dq.py` (cdc_op enum, ts nulls, future-dating, batch_id nulls) is a decent baseline. |
| SCD2 strategy doc | `docs/architecture/gold/scd2_implementation_strategies.md` | 276 L, genuinely good design doc: stateless-recompute vs stateful-MERGE, COW vs MOR, an honest recommendation with a migration path. Keep. |
| Star schema + gold rules | `docs/architecture/schema/star_schema.md` | "Grain First", "Safe Join Rule", "Metric Integrity Rule" — a good modelling checklist, plus a mermaid ERD that matches the code. |
| PySpark CI gate skeleton | `.github/workflows/CI.yml` | Correct minimal shape. **Extend the path from `src` to `src jobs notebooks` and pin `ruff`.** |

**Salvage-then-rewrite:** notebook 33 orchestration (the concept is right, the mechanism — `nbclient` running notebooks with relative paths and no retry/timeout/artifacts — is not a scheduler).

**Do not salvage:** `main.py`, `jobs/batch/build_bronze.py` (truncated + invalid SQL), `docs/operations/spark_pipeline_checklist.md`, `docs/architecture/legacy/project_stats.md` (stale snapshot), all three `.bak` files, `ELK` compose (misconfigured globs, empty filter).

---

## (g) Gaps — what a modern lakehouse platform needs that is simply absent

**Orchestration & code-first**
- No production orchestrator (Airflow/Dagster/Prefect). Notebook 33 is a `for` loop over `nbclient`.
- No CLI entrypoints for silver or gold (only the truncated bronze attempt). No `--since`/`--run-id`/`--dry-run` arguments anywhere.
- No job-level retry, alerting, or run registry. `monitoring.pipeline_audit` is written by notebook code, not by a scheduler.

**Testing & contracts**
- Zero tests. No unit, integration, contract, or fixture tests. Nothing asserts a single table's contents.
- No data contracts. DQ is metric-collection only — **no thresholds, no severity levels, no fail-fast**. `improvement_plan_team_lead.md` B2 names this exact gap.
- No schema registry integration for the *lakehouse* side (Apicurio governs Kafka only; Iceberg schemas are unmanaged).

**Lakehouse operations**
- **Zero Iceberg maintenance.** No `rewrite_data_files`, `rewrite_manifests`, `expire_snapshots`, `remove_orphan_files`, `rewrite_position_delete_files`. Snapshots and small files will accumulate without limit. Both roadmaps flag it; nothing was built.
- No branching/tagging, no schema-history policy, no table-level `sorting`/clustering, no partition evolution strategy.
- No backfill tooling, no replay capability, no rollback path for a bad gold write.
- No row counts or watermark-lag monitoring; no freshness SLA enforcement.

**Consumption & BI**
- Zero Trino queries, views, or materialized views. Trino is deployed and entirely unused.
- No semantic/metric layer (no dbt, no MetricFlow). No GMV/AOV/conversion/delivery-lead-time definitions. No dashboard.
- No BI connection docs or query SLOs.

**Governance, security, lineage**
- No lineage tooling (OpenLineage/Marquez/DataHub/OpenMetadata all absent).
- No access-control model beyond Polaris's single `catalog_admin` grant to one principal. No namespace-level isolation, no per-team roles, no ownership.
- No secrets management — plaintext in git (§e), no external secret store, no rotation.
- No PII classification, no masking, no audit of who read what.
- No Kubernetes/Helm/Terraform — no reproducible environment beyond one developer's laptop.

**Platform & scale**
- No Spark on a cluster — everything is single-container `local` mode. No `spark-submit`, no executor sizing, no dynamic allocation.
- No backpressure/concurrency controls on the `foreachBatch` writer beyond a single `availableNow` trigger.
- No cost/perf instrumentation, no file-size KPIs, no query-latency baselines.
- **2 of the 3 advertised pipeline types do not exist**: no streaming/Flink, no vector DB. Only the batch path is built.

**Engineering basics**
- No `.env.example`, no pinned dependency manifest (`pyproject.toml` is empty; the real dep list lives in a `pip` line inside a Dockerfile).
- No pre-commit hooks, no formatter config, no type checking (the roadmap asks for mypy; nothing configured).
- No CONTRIBUTING, no ADR/decision-record system, no docs index (`docs/00_index.md` is a backlog item).
- No CI/CD beyond a lint job. No image publishing, no environment promotion (`dev`/`test`/`prod-local` are roadmap items).
- Python version incoherence: `pyproject` says `>=3.14`, CI uses `3.10`, `.python-version` is a 1-line value, container installs whatever `python3` the Spark image ships.

---

## (h) Git history signals

| Metric | Value |
|---|---|
| Total commits | **166** (verified via GitHub API `Link: …page=166; rel="last"`) |
| First commit | `51a7d72a` — **2025-10-23T16:35:57Z**, "Initial commit" |
| Last commit | `6f371903` — **2026-05-03T12:26:43Z**, "last commit before we try sth new in another repo as copy" |
| Date range | **~6.3 months**, 2025-10-23 → 2026-05-03 |
| Repo created | 2025-10-23T15:47:20Z |
| Branches | 1 (`main`) |
| PRs | 1 — #1 *"Add Stage A1 file placement map and repo improvement plan docs"*, opened + merged 2026-04-13 in 36 minutes |
| Tags / Releases | **0 / 0** |
| Stars / forks / watchers | 0 / 0 / 0 |
| Open issues | 0 |
| License (API field) | **`null`** |

**Commits per month** — this is the key signal:

```
2025-10   4     (scaffold)
2025-11   0     (abandoned month)
2025-12  26
2026-01  25
2026-02  20
2026-03  53     ← peak
2026-04  37
2026-05   1     ← "we try sth new in another repo as copy"
```

**Verdict: real, sustained iteration — not a single burst.** 162 commits across five consecutive months averaging ~30/month, with a clear build order visible in the messages: `postgres working` (2026-04-13) → `automated the part where we have to manually copy and key the polaris credentials into spark-defaults.conf` (2026-04-04) → `tested code until notebook 28` (2026-03-30) → `finished gold pipeline, attempting to add trino + dbeaver + powerBI` (2026-04-04) → the 2026-04-13/14 "rearranging files" series → `rearranging files done. Now notebook 33 can run (Gold tables are ready)` (2026-04-15).

**Institutional knowledge: moderate and recoverable from docs, absent from code.** The reasoning is captured — `scd2_implementation_strategies.md`, `improvement_plan_team_lead.md`, `completion_roadmap.md`, the `enable_apicurio.md` schema-evolution walkthrough with screenshots, the 34 `docs/` images, and the per-step runbooks. Two independent, accurate self-reviews exist. But the *hard-won debugging knowledge is in the notebooks, not in the module docstrings* — `spark-defaults.conf:73` says only *"these are added by gpt during debugging"* and the notebooks' markdown cells carry the rationale. There is no decision log, so the "why" behind the version pins (Spark 4.0.1 / Iceberg 1.10.1 / Trino 480 / Polaris 1.2.0-incubating) is not recorded anywhere. The last commit explicitly announces the project is being forked: *"last commit before we try sth new in another repo as copy"* — so the author has already decided to start fresh, and has left this as a reference copy.

---

## (i) License

**There is no LICENSE file.** Verified two ways:
- `gh api …/contents` returns exactly: `.github`, `.gitignore`, `.python-version`, `Makefile`, `README.md`, `configs`, `data`, `docs`, `infra`, `jobs`, `main.py`, `notebooks`, `pyproject.toml`, `src`. No `LICENSE`, no `COPYING`.
- GitHub API repo metadata: `"license": null`. The repo has **no detected license**.
- No license header in any source file. `pyproject.toml` (7 lines) has **no `license` field** and no `license-files` entry.

**Legal status: all rights reserved by default.** Under the Berne Convention, an unlicensed public repository is proprietary — the author retains exclusive copyright, and nobody (including you) may legally copy, modify, or redistribute the code. `README.md:6` asserts *"This project is fully open source"*, but **the README's claim is not backed by any license text.** That claim is currently unenforceable.

**Practical impact for the reuse decision:**
- **Reading** the repo for reference is fine.
- **Copying code into a new project is not** — not the compose files, not `scd2.py`, not `writers.py`, not the SQL, not the Polaris bootstrap.
- The Olist source CSVs are separately licensed (Kaggle, Olist, typically CC BY-NC-SA 4.0), so the *data* has its own non-commercial restriction independent of this repo.

**One-line fix to unblock everything:** the owner adds a LICENSE file (MIT/Apache-2.0 for maximum reuse, or MPL-2.0 if they want copyleft on modifications) and a `license = "…"` field in `pyproject.toml`. Until then, treat every line of this report's §f as "read and reimplement from understanding," not "lift."

---

## Bottom line for the reuse-vs-rewrite call

**The infrastructure wiring is the reusable asset, and it needs less repair than it looks.** The compose topology, the Polaris bootstrap script, the Trino catalog config, and the Iceberg property baseline are all structurally correct and would survive a port with modest edits (add `.env.example`, pin `mvn` in a Makefile target, add `extra_hosts`, strip secrets). The SCD2 core, the `replace_by_key` writer, and the incremental impact-propagation logic in `gold/facts/` are good enough to port nearly verbatim.

**But the project is architecturally a notebook, and that is the finding that matters.** ~44% of the lines are notebook JSON; the silver ingest/transform/drift/DQ/audit logic — roughly 350 lines of the pipeline's real behaviour — lives in `23_silver.ipynb` cells, not in any importable module. `src/` contains gold and silver-*transforms* only. There are no tests at all, so "it works" rests entirely on 34 screenshots and the author's word. The last commit is the author saying they intend to start over.

So: **salvage the infra and the gold-layer algorithms, rewrite the orchestration and the test suite from scratch, and get a license before lifting a single line.**
