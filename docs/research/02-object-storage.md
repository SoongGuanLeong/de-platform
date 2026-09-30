# 02 - Object storage: what replaces MinIO as the S3-compatible data plane

**Angle:** hard-blocker resolution - the object storage layer of a vendor-neutral lakehouse
**Target role:** Senior Data Engineer - Data Lakehouse (ONL Biz Solutions Sdn Bhd, Cheras KL; JD cached at `career-ops/data/jd-cache/031.md`)
**Research date:** 2026-09-27
**Binding constraint (measured, not assumed):** 12 CPU, 14 GB total RAM (~7-8 GB free once desktop apps are counted), 231 GB disk, podman 5.7, no Docker, no kubectl/helm/terraform.
**Method:** every claim below is taken from a primary source - the GitHub REST API against the project's own repository (release pages, tags, commit dates, contributor distribution, in-repo documentation, in-repo test lists), the OCI/Docker registry v2 API against the published image, the project's own docs site, or a first-party integration guide published by the *consuming* project. Where a widely-repeated secondary claim turned out to be wrong, I say so and give the primary evidence. Where I could not verify, I say that too.

---

## 0. TL;DR

| | Verdict |
|---|---|
| **Primary** | **SeaweedFS 4.47** in `weed mini` single-process mode, with its built-in Apache-2.0 Iceberg REST catalog used as the *dev-time* catalog |
| **Fallback** | **RustFS 1.0.0** - best S3 conformance evidence of any candidate, and the only one that can read a MinIO drive set in place |
| **Runway** | Cloudflare R2 / Backblaze B2 free tier for CI and for the "real S3" leg of the migration demo |
| **Tests only** | `moto` or Adobe `S3Mock` - never LocalStack, which is now archived |
| **Failed on footprint** | **Ceph** (~28 GB documented minimum RAM), **Apache Ozone** (1.7 TB documented production minimum RAM) |
| **Failed on S3 fidelity for Iceberg** | **Apache Ozone** (no conditional requests at all, no versioning), **Garage** (no bucket policies, no versioning, no SSE, no object lock) |

**The two facts that decided it:**

1. **The Iceberg REST catalog is in SeaweedFS's free core and is guarded by CI; in RustFS it is marked Preview with Spark unverified.** SeaweedFS's `weed/s3api/iceberg/server.go` registers the full REST surface *including* `POST /v1/transactions/commit` (multi-table transaction), views, rename, and OAuth token vending, all under Apache-2.0, gated by `.github/workflows/s3-tables-tests.yml` and `s3-spark-tests.yml`. RustFS's own `docs/architecture/s3-tables-support-matrix.md` says: `Spark Iceberg REST catalog | Manual/live harness | ... Live execution and commit-conflict probing remain manual unless enabled in the runner`, and `Multi-table transactions | Not claimed`. Since the JD's stack is *Iceberg + Flink + Spark + ClickHouse*, that asymmetry is decisive.
2. **ClickHouse publishes a first-party SeaweedFS catalog guide, and nothing first-party for the others.** `clickhouse.com/docs/guides/use-cases/data-warehousing/seaweedfs-catalog` is a complete, versioned recipe (`DataLakeCatalog` engine, `catalog_type='rest'`, `IcebergS3` write path, ClickHouse >= 26.8, SeaweedFS >= 4.42). RustFS has nothing. Ozone appears only as a line in its own "compatible applications" list.

**What we lose by not having MinIO:** `mc` (no equivalent worth using in SeaweedFS), continuous bitrot detection by default (SeaweedFS gates EC bitrot scrub behind Enterprise), self-healing and automatic EC repair (Enterprise), zstd compression (OSS is gzip-only, so 10-30% more disk), and a polished console. Detail in §8.

---

## 1. The blocker, confirmed with dates

| Fact | Evidence |
|---|---|
| `github.com/minio/minio` is **archived** | GitHub API `archived: true`; last push **2026-04-24T17:54:39Z**; last release `RELEASE.2025-10-15T17-29-55Z` (published 2025-10-16) |
| `github.com/minio/mc` is **archived** | `archived: true`; last push **2025-11-20T03:07:53Z** |
| **The Docker image is gone, not just deprecated** | `GET https://registry-1.docker.io/v2/minio/minio/tags/list` with a valid pull-scoped token returns `HTTP 401 {"errors":[{"code":"UNAUTHORIZED", ... "Name":"minio/minio","Action":"pull"}]}` and **zero tags**. Control: `chrislusf/seaweedfs` with the same method returns `HTTP 200`. |
| A rival project says so in its own words | `seaweedfs/seaweedfs` README: *"as Apr 25, 2026 MinIO ceased development. It's strongly discouraged to use that unmaintained software with multiple security bugs."* |

That last row matters more than it looks: **the leading indicator of MinIO's death was the image disappearing, not the archive flag.** The archive flag was set on 25 April 2026; the images were already unpullable months earlier. Any monitoring we build should watch the registry, not the README (§10).

---

## 2. The acceptance test: what does Iceberg's `S3FileIO` actually require?

Before ranking anything I derived the requirement set from the Iceberg source rather than from folklore, because two folklore claims in circulation are wrong.

**Confirmed required, from `iceberg-aws` docs and `S3FileIOProperties.java`:**

| Requirement | Where it comes from |
|---|---|
| **Progressive multipart upload** - `CreateMultipartUpload` / `UploadPart` / `CompleteMultipartUpload` / `AbortMultipartUpload`, 32 MB parts, 1.5x threshold, parts deleted as each completes | `site/docs/aws.md` -> "Progressive Multipart Upload", `s3.multipart.part-size-bytes` default `32MB` |
| **Range reads** | Parquet footer + column-chunk reads |
| **`ListObjectsV2`** with prefix / delimiter / continuation-token | manifest and metadata-file listing |
| **`HeadObject`** | file existence + size + ETag for every data file |
| **Bulk `DeleteObjects`** | orphan-file cleanup; gated by `s3.delete-enabled` / `s3.delete.batch-size` |
| **`CopyObject`** | compaction rewrites |
| **Presigned URLs** (recommended) | engine-to-engine data transfer |
| **SSE** (optional) | `s3.sse.type` = `none` / `s3` / `kms` / `dsse-kms` / `custom` |

**Two corrections to widely-repeated claims:**

- **"Iceberg needs object versioning" - FALSE.** Iceberg implements snapshot isolation in the table metadata; `S3FileIO` never reads an S3 version id. `S3FileIOProperties.java` has no versioning property. Versioning matters for a *governance and retention* story, not for Iceberg correctness. (A secondary source asserting otherwise is cited and refuted in §11.)
- **"Iceberg needs conditional writes on `metadata.json`" - FALSE for the S3 data path.** A full-codebase search of `apache/iceberg` for `IfNoneMatch` returns only test/mock files (`TestObjectStoreUtil`, `MockS3Client`, `TestExceptionCode`, `RESTCatalogAdapter`). Optimistic commit lives in the *catalog* - `HadoopCatalog`/`JdbcCatalog` in a database, `RESTCatalog` via `requirements`/`assert-ref-snapshot-id` against the catalog server. So a non-REST catalog (Polaris, or a JDBC catalog) does not need the object store to do CAS at all. **What this changes:** conditional-write support moves from "table stakes" to "nice to have", and it removes Ozone's single most damning gap from being fatal for the *data* path. It does not save Ozone, because Ozone also lacks versioning, bucket policies, and CORS - see §3.4.

**Iceberg addressing configuration, verified in source** (`S3FileIOProperties.java`, lines 233-240, 1015):

```
s3.path-style-access   default FALSE   -> must be set true for any on-prem S3
s3.endpoint                             -> per-client endpoint
s3.access-key-id / s3.secret-access-key / s3.session-token
```

This is the whole of the "does it need per-client endpoint configuration" question: **yes, and it is one catalog property per engine.** That is also the entire migration mechanism (§9).

---

## 3. The candidates

### 3.1 SeaweedFS - **recommended primary**

**Governance and licence.** Apache-2.0, verified on `master`. **No CLA.** But also: **no `GOVERNANCE.md`, no `CONTRIBUTING.md`, no `MAINTAINERS.md`** (all three return 404 from the contents API). The only governance artifact is a stock Contributor Covenant `CODE_OF_CONDUCT.md`. Self-described as *"an independent Apache-licensed open source project with its ongoing development made possible entirely thanks to the support of these awesome backers"* - Patreon, plus a commercial edition (§3.1.8).

**Maintenance.** 35,001 stars, 3,010 forks, 774 open issues, last push 2026-09-27T00:53:31Z. Repo created **2014-07-14** - it predates most of the field.

**Releases - the strongest cadence in the field:**

| Tag | Published |
|---|---|
| 4.47 | 2026-09-14 |
| 4.46 | 2026-09-08 |
| 4.45 | 2026-08-31 |

Weekly-to-fortnightly, always a clean `x.y` with no prerelease suffix.

**Activity.** **353 commits in the 30 days to 2026-09-27.**

**Concentration - the real weakness.** 15,284 commits on `master`, **397 contributors** on the full list. Over the top-100 contributor page (14,049 contributions):

```
chrislusf          10,514   74.8%
dependabot[bot]     1,608
kmlebedev             391
chrisluuber           104
plisandro             101
top-5 share: 90.5%    top-10 share: 92.3%
```

**Bus factor 1.** There is no governance document to distribute it. Say this out loud in the write-up rather than burying it.

#### 3.1.1 S3 API fidelity

Primary source: the project's own wiki, `raw.githubusercontent.com/wiki/seaweedfs/seaweedfs/Amazon-S3-API.md` (252 lines, fetched 2026-09-27), using official AWS operation names. Counted: **86 "Yes", 33 "No".**

Everything `S3FileIO` needs is **Yes**:

| Operation group | Status |
|---|---|
| CreateBucket / DeleteBucket / HeadBucket / ListBuckets | Yes |
| GetBucketVersioning / **PutBucketVersioning** / **ListObjectVersions** | **Yes** (see [S3 Object Versioning]) |
| GetObject - *"Supports range requests, conditional headers, SSE, user metadata"* | Yes |
| **PutObject - *"Supports SSE, user metadata, conditional headers"*`** | Yes |
| Get/Put/DeleteObjectTagging, Get/Put/DeleteBucketTagging | Yes |
| **All six multipart operations** + `UploadPartCopy` | Yes |
| DeleteObjects (bulk) | Yes |
| CopyObject - *"Supports version ID, encryption, metadata directive"* | Yes |
| **Get/PutBucketPolicy** | Yes |
| Get/Put/DeleteBucketCors | Yes |
| Get/Put/DeleteBucketEncryption | Yes |
| Get/Put/DeleteBucketOwnershipControls | Yes |
| GetBucketLocation | Yes, *"Returns default location"* |
| Object Lock (retention + legal hold) | Yes |
| Presigned URLs, browser POST uploads, checksums | Yes |
| **"Conditional Headers (All operations)"** | **Yes** |
| **"Object Versioning"** | **Yes** |

The 33 "No" rows are all irrelevant to Iceberg: `ListDirectoryBuckets` (S3 Express One Zone), the analytics/inventory/intelligent-tiering/metrics/accelerate families, `PutBucketLogging`, `Get/PutBucketNotificationConfiguration`, bucket replication, bucket website, `GetObjectTorrent`, `RestoreObject`, `SelectObjectContent`, `WriteGetObjectResponse` (Object Lambda). Two notes: `PutBucketLifecycleConfiguration` is **"Transition rules not supported"**, and `GetBucketLocation` returning a fixed default is a known friction point with `s3-accelerate`-style SDK paths.

Source-code corroboration from `weed/s3api/` (200+ files): `s3api_object_handlers_multipart.go`, `filer_multipart.go`, `s3api_object_versioning.go`, `s3api_version_id.go`, `s3api_object_handlers_conditional_read_test.go`, `s3api_object_handlers_put.go` (a `validateConditionalHeaders` helper implementing the RFC 7232 precedence order If-Match -> If-Unmodified-Since -> If-None-Match -> If-Modified-Since, returning `s3err.ErrPreconditionFailed`), `s3_object_lock_*`, `s3_sse_s3.go` / `s3_sse_kms.go` / `s3_sse_c.go`, `s3api_embedded_iam.go` / `s3api_embedded_iam_oidc.go`, `s3api_sts*.go`.

`s3api_bucket_config_stubs.go` confirms the "No" list: the Analytics, Inventory, Intelligent-Tiering and Metrics config handlers are `NoSuchBucket`-only stubs. **None of these affect Iceberg.**

**CI enforcement - the part that actually matters.** `.github/workflows/` contains 80 workflows. The load-bearing ones:

- **`s3tests.yml` is literally titled `"Ceph S3 tests"`** and triggers on any change under `weed/s3api/**`, `weed/filer/**`, `weed/server/**`, `weed/iam/**`. SeaweedFS runs **Ceph's own `s3tests` conformance suite** against itself, in the default gate, on every change.
- `s3-spark-tests.yml` - `"S3 Spark Integration Tests"`, "S3 Spark Issue Reproduction Tests", 45-minute timeout
- `spark-integration-tests.yml`
- `s3-tables-tests.yml`, `s3-parquet-tests.yml`, `s3-snowflake-tests.yml`
- `s3-iam-tests.yml`, `s3-policy-tests.yml`, `s3-sse-tests.yml`, `s3-etag-acl-tests.yml`, `s3-keycloak-tests.yml`, `s3-proxy-signature-tests.yml`, `tls-rotation-tests.yml`
- `s3-mutation-regression-tests.yml`, `ec-integration-tests.yml`, `kms-tests.yml`, `java_integration_tests.yml`, `kafka-tests.yml`, `helm_ci.yml`, `terraform_ci.yml`

The README's claim - *"The S3 compatibility suite and the SDK, IAM, SSE, policy, and Spark integration tests run in CI on every change"* - is verifiable from the workflow list. That is a stronger guarantee than either RustFS or Ozone offers on the Iceberg path.

#### 3.1.2 Iceberg integration - the decisive advantage

**A complete Iceberg REST catalog is in the Apache-2.0 core, not behind a licence key.** `weed/s3api/iceberg/server.go` `RegisterRoutes()` registers, on both `/v1/...` and `/v1/{prefix}/...`:

```
GET    /v1/config
POST   /v1/oauth/tokens                                  <- OAuth2 token + exchange
GET|POST          /v1/namespaces
GET|HEAD|DELETE   /v1/namespaces/{namespace}
POST              /v1/namespaces/{namespace}/properties
GET|POST          /v1/namespaces/{namespace}/tables
POST              /v1/namespaces/{namespace}/register
GET|HEAD|DELETE   /v1/namespaces/{namespace}/tables/{table}
POST              /v1/namespaces/{namespace}/tables/{table}         <- commit (CAS, with retry)
POST              /v1/tables/rename
  ... views CRUD + /v1/views/rename
POST   /v1/namespaces/{namespace}/tables/{table}/metrics           <- ReportMetrics
POST   /v1/transactions/commit                                     <- MULTI-TABLE TRANSACTION
```

Compare RustFS, which states `Multi-table transactions | Not claimed`. SeaweedFS ships the harder thing.

`handlers_commit.go` shows a real CAS loop: on conflict it cleans up the orphaned metadata file and retries (`"CommitTable conflict for %s (attempt %d/%d), retrying"`, with a `maxCommitAttempts` bound). That is optimistic-concurrency behaviour, not last-write-wins.

`handlers_oauth.go` implements the OAuth2 token endpoint plus token exchange; `s3api_iceberg_credentials.go` implements `VendTableCredentials` scoped to **one table's prefix**, driven by `SetIcebergCredentialRole` and **disabled until an operator sets it** - the right default.

A **Lance** namespace (`weed/s3api/lance/storage.go`, `design-lance-catalog.md`) sits alongside it. Not needed for us; worth knowing it exists, because it explains where the maintainer's incentive is pointed.

#### 3.1.3 Spark, Flink, ClickHouse

- **ClickHouse - first-party integration guide, the only one of its kind.** `clickhouse.com/docs/guides/use-cases/data-warehousing/seaweedfs-catalog`. Requirements: **SeaweedFS >= 4.42, ClickHouse >= 26.8** (26.4-26.7 read and insert but cannot create through the catalog; < 26.4 writes files without registering them - the guide says so explicitly). It uses `ENGINE = DataLakeCatalog('http://seaweedfs:8181/v1', ...)` with `catalog_type = 'rest'`, `warehouse = 's3://analytics'`, `storage_endpoint = 'http://seaweedfs:8333/analytics'`, and `oauth_server_uri = 'http://seaweedfs:8181/v1/oauth/tokens'`. Writes go through `IcebergS3(...)`. Two operational gotchas the guide documents and we must honour: `allow_experimental_database_iceberg = 1` plus `allow_experimental_insert_into_iceberg = 1` plus `write_full_path_in_iceberg_metadata = 1`; and **namespaced tables need backticks** because ClickHouse does not support more than one namespace. The guide also documents that the catalog repairs metadata ClickHouse's experimental writer does not emit (missing field IDs, bucket-relative paths, default name mapping) - and that this repair needs SeaweedFS 4.42+.
- **Spark** - works over S3 with `s3.endpoint` + `s3.path-style-access=true`; `s3-spark-tests.yml` and `spark-integration-tests.yml` in CI. Also offers a **Hadoop-compatible filesystem** (`seaweedvfs://` / `seaweedfs://`) for Spark, Flink and HBase.
- **Flink** - same Hadoop FS path; `kafka-tests.yml` in CI. The README names Spark, Trino, Dremio, DuckDB, Apache Doris, RisingWave, ClickHouse and LanceDB as query engines on the same tables concurrently, with *"Catalog commits are atomic compare-and-swap, so concurrent writers are safe."*
- **s3a://** - not required. `s3a://` is a Hadoop *client* scheme and works against any of these via `fs.s3a.endpoint` + `fs.s3a.path.style.access=true`. SeaweedFS's own Hadoop FS is the better choice for Flink checkpoints and Spark shuffle dirs - see §8.

#### 3.1.4 Container image and Helm chart

- **Image:** `chrislusf/seaweedfs` on Docker Hub. **1000+ tags** (1.27 through 4.x), **4 sub-manifests** (multi-arch). Confirmed present and pullable at 2026-09-27 (`HTTP 200` with a pull token). Built and published upstream by the project via `container_latest.yml`, `container_release_unified.yml`, `container_release_foundationdb.yml` workflows - i.e. **published upstream, not a third-party mirror.**
- **Helm:** chart lives **in-tree** at `k8s/charts/seaweedfs`, and the repository is published to a live Helm repo. Verified: `https://seaweedfs.github.io/seaweedfs/helm/index.yaml` returns `200`, and its newest entry is
  ```yaml
  seaweedfs-4.47.0.tgz   created: 2026-09-14T02:50:02Z   appVersion: "4.47"
  ```
  - which tracks the GitHub release (4.47, 2026-09-14) to the day. Also on ArtifactHub.
  - **Quality caveat:** `Chart.yaml` is `apiVersion: v1` (Helm 2 era) with `version: 4.47.1`. It still installs on Helm 3, but there are no `dependencies:`/`Chart.lock`, and the README says *"cert config exists and can be enabled, but not been tested."* It is a competent chart, not a polished one. Also note the README's advice: the **leveldb2 default filer backend** is fine for one node; HA filer needs a MySQL-compatible store, which is out of scope for us.

#### 3.1.5 Footprint against our 7-8 GB / 231 GB

`weed mini` is explicitly the small-machine mode. Defaults read out of `weed/command/mini.go` (2,234 lines):

```go
defaultMiniVolumeSizeMB = 128    // Default volume size for mini mode
-volume.fileSizeLimitMB   256    // limit file size to avoid out of memory
-volume.readBufferSizeMB  4      // read buffer size in MB
-s3.cacheCapacityMB       0      // in-memory chunk cache for S3 GETs (0 disables)
-s3.readerCacheSizeMB     0      // reader buffers across S3 GETs (0 means unlimited)
```

**One Go process, master + volume server + filer + S3 gateway + Iceberg REST catalog + admin UI, with both S3 caches off by default.** The README: *"`weed mini` is auto-tuned for one node and is fine for single-node production."* ClickHouse's compose runs it as a single container. This is the only candidate whose documented operating mode is sized for a 7-8 GB box with Kafka, Spark, Flink and ClickHouse also resident.

Disk: 231 GB minus whatever the rest of the platform needs. **Erasure coding is a real cost here** - the project's own page states the OSS build is fixed at **EC 10+4 (1.4x overhead)**; 20+4 (1.2x) is Enterprise. Budget usable ≈ 150-160 GB before the wall.

#### 3.1.6 Operational complexity for a single-node operator

- **The filer is the metadata spine.** In `weed mini` it is leveldb2 inside the same process. One disk, one failure domain. The chart README is explicit that leveldb filer-replica sync "supports multiple filer replicas ... with limitations" and that HA filer needs MySQL/Postgres.
- **Volume index is in memory by default** (`-volume.index=memory`), rebuilt on restart.
- **A real single-node footgun, open right now:** issue **#10838 (2026-08-19)** - *"`weed mini`: default `-admin.port` derives an admin gRPC port inside the ephemeral range (33646)"*. ClickHouse's guide works around it explicitly with `-admin.port=12646`. We will hit this; take the workaround from the start.
- **Write amplification does not shrink with object size.** SeaweedFS's own README: *"Each file write incurs extra writes to the corresponding meta file, on every drive of the erasure set. Changing only tags or retention rewrites that meta file on all of them ... There is no optimization for lots of small files."* At Iceberg scale - millions of small Parquet files plus manifests plus metadata JSON - **this is the single most important thing to benchmark and publish.** The upside claimed in the same README is O(1) disk reads and p50 write latency of 0.8 ms; both can be true at once.
- **On one box with one directory there is no erasure set**, so you are running a single copy on a single disk. MinIO in single-drive mode had the same property, so this is not a regression - but it is a claim we must not make.
- **Remote tiering exists** (`weed/storage/backend`, `design-cloudstack-provider.md`), which is the built-in path to offloading cold data to real S3.

#### 3.1.7 Built-in Iceberg REST catalog vs our separate Polaris decision

They are **alternatives, not complements.** Polaris *is* the catalog; a built-in REST catalog in the object store *replaces* it. My recommendation:

- **Dev / demo / laptop:** use SeaweedFS's built-in catalog. It is one process instead of three, it needs no relational database, and it removes an entire failure domain from the demo. This is a strong portfolio story in itself - *"here is the whole lakehouse in one binary."*
- **Production / governance:** use **Apache Polaris**, as the JD says. `apache/polaris`, Apache-2.0, ASF, latest release `apache-polaris-1.7.0` (2026-08-02), 1.6.0 (2026-07-09), 1.5.0 (2026-05-18), last push 2026-09-27. Contributor distribution is broad and multi-employer (after renovate-bot: snazy 528, adutra 300, MonkeyCanCode 280, jbonofre 190, dimas-b 172, flyrain 135, XN137 86, eric-maynard 86...). Polaris gives RBAC, multi-engine federation, and a governance surface that neither candidate's built-in catalog has.
- **The migration is one line in the catalog config**: swap `type=rest` + `uri=http://seaweedfs:8333/...` for `type=rest` + `uri=<polaris>/api/catalog`. The warehouse path and every data file stay exactly where they are, because the object store does not change. **That is the whole argument for choosing a storage engine with a standard catalog protocol rather than one that locks the catalog in.**

#### 3.1.8 The open-core problem - stated plainly

**`seaweedfs.com` is now a commercial product page titled "SeaweedFS Enterprise."** It sells at **$2/TB/month** or $20/TB/year, with "Free - Dev & Test under 25TB," a linked **EULA**, and a `weed shell` licence-key flow (`license.set -file=license.key`). The comparison table gates, in the project's own words:

| Capability | Open Source | Enterprise |
|---|---|---|
| S3 / FUSE / HDFS / Iceberg APIs | yes | yes |
| Erasure Coding | **"Fixed ratio"** | Customizable (20+4 = 1.2x) |
| Storage Compression | **gzip** | zstd by default + gzip |
| Sealed Directories (18-58x filer metadata reduction) | - | yes |
| Data Recovery (undelete) | - | yes |
| Point-in-Time Recovery | - | yes |
| Self-Healing Storage | - | yes |
| Automatic EC Repair & Vacuum | - | yes |
| Remote Volume Vacuum | - | yes |
| EC Bitrot Scrub | - | yes |
| Admin UI with OIDC | - | yes |
| Multi-Tenancy & S3 QoS | - | yes |
| Support | Community | 24h on business days |

`weed version` prints, unprompted: *"For enterprise users, please visit https://seaweedfs.com for the SeaweedFS Enterprise Edition, which has advanced features, including data recovery, self-healing storage, customizable erasure coding, EC vacuum and repair, etc."*

**What is gated that we would want:** bitrot scrubbing, self-healing, EC repair, zstd, custom EC ratios, tenant isolation, admin OIDC. **What is *not* gated: every S3/FUSE/HDFS/Iceberg API, the Iceberg REST catalog, and the fixed 10+4 EC.** So the Iceberg path is safe. The durability-and-cost path is where a future upgrade conversation becomes a sales conversation - and that is the pattern that killed MinIO, one stage earlier.

This is a genuine finding against my own recommendation and it belongs in the write-up, not in a footnote. §10 is how we watch it.

---

### 3.2 RustFS - **recommended fallback**

**Governance and licence - the sharpest issue.** Apache-2.0 *on the LICENSE file*. But `CLA.md` is an **Individual Contributor Licence Agreement owned by "RustFS, Inc."**:

> *"In order to clarify the intellectual property license granted with Contributions... **RustFS, Inc. ("RustFS") must have a CLA on file** that has been signed by each Contributor."*
>
> *"you hereby grant to RustFS and recipients of software distributed by RustFS a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce... and distribute your Contributions... under the Apache License, **at RustFS's sole discretion**."*

Compare with the Apache-2.0 grant in §3.1, which grants the same rights with no intermediary discretion. **Structurally, this is the CLA that caused the MinIO relicensing fight in 2021.** No `GOVERNANCE.md`. No foundation. Commercial steward: RustFS, Inc., with 27 public repos under the `rustfs` org.

**Release status - the second sharp issue.** Of the **last 100 GitHub releases, exactly one is not marked prerelease**:

| Tag | Published | Prerelease |
|---|---|---|
| `1.0.1-preview.11` | 2026-09-24 | yes |
| `1.0.1-preview.10` | 2026-09-22 | yes |
| `1.0.1-preview.9` | 2026-09-21 | yes |
| `1.0.0` | **2026-09-16** | **no** |

A `1.0.1-preview.12` tag was cut on 2026-09-27. `SECURITY.md` says `| Latest | yes |` and `| < 1.0 | no |`. The project shipped 1.0.0 **eleven days ago** and has been on previews ever since, cutting a build every 1-3 days. This is a young codebase in a churn phase, and issue **#8003 (2026-09-18)** is titled *"Upgrading 1.0.0-beta.11-preview.1 -> 1.0.1-preview.5 breaks existing buckets (500 ...)"*. **Pin exactly.**

**Activity.** 33,945 stars, 1,526 forks, **59 open issues**, last push 2026-09-27T04:30:30Z. 6,837 commits, **173 contributors**:

```
overtrue   2,463   36.5%
houseme    1,474
weisd        715
cxymds       401
guojidan      249
top-5 78.6%   top-10 91.0%
```

Better concentration than SeaweedFS. But **59 open issues for a 34k-star project** is a very thin backlog - it reads like a young project with a marketing-driven star count rather than a production user base.

#### 3.2.1 S3 API fidelity - the best evidence in the field

`docs/architecture/s3-compatibility-matrix.md` is unusually rigorous: it declares its own source of truth as **Ceph's `s3tests` suite** and the runner `scripts/s3-tests/run.sh`, and requires counts to be derived from the test lists rather than recorded by hand. Computed from those files:

| List | Count |
|---|---|
| `scripts/s3-tests/implemented_tests.txt` | **460** |
| `scripts/s3-tests/unimplemented_tests.txt` | **21** |
| `scripts/s3-tests/excluded_tests.txt` | **274** |
| `scripts/s3-tests/lifecycle_behavior_tests.txt` | 5 |

Supported per the matrix, and verified present as test names in `implemented_tests.txt`:

- Bucket create/delete/list/head; object put/get/delete/copy/head
- **Multipart**: create/upload/complete/abort/list, multipart copy, `test_multipart_copy_without_range`, `test_multipart_upload_overwrite_existing_object`, `test_multipart_upload_incorrect_etag`
- **Range reads**: `test_ranged_request_empty_object`, `test_ranged_request_invalid_range`
- **Conditional reads**: If-Match, If-None-Match, If-Modified-Since
- **Conditional writes**: *"Conditional writes: If-Match/If-None-Match for PUT/Copy"*
- **Versioning + delete markers**: `test_versioning_bucket_atomic_upload_return_version_id`, `test_versioning_multi_object_delete_with_marker`, `test_versioning_obj_create_versions_remove_all`, `test_versioning_multi_object_delete_with_marker_create`
- Object Lock; presigned GET/PUT; bucket policy; public access block; SSE-C and selected SSE-KMS
- Checksums: CRC32, CRC32C, CRC64NVME, SHA1, SHA256, MD5, SHA512, XXHASH3, XXHASH64, XXHASH128, incl. source preservation and explicit override
- `test_abort_multipart_upload`, `test_multipart_resend_first_finishes_last`, `test_lifecycle_set_multipart`

Not passing: bucket access logging (handlers exist, `s3tests` cases still unimplemented), POST-Object form checksum handling, **bucket ownership controls (no handler)**, multipart listing / part-lookup edge cases, IAM-account-dependent cases, tenanted bucket-policy edge cases.

Two **intentional deviations from AWS S3**, documented as such:
1. Object keys with `.`, `..` or empty (`//`) path segments return `400 InvalidArgument` rather than being treated as opaque.
2. Directory markers (keys ending `/`) in a versioned bucket are stored as the **null version**, so a later PUT overwrites in place.

CI: 14 workflows, including `rustfs-s3-compat-test.yml`, `e2e-s3tests.yml`, `rustfs-table-test.yml`, `rustfs-upgrade-test.yml`, `rustfs-fault-tolerance-test.yml`, `rustfs-heal-test.yml`, `rustfs-kms-test.yml`, `rustfs-replication-test.yml`, `rustfs-tier-test.yml`, `minio-interop.yml`.

#### 3.2.2 MinIO on-disk interoperability - the best "why not just MinIO" answer available

`docs/architecture/minio-file-format-compat.md` is a one-way interop contract (MinIO -> RustFS), backed by fixtures and a dedicated CI workflow:

| MinIO artifact | default/full build | `rio-v2` build |
|---|---|---|
| Unencrypted `xl.meta` (meta_ver 1-3, inline, multipart, versioned, delete marker) | **Read** | Read |
| `.metadata.bin` bucket config (a `.minio.sys` layout) | **Read and imported** | Read and imported |
| IAM config under `config/iam/` | **Imported** | Imported |
| SSE-S3 / SSE-KMS objects (MinIO builtin static KMS) | fail closed, diagnosed | **Read** (needs the master key) |
| SSE-C objects | fail closed, diagnosed | Read |
| Any SSE object behind KES / KMS plugin / MinKMS | fail closed | fail closed |
| RustFS-written drive read by a live MinIO binary | Unsupported (`MinIO looks for .minio.sys, RustFS writes .rustfs.sys`) | same |

So: **if the prototype still has MinIO data on disk, RustFS can adopt it without a rewrite** - point the new binary at the old drives. That is a one-line migration, not an `rclone` week. It is the single most concrete thing in this report for the "why not just MinIO" question.

#### 3.2.3 Iceberg catalog - a Preview with a manual Spark path

`docs/architecture/s3-tables-support-matrix.md` is admirably honest - it defines status labels, names its source of truth (`rustfs/src/admin/handlers/table_catalog/` and `scripts/table-catalog/`), and has a "Release Claim Guidance" section that explicitly forbids the phrase *"RustFS is fully compatible with AWS S3 Tables."*

- **README status: `S3 Tables (Iceberg REST) | 🧪 Preview`.**
- Endpoints: `/iceberg/v1` supported; `/_iceberg/v1` as a MinIO-AIStor-style alias.
- Client coverage: **PyIceberg = Automated. DuckDB 1.5.5 = Automated** (create/insert/update/delete/merge, schema evolution, snapshots, concurrent writers, drop, PyIceberg cross-read, both signing profiles). **Spark Iceberg REST catalog = "Manual/live harness"**, with pinned package inputs and *"Live execution and commit-conflict probing remain manual unless enabled in the runner."* **Trino = read-only, "Write compatibility not claimed."**
- `Multi-table transactions | Not claimed`. `Active-active multi-region writes | Not claimed`. `Built-in periodic maintenance scheduling | Not claimed`. `Delete-file or row-level compaction execution | Not claimed`.
- Maintenance (compaction, snapshot expiry, orphan cleanup) is `Preview / controlled` - operator-triggered, no built-in scheduler.
- Open issues as of 2026-09-27, all filed in the last three days: **#8103** (2026-09-24) *"S3 table select table.files failed, AWS SigV4 ERROR"*; **#8100** (2026-09-24) *"S3 table clean table, rewrite_data_files failed"*; **#8116** (2026-09-25); **#8104** (2026-09-27) *"fix(table-catalog): preserve data sequences during file rewrites"*.

The docs are better than SeaweedFS's here - SeaweedFS has no equivalent published matrix. But **a Spark path that CI does not run is not a guarantee**, and the JD's stack is Spark-and-Flink-first.

#### 3.2.4 Engines, footprint, containers, Helm, operations

- **ClickHouse:** nothing first-party.
- **Flink:** issue **#1287** (closed 2026-05-31) *"[Bug] Bulk Delete Operation Fails in Flink with RustFS S3 Storage"*; issue **#5961** (closed 2026-08-12) *"Concurrent UploadPart requests for different part numbers are serialized"*. Both fixed, but they are a pattern of multipart/upload-path edge cases that SeaweedFS's CI matrix also targets and RustFS's does not specifically.
- **Memory - documented and it fits.** `docs.rustfs.com`: *"RustFS needs at least 2 GB of memory to run test environments"*; the hardware-selection page says **1 core+, 1 GB+** for a test environment. Comfortably inside 7-8 GB.
- **Image:** `rustfs/rustfs` on Docker Hub, **186 tags**, 4 sub-manifests, published upstream by `docker.yml`. Confirmed pullable.
- **Podman: yes.** RustFS documents a dedicated **"Install with Podman"** path, rootless and daemonless. That is a direct fit for our podman-5.7-no-Docker box and SeaweedFS does not document one as explicitly.
- **Helm:** two sources, both weak. An in-repo `helm/rustfs` chart (`apiVersion: v2`, `version: 1.0.0`, `appVersion: 1.0.0`, `maintainers: - name: RustFS, Inc.`), and a separate `rustfs/helm` repo (24 stars) whose published artifact is **`rustfs-0.0.68.tgz`** - a version number that has nothing to do with the app's 1.0.0. `https://rustfs.github.io/rustfs/helm/index.yaml` returns **404**. The chart defaults to `replicaCount: 4` distributed mode, so a laptop install needs `--set mode.standalone.enabled=true mode.distributed.enabled=false`.
- **Operations:**
  - **SNSD is a one-way door.** README: *"A single-node single-drive (SNSD) deployment is supported only as a standalone local path. **It cannot expand in place or be added to a Pool.** To move to a multi-drive topology, create a new deployment and migrate data through S3."* That is a real trap for a dev setup that later wants to grow.
  - EC geometry: an erasure set must be 2-16 drives and divide the drive list symmetrically; pool expansion requires ellipsis expressions in every Pool argument.
  - `FullReady = storage_ready && iam_ready && lock_quorum_ready && peer_health_ready` (`rustfs/src/server/readiness.rs`). Until then the **S3 data plane returns `503` with `Retry-After: 5`**. A sick disk becomes S3 503s, not degraded reads. Design the platform's health checks around that.

---

### 3.3 Garage - **rejected: S3 fidelity and governance**

- **Governance and licence:** **AGPL-3.0**. Built by **Deuxfleurs**, self-described as *"an experimental small-scale self hosted service provider."* The GitHub repo is an explicit **mirror** - *"Main repo: https://git.deuxfleurs.fr/Deuxfleurs/garage"* (Gitea). No GitHub releases; tags only.
- **Releases:** `v2.4.1` 2026-09-07, `v2.4.0` 2026-09-06, `v2.3.0` 2026-04-16, `v2.2.0` 2026-01-24. Last commit 2026-09-26. Active.
- **Concentration:** 2,897 commits, 97 contributors, `Alexis211` (Alex Auvolat) **1,491 / 2,246 = 66.4%**, top-5 87.4%.
- **S3 fidelity - the disqualifier.** From Garage's own `s3-compatibility` page, whose own update history reads *"2022-05-25 - ..."* - **the page has not been updated in over four years**, and it warns *"We are not proactively monitoring new versions of each software."* Missing:
  - **`PutBucketPolicy` / `GetBucketPolicy` / `DeleteBucketPolicy` - Missing.** Its own words: *"Garage implements none of them, and has its own system instead, built around a per-access-key-per-bucket logic."*
  - **`PutBucketVersioning` Missing; `ListObjectVersions` Missing; `GetBucketVersioning` is a stub that always returns "versioning not enabled".**
  - All object lock; all SSE (except SSE-C); all object and bucket tagging; event notifications; bucket replication; `SelectObjectContent`; `RestoreObject`; all ACLs.
  - **No conditional requests appear anywhere in the table.**
  - Lifecycle is limited to `Expiration` (without `ExpiredObjectDeleteMarker`) and `AbortIncompleteMultipartUpload`.
  - Present: all core endpoints, the full multipart set, presigned URLs, path- and vhost-style, SSE-C, CORS, static websites, bucket aliases.
- **No built-in Iceberg catalog.**
- **No upstream container image:** `garagehq/garage` returns `401` on Docker Hub; the project distributes **binary packages** and a compose file, not a published image. There is no Helm chart (the K8s cookbook is a ConfigMap recipe).
- **Verdict:** the missing bucket-policy API is fatal for a platform whose whole point is governance and access control, and the missing versioning kills the retention story. Excellent software, wrong shape.

---

### 3.4 Apache Ozone - **rejected: S3 fidelity AND footprint**

- **Governance and licence:** **Apache-2.0, ASF-governed** - the only true foundation project in this set, alongside Ceph. That is a real and durable advantage, and the right project to pick if S3 fidelity were not a constraint.
- **Activity:** 1,309 stars, 646 forks, 123 open issues, last push 2026-09-27. Releases: `2.2.1` 2026-08-27, `2.2.0` 2026-07-16, `2.1.2` 2026-09-18 (a backport landing after 2.2.1 - a healthy sign of branch discipline).
- **Concentration:** 11,407 commits, 300 contributors, `adoroszlai` 1,803/10,309 = **17.5%**, **top-10 = 45.3%** - by far the most distributed of the object stores here (and the bot contribution, renovate + dependabot at ~1,072, is counted inside those percentages, so the human share is broader still). This is what a foundation buys you.
- **S3 fidelity - disqualifying, from Ozone's own 2.2.1 docs:**
  > *"**Advanced Features Not Supported:** ACLs, Bucket Policies, CORS Configuration, and Website Hosting: These are not fully implemented; Ozone uses an internal permission model that deviates from AWS S3."*
  > *"**Bucket Versioning, Object Locking, Server-Side Encryption, and S3 Select: These features are currently not supported.**"*
  > *"**Conditional Requests:** Support for conditional requests (e.g., `If-Match`, `If-None-Match`) is planned and tracked in HDDS-13117."*

  HDDS-13117 is a JIRA ticket, i.e. **not implemented** in 2.2.1. It does have complete multipart (all six operations), tagging, `ListObjectsV2`, presigned URLs for all major operations, and **path-style addressing by default** (`ozone.s3g.domain.name` switches it to virtual-host).
  Also: `GetObject` on a missing object *"may return a generic 404 without the structured XML error body"*; the presigned URL *"may include a fixed default region."*
- **Security model is a barrier.** AWS SigV4 only (no SigV2). With security enabled, `ozone s3 getsecret` **requires a Kerberos kinit**. With security disabled, **any** `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` works. There is no useful in-between for us, and Kerberos is a heavy thing to add to a portfolio.
- **`s3a://` needs four overrides**, and Cloudera adds a fifth: `fs.s3a.endpoint`, `fs.s3a.path.style.access=true`, `fs.s3a.bucket.probe=0`, `fs.s3a.change.detection.mode=none` - and *"S3A is not supported when the File System Optimization (FSO) ... is enabled ... FSO is enabled by default,"* so you must also set `ozone.om.enable.filesystem.paths=false`. That is five config changes and a cluster restart to get Hadoop working.
- **No built-in Iceberg REST catalog.**
- **Footprint - the hard fail.** Ozone's own `administrator-guide/installation/hardware-and-sizing` page (last updated 2026-09-21):
  - *"A minimal production-ready deployment should include: 3 nodes for OM HA, 3 nodes for SCM HA, at least a single Recon instance, **Minimum 10 Datanodes** for RS-6-3."*
  - Reference config: metadata nodes **128 GB RAM / 31 GB JVM heap each x3**; datanodes **128 GB RAM / 31 GB heap each x10+**.
  - That is a documented production minimum of **~1.7 TB RAM**, roughly 200x our free 7-8 GB.
  - Performance guide: OM/SCM/Recon 64 GB heap in large clusters; Datanode/S3 Gateway/HttpFS 31 GB heap.
  - *"Bare metal machines are recommended... **Virtual machines or containers are not recommended for production deployments.**"*
  - The official dev compose (`apache/ozone-docker/docker-compose.yaml`) runs **six JVMs** - `datanode`, `om`, `scm`, `recon`, `s3g`, `httpfs` - from one image, and the docs say to start it with `--scale datanode=3`, i.e. **eight JVMs**. Each JVM has RSS overhead well above its heap.
- **Image/Helm:** `apache/ozone` on Docker Hub, 41 tags, 4 sub-manifests, published upstream. No official Helm chart; the ASF ships a compose and a "Docker Runner Image" instead.
- **Verdict:** wrong project for this box, and wrong S3 API for this platform. If a future phase ever needs a foundation-governed object store, Ozone is the one to re-examine - after HDDS-13117 lands.

---

### 3.5 Ceph - **rejected on footprint, as expected**

- **Governance and licence:** LGPL-2.1 (GitHub's licence detector reports `NOASSERTION`; the project is LGPLv2.1+). No single steward - contributions come from Red Hat, Intel, IBM and a wide downstream including China Mobile. The most genuinely distributed contributor base measured here: 300+ contributors, `tchaikov` 12,342, `yehudasa` 5,440, `cbodley` 4,736, `batrick` 4,603, `gregsfortytwo` 3,512, `jdurgin` 2,638, `athanatos` 2,348, `zdover23` 2,059, `ukernel` 1,926, `idryomov` 1,681.
- **Activity:** 17,074 stars, 6,511 forks, 1,543 open issues, last push 2026-09-26. Tags `v21.0.0` 2026-03-25, `v21.3.0` 2026-06-10, `v20.0.0` 2025-03-03. No GitHub releases; Ceph ships via its own tracker. Current stable line is Squid; `v21` is the next major on `main`.
- **S3 fidelity: the best in the world.** RGW is what the industry tests against - and, notably, **both SeaweedFS and RustFS run Ceph's own `s3tests` suite against themselves.** RGW has versioning, object lock, SSE-C/SSE-KMS, real bucket policies, CORS, full multipart and conditional requests. If S3 fidelity were the only criterion, Ceph wins.
- **Footprint - the hard fail, from Ceph's own `hardware-recommendations`:**
  | Daemon | Documented RAM |
  |---|---|
  | `ceph-osd` | **4 GB+ per daemon** (`osd_memory_target` default 4 GB); *"2-4GB may function but will be slow"*; *"Less than 2GB is not recommended"* |
  | `ceph-mon` | **5 GB+ per daemon** |
  | `ceph-mds` | 2 GB+ |
  | `ceph-radosgw` | 1 GB |

  A minimal RGW-serving cluster is 3 mons + 2 mgrs + 3 OSDs + 1 RGW ≈ **15 + 12 + 1 = 28+ GB**, before mgr overhead - **~4x our entire 14 GB machine**, and 3.5x our *free* RAM. Red Hat's containerized guidance is worse: *"Minimum of 5 GB of RAM per OSD container, 3 GB per mon-container, 3 GB per mgr-container."* On top: BlueStore wants a DB/WAL device per OSD (ideally NVMe), the RGW is a multi-process C++ stack per daemon, and `ceph-volume` preparation is a real operational chore.
- **No built-in Iceberg REST catalog.** Ceph lives in the Hadoop world - `HadoopCatalog` + Hive Metastore, and `ofs://`/`s3a://` rather than a modern REST catalog.
- **Verdict:** a data-centre product. Correct answer, wrong planet. Included for completeness; excluded on RAM, permanently, for this platform.

---

### 3.6 The option of not self-hosting

This is not a consolation prize. It is the correct answer for two specific jobs, and the honest framing for the cost story.

#### 3.6.1 A real S3 bucket on a free tier

| | **Cloudflare R2** | **Backblaze B2** |
|---|---|---|
| Free tier | **10 GB-month** storage, **1 M** Class A (writes/deletes), **10 M** Class B (reads) | **first 10 GB always free**, Class A/B/C **free** for pay-as-you-go, 2,500 Class D/day free |
| Egress | **zero, always** | free to **3x average monthly storage**, then $0.01/GB; also free through the Cloudflare Bandwidth Alliance |
| Paid | $0.015/GB-month; IA class $0.01/GB-month + $0.01/GB retrieval | **$6.95/TB/month** (vs S3 $26, GCP $20, Azure $23) |
| Iceberg-relevant features | has its own **R2 Data Catalog** for Iceberg | full S3 API incl. **Object Lock**, versioning, lifecycle, CORS, `ListObjectVersions`, multipart, `CopyObject`; only Class D (egress) is billed |

**B2 is the better fit for a write-heavy ingestion demo** - uploads are free, and Class A is where an Iceberg write path spends. R2 is the better fit where egress dominates (a ClickHouse serving layer reading a lot). Use **B2 for the dev/demo bucket and R2 for the CI bucket**, and say why: it demonstrates that the platform is not coupled to one provider, which is a *stronger* portfolio signal than either one alone.

One caution, verified above: RustFS generates a **Cloudflare R2 Data Catalog profile** and a **MinIO AIStor Tables profile**, but its own matrix says these are *"Profile generator"* / *"reference only"* - *"live interop not claimed."* R2 has quirks around checksums and conditional requests. **Test, do not assume.**

#### 3.6.2 An S3 API emulator in tests

| Emulator | Status at 2026-09-27 | Verdict |
|---|---|---|
| **LocalStack** | **`archived: true`.** Last release `v4.14.0` (2026-02-26). Last commit 2026-03-23. README: *"we are consolidating our development into a single, unified image. As part of this transition, **this repository is now archived and read-only** ... LocalStack for AWS offers a range of options including a **free Hobby plan for non-commercial use**."* | **Do not build on it.** It is the *second* project in this report to hit the exact MinIO pattern - a strong community project that moved the free tier behind a commercial licence and archived the repo. Cite it in the write-up as evidence that the pattern is a property of the market, not of MinIO's management. |
| **moto** (`getmoto/moto`) | Apache-2.0, 8,679 stars, **not archived**, last push 2026-09-26, `5.2.3` (2026-08-22) | **Recommended for unit tests.** In-process Python mock; `moto.server` can front it over HTTP. Perfect for asserting our Dagster/Iceberg glue code's call sequence. Not a data plane for Spark or Flink. |
| **Adobe S3Mock** (`adobe/S3Mock`) | Apache-2.0, 1,158 stars, **not archived**, last push 2026-09-21, `5.2.3` (2026-09-19) | **Recommended for integration tests.** Standalone Spring Boot app / Testcontainers. Better protocol fidelity than moto for a Java-side Spark job. |
| **`iceberg-rest-fixture`** | Shipped by Apache Iceberg itself for testing REST catalogs | Use it to unit-test the catalog client against a *known-good* spec implementation, so a bug in our object store's catalog is distinguishable from a bug in our code. |
| **RustFS `s3chaos`** | In the `rustfs` org, active 2026-09-26 | Interesting: a chaos/failure probe for S3. Worth reading even if we do not adopt RustFS. |

**Layered plan:** `moto` for fast unit tests, `S3Mock` for integration, **R2/B2 for the end-to-end pipeline in CI** - because only real S3 exercises real multipart, real checksums, and real SigV4. An emulator is a fixture, not evidence.

---

## 4. Scorecard

Legend: **++** strong / **+** adequate / **~** workable with caveats / **-** weak / **--** disqualifying.

| | SeaweedFS | RustFS | Garage | Ozone | Ceph | R2/B2 | emulator |
|---|---|---|---|---|---|---|---|
| Licence | ++ Apache-2.0, no CLA | ~ Apache-2.0 **+ RustFS, Inc. CLA, "sole discretion"** | - AGPL-3.0 | ++ ASF | ++ LGPL, no steward | n/a | ++ Apache-2.0 |
| Governance | ~ bus factor 1, **no governance doc**, just went open-core | - company, no foundation, no disclosed funding | ~ 2-person co-op | ++ ASF | ++ federated vendors | n/a | ++ ASF (moto) |
| Release health | ++ weekly `x.y`, no prereleases | -- 1.0.0 **11 days old**; 99 of last 100 releases are `preview` | ~ v2.4.1 2026-09-07, tags only | ++ 2.2.1 + backports | ++ v21.3.0 2026-06-10 | n/a | + |
| Commit concentration | - 74.8% one person | ~ 36.5% top-1 | - 66.4% one person | ++ top-10 = 45.3% | ++ very broad | n/a | n/a |
| Contributor count | ++ 397 | ~ 173 | - 97 | + 300 | ++ 300+ | n/a | n/a |
| S3: multipart | ++ | ++ | ++ | ++ | ++ | ++ | ~ |
| S3: range reads | ++ | ++ | ++ | ++ | ++ | ++ | ~ |
| S3: conditional writes | ++ | ++ | **-- absent from its own matrix** | **-- HDDS-13117** | ++ | ~ test it | ~ |
| S3: versioning + delete markers | ++ | ++ | **-- stub / missing** | **-- unsupported** | ++ | ++ | ~ |
| S3: bucket policies (governance) | ++ | ++ | **-- missing, by design** | ~ "internal permission model" | ++ | ++ | ~ |
| S3: object lock / SSE / CORS | ++ (SSE gzip/entropy) | ++ | -- SSE only SSE-C; no lock | - no SSE (Ranger KMS instead) | ++ | ++ (B2 lock) | ~ |
| **Built-in Iceberg REST catalog** | **++ in Apache-2.0 core, multi-table transactions, views, OAuth** | ~ **Preview**; Spark "manual/live harness"; no multi-table txn | - none | - none | - none | ~ R2 Data Catalog | - |
| Iceberg + Spark | **++ CI-gated** | ~ manual harness only | ~ untested | - needs 5 S3A overrides | + | ++ | - |
| Iceberg + Flink | + Hadoop FS, `kafka-tests.yml` | ~ fixed bulk-delete bug (#1287) | ~ | - no S3 event notifications | + | ++ | - |
| **Iceberg + ClickHouse** | **++ first-party guide, versioned** | - none | - none | ~ listed as compatible | + | ++ via `DataLakeCatalog` | - |
| `s3a://` / Hadoop | ++ own Hadoop FS + S3A | ~ S3A | ~ S3A | - FSO must be disabled | ++ native | ~ | - |
| RAM vs our 7-8 GB | **++ `weed mini`, 1 process, caches off** | **++ documented 1-2 GB test** | ++ light | **-- 1.7 TB documented min** | **-- ~28 GB documented min** | **++ 0** | + moto in-process |
| Disk vs 231 GB | ~ 1.4x EC overhead (10+4) | ~ 2x+ EC, SNSD cannot grow | ~ 3x replication typical | -- 25Gbps + NVMe metadata | -- NVMe DB/WAL per OSD | **++ unbounded** | - |
| Upstream container image | **++ `chrislusf/seaweedfs`, 1000+ tags, 4 arches** | **++ `rustfs/rustfs`, 186 tags, 4 arches** | **-- none published** | **++ `apache/ozone`, 41 tags** | ++ `quay.io/ceph/ceph` | n/a | ++ |
| Helm chart | **+ live, tracks releases to the day; `apiVersion: v1` is dated** | ~ in-repo + a 0.0.68 chart repo, canonical URL 404 | - none | - compose only | - operator/rook | n/a | n/a |
| Podman story | ~ (compose works) | **++ documented Podman install path** | ~ binary packages | ~ compose | ~ | n/a | ++ |
| MinIO data adoptable | - S3 copy required | **++ reads `xl.meta` + `.minio.sys` in place** | - | - | ~ reads MinIO layout | n/a | n/a |
| Same-fate risk | ~ **high**: bus factor 1 + just went open-core | **-- high**: discretionary CLA + company, MinIO's exact pitch | ~ | **-- lowest** | **-- lowest** | n/a | ++ moto |

---

## 5. Recommendation

**Primary: SeaweedFS 4.47, `weed mini` single-process mode, with its built-in Apache-2.0 Iceberg REST catalog for dev/demo and Apache Polaris for the production/governance story.**

Deployment sketch for our box (one podman process, not a pod):

```
weed mini -dir=/srv/warehouse \
          -s3.config=/etc/seaweedfs/s3config.json \
          -tableBucket=warehouse \
          -admin.port=12646            # issue #10838: keep out of the ephemeral range
```

Then, once, per client:

```
Spark:   spark.sql.catalog.lake.s3.endpoint            = http://127.0.0.1:8333
         spark.sql.catalog.lake.s3.path-style-access   = true
Flink:   's3.endpoint' = 'http://127.0.0.1:8333'  +  's3.path-style-access' = 'true'
PyIceberg: "s3.endpoint": "...", "s3.path-style-access": "true"
ClickHouse: DataLakeCatalog('http://127.0.0.1:8181/v1', ...) + storage_endpoint
Hadoop:  fs.s3a.endpoint = http://127.0.0.1:8333 ; fs.s3a.path.style.access = true
```

**Fallback: RustFS 1.0.0, pinned exactly**, standalone mode. Adopt it if either (a) SeaweedFS's Iceberg catalog regresses, or (b) we discover the prototype has meaningful MinIO data on disk that we must adopt in place, or (c) the governance risk in §3.1.8 crystallises and we decide a vendor with a security-advisory process beats a single maintainer.

**Runner-up placement, stated explicitly:** RustFS is the **fallback, not the co-primary.** It wins on S3 conformance evidence (460 passing `s3tests`) and loses on the one thing our stack cannot do without (a CI-verified Spark path through the Iceberg catalog). If the platform ever drops Spark from the write path, flip the order.

**Deliberately not chosen:** Ozone and Ceph are better-governed than either of our picks. We are choosing them anyway because neither has the S3 API Iceberg needs, and neither fits in 8 GB. If governance weight ever outranks both, the correct move is to *stop self-hosting the object store entirely* and use B2/R2 - not to run Ozone on a laptop.

---

## 6. "Why not just MinIO?" - the answer for an interviewer who knows MinIO

This is the question that will be asked, and a vague answer loses the room. Five specific prongs:

1. **"It no longer exists as a thing you can run."** `minio/minio` was archived 2026-04-24; `minio/mc` is archived too; and - the part people miss - **`minio/minio` no longer exists on Docker Hub at all.** With a valid pull-scoped token the registry returns `401 UNAUTHORIZED` and zero tags, while `chrislusf/seaweedfs` returns `200` from the identical call. The prototype's `image: minio/minio` cannot resolve. This is not a deprecation, it is a removal.

2. **"Your data is not stranded, and I checked who can read it."** RustFS's `docs/architecture/minio-file-format-compat.md` - a first-party interop contract with fixtures and a `minio-interop.yml` CI workflow - documents that the default build **reads unencrypted `xl.meta` (meta_ver 1-3, inline, multipart, versioned, delete markers), reads and imports `.metadata.bin` from a `.minio.sys` layout, and imports `config/iam/`**. MinIO SSE objects are readable in the `rio-v2` build. So if we still have MinIO disks, the migration is *point the new binary at the old drives* - a one-way MinIO->RustFS handoff, not a `rclone` week. **If we take the SeaweedFS recommendation instead, the honest statement is: `rclone sync` from RustFS or MinIO to SeaweedFS, and here is the command and here is the measured throughput.** We should actually run that measurement and publish it. An interviewer will trust the measurement more than the claim.

3. **"MinIO was not killed by bad code, and that is the point."** MinIO relicensed from Apache-2.0 to AGPLv3 in 2021, funded a company on top, and when the AI-object-store market did not pay, the community edition was retired. The failure was **business model**, and the code was fine. So the correct response is not "find the next MinIO" - it is *"do not adopt a single-vendor project whose vendor's revenue depends on you not being able to leave."* That principle eliminates MinIO and it eliminates most of the field. What survives it is: a foundation (Ozone, Ceph - both excluded on other grounds), or a project with no relicensing lever **and** a data plane we can copy out of in an afternoon. We chose the latter, and §9 is how we make the "copy out in an afternoon" claim true rather than aspirational.

4. **"We are not betting the platform on the choice."** Every candidate we considered speaks S3, and Iceberg's endpoint configuration is one catalog property per engine. The object store sits behind a single `LAKEHOUSE_S3_ENDPOINT` / `S3_ENDPOINT` pair injected by Dagster into Spark, Flink, ClickHouse and the catalog alike. Swapping is: change the env var, restart, `rclone sync`. **And we prove it** by running the full pipeline against B2 and R2 in CI, not just against the local engine. "Try it on real S3" is the strongest sentence available on this topic, and it costs us one CI job.

5. **"What we gave up, on purpose."** `mc` is gone with the repo and neither pick replaces it well (RustFS has its own `rustfs/cli`; SeaweedFS wants `aws --endpoint-url` or the admin UI). SeaweedFS OSS is **gzip-only** - zstd is Enterprise - so we store 10-30% more bytes than MinIO would have. And SeaweedFS OSS has **no bitrot scrub and no self-healing**; MinIO had continuous hashing in the free edition. We replace the scrubber with a scheduled `rclone check --download` job wired to Prometheus, which is a better artefact to show an interviewer anyway. §8 in full.

**And the question behind the question.** If the interviewer is really asking *"what happens when your storage choice dies too?"* the answer is: we notice, because we automate the detection (§10), and we are out in an afternoon with `rclone sync`, because we never wrote a line of code against a non-S3 interface. That is a stronger position than a team that is still running MinIO.

---

## 7. What the platform loses by not having MinIO

Named, not hand-waved:

| Loss | Severity | Mitigation / decision |
|---|---|---|
| **`mc`** - the best S3 CLI most people have used | Low | Use `aws --endpoint-url` (which is what a real interviewer's laptop has anyway, and it makes the "just S3" claim literal) plus the SeaweedFS admin UI for bucket/user management. RustFS's `rustfs/cli` is the better tool if we ever flip. |
| **Bitrot detection in the free edition** | **Medium-high for a lakehouse** - this is the whole pitch of the product | Scheduled `rclone check --download` (or a `aws s3 sync --dryrun` digest comparison) as a Dagster asset, alerting on drift. Turns a missing feature into a demonstrable control. **Publish the numbers.** |
| **Self-healing / automatic EC repair** | Medium | Enterprise-gated. Not needed at demo scale; state it in the README rather than implying parity. |
| **zstd compression** | **Medium, and measurable** - 10-30% more disk on 231 GB | Quantify it: we will store more Parquet bytes. Mitigate with Iceberg compression (`zstd`/`lz4` *inside* Parquet, which is ours to choose and is where the real win is anyway) and by keeping the working set small. |
| **EC ratio tunability** (SeaweedFS OSS fixed at 10+4 = 1.4x) | Medium | Budget 1.4x. Run the S3 storage-tiering demo (hot local / cold S3) to show we know what the knob would buy. |
| **Console polish / UX** | Low | Irrelevant for a portfolio project; a bonus if we wire the admin UI into the docs. |
| **A universally recognised name** | **Real and underrated** - every question now costs a paragraph | Own it. Lead the write-up with §6. A candidate that needs defending but whose defence is *better* than the incumbent's is a better story than a comfortable answer. |
| **Flink and Spark checkpoint storage** | none - this is an improvement | Do **not** put Flink checkpoints or Spark shuffle on the S3 gateway. SeaweedFS's own Hadoop FS (`seaweedvfs://`) or local disk is correct there. Putting checkpoints behind an S3 API is a classic mistake and avoiding it is worth a line in the design doc. |

---

## 8. Cost and scaling story

**Where the disk wall is.** 231 GB total, minus the OS, the podman graph, and whatever Spark/Flink/ClickHouse scratch need. Call it **~150-160 GB of usable Iceberg warehouse** at SeaweedFS OSS's 1.4x EC overhead. That is a real number to state, and it is a *good* number: it is comfortably more than any demo needs and small enough that the crossover to a managed store is something we can demonstrate rather than speculate about.

**What happens when data outgrows local disk - in order:**

1. **First: Iceberg does the work, not the storage layer.** Partition pruning, sort order, compaction of small files, snapshot expiry. `rewrite_data_files` / `rewrite_manifests` shrink the footprint without moving anything. Demonstrating that *before* reaching for more capacity is the right order of operations and is exactly what the JD asks for ("partitioning, sort order, compaction, retention... to balance write throughput, query performance, and storage cost").
2. **Second: expire snapshots and drop data.** SeaweedFS ships server-side table maintenance (compaction, snapshot expiry, orphan-file removal, manifest rewriting) through the S3 Tables maintenance APIs. Retention policy lives in the platform, not in a bucket lifecycle rule - which is the correct place for a lakehouse, and a good thing to argue in the write-up.
3. **Third: tier cold data to real S3, in-platform.** SeaweedFS has remote/tiered storage to a cloud S3 endpoint configured in the platform. The object store becomes a cache in front of B2/R2 rather than a system of record. Hot Iceberg data stays local; Parquet history goes to B2 at $6.95/TB/month with free egress up to 3x.
4. **Fourth: move the whole warehouse to real S3.** A Dagster job runs `rclone sync` (or `aws s3 sync`) from the local endpoint to the managed one, verifies digests, and then the next run points at the managed endpoint. **Because the endpoint is one env var, this is a config change plus a data copy, and no application code changes.** We should ship this as a runnable script and a documented runbook, because a reviewer will ask to see it.

**The cost arithmetic, so the story is concrete:**

| | Local SeaweedFS | Backblaze B2 | Cloudflare R2 |
|---|---|---|---|
| 150 GB | $0 (hardware amortised) | $1.04/mo | $2.10/mo |
| 1 TB | - | **$6.95/mo** | $15.00/mo |
| 10 TB | - | $69.50/mo | $150.00/mo |
| 1 TB/mo egress | not applicable | $0 (within 3x) | **$0, always** |
| Same at AWS S3, 1 TB + 1 TB egress | - | - | ~$71/mo (~$26 storage + $45 egress) |

**The honest conclusion, which is also the best interview material:** *at this scale, self-hosting was never about cost - it was about control and about not paying egress. The moment egress matters, the free tier and then B2/R2 beat any box we own, and the whole value of the self-hosted tier is that it is a *drop-in*, not a commitment.* Self-hosting is the dev/demo substrate; S3 is the production destination; the engineering work is making the handover boring. Say exactly that.

---

## 9. Moving to real S3 without changing application code - the mechanism

This is worth being pedantic about, because it is the load-bearing claim.

**Every consumer takes the endpoint as a property, and every one of them is a single setting:**

| Consumer | Property | Notes |
|---|---|---|
| Iceberg `S3FileIO` (all engines) | `s3.endpoint` | `S3FileIOProperties.java` |
| Iceberg `S3FileIO` | `s3.path-style-access` | **default `false`** (line 238) - must be `true` for anything that is not DNS-resolvable bucket-style |
| Iceberg `S3FileIO` | `s3.access-key-id` / `s3.secret-access-key` / `s3.session-token` | Also supports catalog-vended credentials via `X-Iceberg-Access-Delegation` - and both SeaweedFS and RustFS implement vending. **Use vended credentials in production**; static keys in the warehouse config are a code smell a reviewer will flag. |
| Spark | `spark.sql.catalog.<n>.s3.endpoint`, `...s3.path-style-access` | via `iceberg-aws-bundle` |
| Flink | `'s3.endpoint'`, `'s3.path-style-access'` | via `iceberg-aws-bundle`; needs both jars on the classpath |
| ClickHouse | `DataLakeCatalog(... ) SETTINGS storage_endpoint = ...` and `IcebergS3('<url>', ...)` | per the ClickHouse guide |
| Hadoop / `s3a://` | `fs.s3a.endpoint`, `fs.s3a.path.style.access=true` | plus `fs.s3a.bucket.probe=0`, `fs.s3a.change.detection.mode=none` |
| `aws` CLI / `rclone` / `boto3` / `pyarrow.fs` | `--endpoint-url` / `endpoint_url` | unchanged |

**The design rules that make the swap real:**

1. **One Dagster resource owns `S3_ENDPOINT`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`, `S3_PATH_STYLE_ACCESS` and injects them into every asset, every Spark/Flink job and the catalog config.** No asset hardcodes an endpoint. This is a one-file change and it is reviewable.
2. **The catalog URI is a separate variable from the S3 endpoint.** `CATALOG_URI` and `S3_ENDPOINT` move independently. That is what lets us use the SeaweedFS catalog in dev and Polaris in prod, or R2 in CI, without touching anything else.
3. **Warehouse paths are `s3://<bucket>/<prefix>` everywhere - never `s3a://`, never a native path.** `s3a://` would tie us to `hadoop-aws` settings and to a Hadoop client; `s3://` is what `S3FileIO`, ClickHouse and PyIceberg all speak natively.
4. **Region is pinned in config even for local runs** (`us-east-1`). Local engines that return a fixed default from `GetBucketLocation` - SeaweedFS and Ozone both do - will otherwise cause SigV4 surprises.
5. **CI runs the pipeline against B2 and R2 in addition to local.** A nightly job, a small synthetic dataset, and an assertion that the same Dagster assets succeed against all three endpoints. This is the artefact that makes §6 prong 4 true instead of aspirational.

**The migration runbook, one screen:**

```
1.  freeze writers; run rewrite_data_files + rewrite_manifests; expire old snapshots
2.  record the source:  aws s3 ls --recursive --endpoint-url $SRC  | sort > before.txt
3.  rclone sync  --transfers 8 --checksum  $SRC_s3:warehouse  $DST_s3:warehouse
4.  record the destination and diff:  < before.txt  vs  after.txt   (must be empty)
5.  point CATALOG_URI + S3_ENDPOINT at the destination; restart Dagster
6.  run the read-side assertion job (row counts per table == expected)
7.  keep the source for one retention window before deleting
```

---

## 10. Is this project at the same risk that ended MinIO? And how would we notice?

**Honest answer: SeaweedFS carries a real version of that risk, and it has already started.** Three concrete facts:

1. **Bus factor 1.** `chrislusf` is 74.8% of commits, and there is no `GOVERNANCE.md` or `MAINTAINERS.md` to distribute authority.
2. **It just went open-core.** `seaweedfs.com` is a paid product with an EULA, a per-TB price and a licence key, and `weed version` advertises it in the binary's own output. The *free core* still has every API we need, but the trajectory is the MinIO trajectory.
3. **It is 12 years old and has never been foundation-governed**, so there is no mechanism - legal or social - that obliges anyone to keep shipping.

**The mitigation is architectural, not a better project choice** - because no candidate is risk-free. Three commitments:

- **(a) The data plane is behind three env vars** (§9). A SeaweedFS sunset is a `rclone sync` and a config change. We can demonstrate this in the repo as a runbook plus a test.
- **(b) The Iceberg path is CI-guarded and we watch those workflows.** Our guarantee rests on `s3tests.yml` (Ceph's own suite, on every `weed/s3api/**` change), `s3-tables-tests.yml`, `s3-spark-tests.yml`, and ClickHouse's guide pinning SeaweedFS **4.42** as a floor. If those stop running, the guarantee is gone.
- **(c) We run the same pipeline against real S3 in CI**, so the escape route is exercised continuously rather than theorised.

**The monitoring, concretely.** Five automated checks, each with a named leading indicator, ordered by how early they fire:

| # | Signal | What it looks like | How often | Why it is early |
|---|---|---|---|---|
| 1 | **Registry reachability** | `GET /v2/<ns>/<name>/tags/list` with a pull token. Non-200 or zero tags. | hourly | **This is the one that would have caught MinIO.** `minio/minio` returned 401/zero tags months before the archive banner. |
| 2 | **Release classification** | Fraction of the last 20 releases that are *not* prerelease. | weekly | MinIO's last 10 releases were all `RELEASE.<date>` on a month end, with no semver. RustFS currently: **99 of the last 100 are prerelease.** A project that stops cutting stable releases is dying. |
| 3 | **Licence and CLA diff** | `git log -p -- LICENSE CLA.md CODE_OF_CONDUCT.md` for any change away from Apache-2.0, or any *new* CLA with a "sole discretion" / relicensing clause. | weekly | This is the MinIO-2021 relicensing tripwire. RustFS's `CLA.md` trips it **today**, which is precisely why it is the fallback and not the primary. |
| 4 | **Open-core drift** | Diff the README and `weed version` output for new "Enterprise Edition" / "contact us" / feature-gate language; watch for S3 or Iceberg operations moving behind a licence. | monthly | The SeaweedFS risk is *feature migration*, not relicensing. Today the Iceberg catalog and all S3 APIs are in the free column - §3.1.8 is the baseline to diff against. |
| 5 | **Bus factor** | Recompute top-1 commit share monthly from the contributors API. | monthly | 74.8% today. A *rise* toward 90% is a wind-down signature; a *fall* is the only good news available. |
| + | **Issue velocity on the Iceberg path** | Open-issue count in `weed/s3api` + `s3-tables-tests.yml` run status | weekly | A CI-guarded guarantee is only a guarantee while CI runs. |

The write-up should publish this table and **run it against both SeaweedFS and RustFS today**, with the 2026-09-27 values filled in, so a reviewer can see the mechanism working rather than promised. That is worth more than any amount of prose about why we picked the safer project - because there isn't one.

---

## 11. Corrections to currently-circulating claims

Recorded because two of these are load-bearing for the platform decision and one of them is in our own `03-longevity-audit.md`.

1. **"SeaweedFS has ~60% S3 API coverage, with versioning, SSE, object lock, lifecycle policies and event notifications all unimplemented."** Source: `dev.to/ethan-carter`, 5 Aug 2026, cited in `03-longevity-audit.md` §3.17.
   **Refuted by primary source.** SeaweedFS's own wiki `Amazon-S3-API.md`, using official AWS operation names, records **86 "Yes" and 33 "No"**, and specifically: `GetBucketVersioning | Yes`, `PutBucketVersioning | Yes`, `ListObjectVersions | Yes`, `Object Versioning | Yes | Yes`, `Object Lock | Yes`, `GetBucketEncryption / PutBucketEncryption | Yes`, `GetBucketCors / PutBucketCors | Yes`, `GetBucketPolicy / PutBucketPolicy | Yes`, `"Conditional Headers (All operations) | Yes"`, and all six multipart operations. Only `PutBucketNotificationConfiguration` is genuinely absent from the Yes set. **This correction matters:** `03-longevity-audit.md` uses it to justify its SeaweedFS caution, and that caution is aimed at the wrong thing. SeaweedFS's real weakness is bus factor and the new open-core split - not S3 coverage.

2. **"Iceberg on S3 needs versioned writes and conditional PUT (`If-Match`) on `metadata.json`."** Same source, same file.
   **Refuted by primary source.** A full-codebase search of `apache/iceberg` for `IfNoneMatch` returns only test and mock files; `S3FileIOProperties.java` exposes no versioning property. Iceberg's optimistic commit is enforced by the *catalog* - `requirements` / `assert-ref-snapshot-id` in `RESTCatalog`, a version column in `HadoopCatalog`/`JdbcCatalog` - not by the object store. **This correction also matters:** it removes the "no versioning" objection as a *correctness* argument, which is why Ozone's missing versioning is damaging to its governance story but not, on its own, fatal to Iceberg. Ozone still fails on bucket policies, CORS, and (as a hedge) the complete absence of conditional requests.

3. **"RustFS is still at 1.0.0-beta.10 (17 Jul 2026), 31.8k stars, 1.4k forks, 27 open issues."** Source: rustfs.com blog listing, cited in `03-longevity-audit.md` §3.18.
   **Superseded.** At 2026-09-27: **33,945 stars, 1,526 forks, 59 open issues**, and `1.0.0` published **2026-09-16** as a non-prerelease - with `1.0.1-preview.9/.10/.11` following on 09-21, 09-22 and 09-24, and a `1.0.1-preview.12` tag on 09-27. The *direction* of `03`'s caution is still right (it is now a 1.0.0 with a preview churn problem, and the CLA is a bigger problem than the beta status), but the specific facts are a month stale.

4. **"MinIO community binaries and Docker images stopped in Oct 2025."** - **confirmed, and stronger than stated.** `minio/minio` returns `401 UNAUTHORIZED` with a pull-scoped token and **zero tags**; there is nothing left to stop. This is a registry fact, not a changelog fact, and it is the right way to phrase it.

5. **"LocalStack Community is a safe, free S3 emulator for tests."** - **no longer true.** `localstack/localstack` is `archived: true`, last release `v4.14.0` (2026-02-26), last commit 2026-03-23, and the README says development is consolidating into a single unified image with the repo *"archived and read-only"* and a **Hobby plan now restricted to non-commercial use**. This is the second project in this report to follow MinIO's path, and the best available argument that the pattern is structural.

---

## 12. Open questions I could not settle from primary sources

Stated rather than guessed.

- **SeaweedFS OSS's real steady-state RSS under an Iceberg write load.** `weed mini`'s defaults are documented and clearly small, but neither the project nor ClickHouse's guide publishes a measured RSS for the combined S3 + Iceberg REST + filer process at Iceberg file counts. **We must measure it** and put the number in the report. This is the one remaining fact that could overturn the recommendation.
- **SeaweedFS's write amplification at Iceberg scale.** The README states the mechanism plainly (a meta-file write per object write, on every drive of the erasure set, not shrinking with object size) but publishes no Iceberg-shaped benchmark. Benchmark it with 1M small Parquet files and publish both systems' numbers.
- **Whether SeaweedFS's Iceberg catalog handles Spark commit *conflicts* correctly under concurrency.** `handlers_commit.go` has a bounded retry loop, which is the right shape, and `s3-spark-tests.yml` exists - but I found no test specifically asserting that two concurrent Spark writers produce exactly one CAS winner. RustFS's matrix *does* assert this ("concurrent writers produce one CAS winner and retryable conflicts") - via a script, not via Spark. **Write this test ourselves**; it is the single highest-value test in the project.
- **SeaweedFS vs R2/B2 on real multipart and checksums.** RustFS's matrix is explicit that R2 is a "profile generator" with *"live interop not claimed."* Nobody publishes the same caveat for SeaweedFS, which may mean it is fine or may mean nobody checked. Run the pipeline against B2 and R2 and find out.
- **Garage's true memory footprint.** Not documented on its site. Irrelevant now that it is rejected on S3 fidelity, but noted for completeness.
- **Ozone's progress on HDDS-13117 (conditional requests).** If it lands, Ozone's verdict changes on fidelity - but not on footprint, which is the binding constraint.

---

## 13. Sources

All accessed 2026-09-27. GitHub facts were read from the GitHub REST API against each project's own repository (not from the HTML UI, which hides `archived` and licence fields).

**GitHub API - repositories, releases, tags, commits, contributors, contents, search**
`seaweedfs/seaweedfs` · `rustfs/rustfs` · `rustfs/helm` · `deuxfleurs-org/garage` · `apache/ozone` · `apache/ozone-docker` · `ceph/ceph` · `minio/minio` · `minio/mc` · `apache/iceberg` · `apache/polaris` · `localstack/localstack` · `getmoto/moto` · `adobe/S3Mock`

**In-repo primary documentation read in full or in part**
- `seaweedfs/seaweedfs`: `README.md`; `.github/workflows/` (80 files, incl. `s3tests.yml` titled "Ceph S3 tests", `s3-spark-tests.yml`, `s3-tables-tests.yml`, `spark-integration-tests.yml`); `weed/command/mini.go`; `weed/command/version.go`; `weed/s3api/iceberg/server.go`, `handlers_commit.go`, `handlers_oauth.go`; `weed/s3api/s3api_iceberg_credentials.go`; `weed/s3api/s3api_object_handlers_put.go`; `weed/s3api/s3api_bucket_config_stubs.go`; `k8s/charts/seaweedfs/Chart.yaml` + `README.md`
- `rustfs/rustfs`: `README.md`; `CLA.md`; `SECURITY.md`; `docs/architecture/s3-compatibility-matrix.md`; `docs/architecture/s3-tables-support-matrix.md`; `docs/architecture/minio-file-format-compat.md`; `docs/architecture/readiness-matrix.md`; `scripts/s3-tests/{implemented,unimplemented,excluded,lifecycle_behavior}_tests.txt`; `helm/rustfs/Chart.yaml`; `.github/workflows/` (14 files)
- `apache/ozone-docker/docker-compose.yaml`
- `apache/iceberg`: `aws/src/main/java/org/apache/iceberg/aws/s3/S3FileIOProperties.java`

**Project documentation sites**
- `raw.githubusercontent.com/wiki/seaweedfs/seaweedfs/Amazon-S3-API.md` (252 lines; the op-by-op table)
- `seaweedfs.com` (Enterprise pricing, open-source-vs-Enterprise comparison table, EULA, support)
- `rustfs.org` / `docs.rustfs.com` (SNSD/SNMD/MNMD, hardware selection, SNSD expansion rule)
- `ozone.apache.org/docs/user-guide/client-interfaces/s3/s3-api/` (v2.2.1); `.../s3a`; `.../administrator-guide/installation/hardware-and-sizing` (page dated 2026-09-21); `.../administrator-guide/configuration/performance/`
- `garagehq.deuxfleurs.fr/documentation/reference-manual/s3-compatibility/` and `/features/`
- `docs.ceph.com/en/squid/start/hardware-recommendations` and `/en/latest/...`; Red Hat Ceph Storage 6 Hardware Guide (containerized minimums)
- `docs.cloudera.com` Ozone s3a and hardware pages
- `clickhouse.com/docs/guides/use-cases/data-warehousing/seaweedfs-catalog` (the decisive first-party integration)
- `cloudflare.com/r2` and `developers.cloudflare.com/r2/pricing`; `backblaze.com/cloud-storage/pricing` and `/transaction-pricing`

**Registry (OCI distribution spec, Docker Hub v2)**
`GET https://registry-1.docker.io/v2/<ns>/<repo>/tags/list` with a pull-scoped bearer token, 2026-09-27:
`minio/minio` **401 / 0 tags** · `chrislusf/seaweedfs` **200 / 1000+ tags / 4 sub-manifests** · `rustfs/rustfs` **200 / 186 tags / 4** · `apache/ozone` **200 / 41 tags / 4** · `quay.io/ceph/ceph` **200** · `garagehq/garage` **401** · `localstack/localstack` **200**

**Helm repositories**
`https://seaweedfs.github.io/seaweedfs/helm/index.yaml` **200**, newest `seaweedfs-4.47.0.tgz` created 2026-09-14T02:50:02Z · `https://rustfs.github.io/rustfs/helm/index.yaml` **404**

**Job posting**
`career-ops/data/jd-cache/031.md` (fetched 2026-09-27) - Debezium CDC -> Kafka; Iceberg on S3 with Apache Polaris REST catalog; Kafka Connect and Flink writing; Spark batch silver/gold; ClickHouse serving; Dagster; AWS/EKS/Terraform/Helm; Prometheus/Grafana/Alertmanager.

**Explicitly *not* used as evidence** (recorded so the omissions are visible): RustFS's own benchmark charts and "vs MinIO / vs other object storage" comparison tables, which are vendor marketing; SeaweedFS's benchmark p50/p99 table on the same grounds; and any blog aggregating S3 API coverage.
