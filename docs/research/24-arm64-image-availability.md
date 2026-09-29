# 24 - arm64 image availability for the pinned components

**Date of research:** 2026-09-29. Every platform entry below was read on 2026-09-29 from the publishing registry's own manifest API, and each row quotes the digest or the exact platform entries observed.

**Scope:** the nineteen components pinned in `docs/technology-selection.md`, asked one question - does the container image each one ships publish a `linux/arm64` manifest, so that a Graviton (m7g) EKS node group can run it? Components that are libraries or toolchain rather than cluster images are named as such and not checked. Only manifest publication is established here; whether an arm64 image starts and works is not. SeaweedFS is included because the assignment asks for it, even though the design uses it local-only. Nothing about pricing or node sizing is restated from 21, 22 or 23.

**Question answered:** which pinned components publish `linux/arm64`, and which must fall back to an x86 node group?

**Ticket:** input to the Graviton-with-per-component-x86-fallback design (no issue number was supplied with this assignment).

## 1. Method, and what "observed" means

For each image the registry's own API was called directly, not a web page, a blog, or a search result:

1. **Docker Hub** - an anonymous pull token from `https://auth.docker.io/token?service=registry.docker.io&scope=repository:<repo>:pull`, then `GET https://registry-1.docker.io/v2/<repo>/manifests/<tag>` with an `Accept` header naming all four manifest media types (OCI index, Docker manifest list, OCI manifest, Docker v2 manifest).
2. **quay.io** - a token from `https://quay.io/v2/auth?service=quay.io&scope=repository:<repo>:pull`, then the same `manifests/<tag>` call.
3. Where the response was an **index / manifest list**, the `platform` block of every child entry is reported verbatim. Where the response was a **single image manifest**, the image's config blob was fetched and its `architecture` and `os` read - a single manifest with no platform list is the signature of a one-architecture image.

Two things are kept distinct in the tables: the **index digest** (the `Docker-Content-Digest` of the multi-arch manifest) and the **platform entries** (what architectures it advertises). The pin says "the latest patch matching the pinned minor", so the tag checked is the newest patch of the pinned minor as it exists in the registry today; the exact tag is in every row.

**A note on `unknown/unknown`.** Most indexes below carry extra entries whose platform is `unknown/unknown`. These are buildkit **attestation manifests** (provenance and SBOM), not operating systems. They are omitted from the platform lists; they do not indicate a platform and do not affect the answer.

**Correction to the assignment's premise (Dagster).** The assignment names `dagster/dagster` as Dagster's image. That repository **does not exist** as a public Docker Hub repository: the tags API returns HTTP 404, and the full repository listing for the `dagster` organisation (29 repositories, read from `https://hub.docker.com/v2/repositories/dagster/`) contains no repository named `dagster`. Dagster's own Docker Compose deployment guide builds the webserver/daemon "host process" image `FROM python:3.10-slim` with `pip install dagster dagster-webserver ...` [S16]; the images the organisation does publish on a 1.13.x cadence are `dagster/dagster-k8s` and `dagster/dagster-celery-k8s` (the Kubernetes host-process images) [S5]. Both were checked and both are arm64-capable. The design therefore needs to name a real Dagster image before this row is settled - see Section 4.

## 2. Component by component

"arm64" means the tag's manifest list advertises `linux/arm64` (or `linux/arm64/v8`, which is the same architecture). Index digests are `sha256:...`; the amd64/arm64 child digests are in Section 3 for the two images that matter.

| # | Component (pin) | Image and exact tag checked | arm64? | Evidence observed on 2026-09-29 |
|---|---|---|---|---|
| 1 | Apache Iceberg 1.11.0 | **not an image** - a table-format library (JARs for Flink/Spark, plus the REST client). Ships no server container. | n/a | n/a |
| 2 | Apache Polaris 1.7.0 | `apache/polaris:1.7.0` | **yes** | OCI index `sha256:3495f67f38cca33892a045f7dd3f46eb52387f0fd52d4145538a772fd8aedad7`; platforms: `linux/amd64`, `linux/arm64` |
| 3 | SeaweedFS 4.47 (local-only) | `chrislusf/seaweedfs:4.47` | **yes** | OCI index `sha256:ce9e796f1fe6f06968f4c04bdaf8f678dad9c8acdfef3d244133d71bfa6bf882`; platforms: `linux/amd64`, `linux/arm64`, `linux/arm/v7`, `linux/386` |
| 4 | Apache Kafka 4.3.1 | `apache/kafka:4.3.1` | **yes** | OCI index `sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837`; platforms: `linux/amd64`, `linux/arm64` |
| 5 | Debezium 3.6.1 | `quay.io/debezium/connect:3.6.1` | **yes** | OCI index `sha256:5a7d3ff04a3d3f2098330b3fb34a6bb6dd3d07de4e09c76b29da13bf6276332a`; platforms: `linux/amd64`, `linux/arm64` |
| 6 | Apache Flink 2.1.3 (java17) | `apache/flink:2.1.3-java17` | **yes** | OCI index `sha256:303377fd46400715e3d4f6feba4443b27e784c5203951dd50c181d36e3893b34`; platforms: `linux/amd64`, `linux/arm64`. (The `2.1.3-scala_2.12-java17` tag resolves to the same index digest.) |
| 7 | Apache Spark 4.1.3 | `apache/spark:4.1.3-java17` | **yes** | OCI index `sha256:9b0a6c2c860f5e7d18dd5270286fef32a09c7f5a7e2b0dbe5642de8a3a02ab3e`; platforms: `linux/amd64`, `linux/arm64`. (Plain `apache/spark:4.1.3` is also amd64+arm64, index `sha256:bf9d035a7c32a8ca46aa58d6348182ffd7d2dff6409206ecfbb3915ff1fef211`.) |
| 8 | ClickHouse 26.8 LTS | `clickhouse/clickhouse-server:26.8.14` (newest 26.8 patch in the registry) | **yes** | OCI index `sha256:4769eec6a9b9842a7d102c8bdfca0400128bc6edf65dec4e19a7d3a2b25f32db`; platforms: `linux/amd64`, `linux/arm64` |
| 9 | PostgreSQL 18.x | `postgres:18.6` (newest 18.x patch) | **yes** | OCI index `sha256:5a5a84b19854a9ffaa54082c166ff4ec27473a361e496e5ea167f298f2da9722`; platforms: `linux/amd64`, `linux/arm64/v8`, `linux/arm/v5`, `linux/arm/v7`, `linux/386`, `linux/ppc64le`, `linux/riscv64`, `linux/s390x` |
| 10 | Dagster 1.13.x | `dagster/dagster` **does not exist**; checked `dagster/dagster-k8s:1.13.24` and `dagster/dagster-celery-k8s:1.13.24` | **yes** (for the images that exist) | `dagster-k8s` OCI index `sha256:b66159cec3ae3c00331f494725ffe75f4aded1f4cdc1082185c5557b054b33fd`, platforms `linux/amd64`, `linux/arm64`; `dagster-celery-k8s` index `sha256:94e5e5dd6da06dd296a40fb8d3bf1e8a323d085214331d3cc018ada613ae5868`, same two platforms. The documented self-build base `python:3.10-slim` is also amd64+arm64 (index `sha256:31dd4d9529d02d7436659061cb7564cd4733fc90e5e152709a942d53382ec8d0`). |
| 11 | Apicurio Registry 3.3.x | `quay.io/apicurio/apicurio-registry:3.3.3` | **yes** | OCI index `sha256:c9cae4c90ce46538abf673c68eb591345f23bcc6c2aa6bfd47189adcf609d8f1`; platforms: `linux/amd64`, `linux/arm64`, `linux/s390x`, `linux/ppc64le`. (The moving `3.3` tag resolves to the same digest.) |
| 12 | OpenLineage 1.53.0 | **not an image** - a lineage-emission spec plus client libraries (Java/Python). No server container; the backend is Marquez. | n/a | n/a |
| 13 | Marquez 0.51.x | `marquezproject/marquez:0.51.1` | **NO** - amd64 only | Single image manifest, not an index: `application/vnd.docker.distribution.manifest.v2+json`, digest `sha256:0721c976cff17d8b14f7949d85d6dac9c7ea37cb9fe857caa19833730fcb1a50`; config blob reports `architecture=amd64`, `os=linux`. `0.51.0` is the same (manifest `sha256:133c1259a3f7677a69319065a6415362dee7d542d5da94622c0c1e4ce2bfed99`). |
| 14 | Prometheus 3.14.0 | `prom/prometheus:v3.14.0` | **yes** | Docker manifest list `sha256:5ce7540c3c00ef4ab0c9d2c995c6a5b9c421f44b4a115d97a2c7af3b1c21cbb0`; platforms: `linux/amd64`, `linux/arm64`, `linux/arm/v7`, `linux/ppc64le`, `linux/riscv64`, `linux/s390x` |
| 15 | Grafana 13.x | `grafana/grafana:13.2.2` (newest 13.x patch) | **yes** | Docker manifest list `sha256:ac461fb352abc50da10a51c7d02462e9c05488f11f53f14b3ad79a8145f638a0`; platforms: `linux/amd64`, `linux/arm64`, `linux/arm/v7` |
| 16 | Alertmanager 0.34.x | `prom/alertmanager:v0.34.1` | **yes** | Docker manifest list `sha256:e9733bafb1bdef9b00e25a21f8f99dc26a22224bf16641ad754d1649f4c3357a`; platforms: `linux/amd64`, `linux/arm64`, `linux/arm/v7`, `linux/ppc64le`, `linux/s390x` |
| 17 | Helm 4.3.0 | **not a cluster image** - client-side packaging tool, run on the operator's machine / CI | n/a | n/a |
| 18 | OpenTofu 1.12.0 | **not a cluster image** - IaC CLI, run on the operator's machine / CI | n/a | n/a |
| 19 | Podman 6.1.x | **not a cluster image** - the local container runtime, not a workload | n/a | n/a |

**Result: of the nineteen components, fourteen ship a container image; thirteen of those fourteen publish `linux/arm64` and one - Marquez - does not.** The other five are not images: Iceberg and OpenLineage are libraries, and Helm, OpenTofu and Podman are toolchain. Marquez's web UI, which is not one of the nineteen but is part of the Marquez deployment, is also amd64-only. SeaweedFS, which is arm64, is local-only in this design.

## 3. The amd64-only images, and what that means for the design

### 3.1 Marquez (API and web UI)

Both Marquez images the design deploys are amd64-only. Research 13 fixes the deployment as the API plus the UI [S15]:

| Image | Tag | Manifest | Architecture |
|---|---|---|---|
| `marquezproject/marquez` | 0.51.1 | single manifest `sha256:0721c976...`, config created 2025-03-27T07:34:55Z | `amd64` |
| `marquezproject/marquez-web` | 0.51.1 | single manifest `sha256:7312112ca0e611b0a37b00d3da6a677485ae4a97622b23d3ae24d849a927868b`, config created 2025-03-27T07:37:50Z | `amd64` |

There is no arm64 tag anywhere in either repository: the full tag lists (read from the registry) end at `0.51.1` for the API and `0.51.1` for the web UI, and every tag is a single-architecture amd64 manifest.

**What else exists, recorded but not recommended:**

- **A third-party fork publishes arm64.** `ilum/marquez` (the ILUM project's fork) publishes an OCI index with `linux/amd64` and `linux/arm64` at tags `0.52.0`, `0.53.0`, `0.53.1`, `0.53.2`, `0.54.0` and `latest` (`0.54.0` index `sha256:6e1d709d41f8a4f7ea7a39927aa3083ee1e99a8cdeb93d7f5287f088e44e1ae7`). Its version numbers have diverged from upstream (it is already at 0.54.0 while upstream's newest is 0.51.1), and it is a fork rather than the MarquezProject release. It does **not** publish the pinned 0.51.x line, and no arm64 image of `marquez-web` was found.
- **A self-build is mechanically possible.** The official `Dockerfile` builds `FROM eclipse-temurin:17` and produces a Gradle shadow JAR [S13]; `eclipse-temurin:17` publishes `linux/arm64` (index `sha256:b64592d40959b4d13b218f6b06b9ab219ff8aa3dad61efd3b5f519ba4d72ef92`), and the shadow JAR is architecture-independent Java bytecode, so an arm64 build of the same source is a matter of `buildx --platform linux/arm64`. Neither a self-built API image nor a self-built web image was built or run for this note, and the web UI is a separate Node build whose arm64 behaviour was not checked.
- **Two upstream arm64 issues exist and are both closed as completed** (`#2755` "Cannot run Docker Backend on Mac", closed 2024-02-23, and `#1818` "Error when running marquez-api on Apple M1", closed 2022-01-07) [S14]. Their closure does not change the registry fact: the published 0.51.1 image is amd64-only. They are recorded only because they are the closest thing to an upstream position on arm64.

**Consequence for the design.** Marquez is the **only** component that forces an x86 fallback. Every other cluster workload - Polaris, Kafka, Debezium, Flink, Spark, ClickHouse, Postgres, Dagster, Apicurio, Prometheus, Grafana, Alertmanager, and (were it cluster-hosted) SeaweedFS - can run on a Graviton node group as published. If the design wants a Graviton-only cluster, the choices are to schedule the two Marquez pods onto a small amd64 node group, to drop the Marquez web UI, or to build Marquez for arm64 - none of which this note decides. This also lands on ground the technology selection already prepared: Marquez is recorded there as a swappable backend behind the OpenLineage transport with a stalled release cadence, so a single-architecture image is one more reason it is the least load-bearing of the cluster components. The measured consequence for node-group sizing (one amd64 node for Marquez) belongs with the pricing work in 21-23, not here.

### 3.2 Nothing else

No other pinned image is amd64-only. In particular the two that were most likely to be single-architecture - ClickHouse and Flink - are both multi-arch, and Polaris, which is the newest and least mature of the server images, publishes arm64.

## 4. Not confirmed / limitations

- **Manifest publication only.** This note proves that a `linux/arm64` manifest is *published* for each image. It does not prove the arm64 image starts, passes its health check, or behaves identically. Nothing was pulled, run, or exercised. That is a container-verification step, not a registry-read step, and it is not claimed here.
- **Dagster's image is unresolved.** `dagster/dagster` does not exist, so the design's Dagster row cannot be closed until the real image is named. The two published 1.13.x images (`dagster-k8s`, `dagster-celery-k8s`) are arm64, and the documented self-build base `python:3.10-slim` is arm64, so the arm64 answer is not in doubt; the *image name* is.
- **The Dagster Kubernetes images were used as the nearest published stand-in.** They are the org's 1.13.x host-process images, but a podman-compose deployment on the host would more likely build its own image from `python:3.10-slim`. Both were checked; neither is a claim about the design's final Dockerfile.
- **Marquez arm64 substitutes were inspected, not evaluated.** The ILUM fork's arm64 images and the feasibility of a self-build are recorded because the assignment asks what exists. Neither was built, pulled, or run, and neither is recommended here. Whether the ILUM fork is a faithful drop-in, and whether it speaks the same OpenLineage API version the pinned 0.51.x does, is not established.
- **Marquez Web's arm64 status rests on the API check plus the absence of an arm64 tag.** `marquez-web` was checked at 0.51.1 and is amd64-only; its Dockerfile was not read, so a self-build path for the UI is asserted only as "not checked".
- **The tag checked for each minor-pinned component is the newest patch present in the registry today**, not necessarily the patch the design will pin. ClickHouse 26.8.14, Postgres 18.6, Grafana 13.2.2, Dagster 1.13.24, Marquez 0.51.1 and Apicurio 3.3.3 were the newest at read time. A future patch is a new manifest and would need re-reading.
- **quay.io config/blob metadata was not read.** The quay blob endpoint returned 404 under the anonymous token used, so for Debezium and Apicurio the platform entries come from the manifest index (which is the authoritative platform source) but the per-image `created` timestamp was not captured.
- **`linux/arm64` and `linux/arm64/v8` are treated as the same architecture**, which they are for Graviton. Postgres advertises the `v8` variant spelling; the others advertise plain `arm64`.
- **The design's runtime base images were not audited beyond Dagster and Marquez.** A component's image being multi-arch does not guarantee every sidecar or init container in its deployment is; that is a per-manifest question for the deployment work, not the component pins.

## 5. Sources

All accessed 2026-09-29. Registry calls are anonymous and were made against the registry's own API; the tag checked is named in each table row.

- [S1] Docker Hub registry manifest API - `https://registry-1.docker.io/v2/<repo>/manifests/<tag>`, authenticated with `https://auth.docker.io/token?service=registry.docker.io&scope=repository:<repo>:pull`. Used for `apache/polaris:1.7.0`, `chrislusf/seaweedfs:4.47`, `apache/kafka:4.3.1`, `apache/flink:2.1.3-java17` and `apache/flink:2.1.3-scala_2.12-java17`, `apache/spark:4.1.3-java17` and `apache/spark:4.1.3`, `clickhouse/clickhouse-server:26.8.14`, `library/postgres:18.6`, `dagster/dagster-k8s:1.13.24` and `dagster/dagster-celery-k8s:1.13.24`, `marquezproject/marquez:0.51.1` and `0.51.0`, `marquezproject/marquez-web:0.51.1`, `prom/prometheus:v3.14.0`, `grafana/grafana:13.2.2`, `prom/alertmanager:v0.34.1`, `library/python:3.10-slim`, `library/eclipse-temurin:17`.
- [S2] Docker Hub tags API - `https://registry-1.docker.io/v2/<repo>/tags/list` (and `https://hub.docker.com/v2/repositories/<repo>/tags`). Used to establish the newest patch of each pinned minor and to show that Marquez and marquez-web have no arm64 tag.
- [S3] quay.io registry manifest API - `https://quay.io/v2/<repo>/manifests/<tag>`, authenticated with `https://quay.io/v2/auth?service=quay.io&scope=repository:<repo>:pull`. Used for `debezium/connect:3.6.1` and `apicurio/apicurio-registry:3.3.3` and `3.3`.
- [S4] Docker Hub organisation listing - `https://hub.docker.com/v2/repositories/dagster/` (29 repositories; no `dagster/dagster`), and `https://hub.docker.com/v2/repositories/dagster/dagster/tags` returning HTTP 404.
- [S5] Docker Hub tags - `dagster/dagster-k8s` and `dagster/dagster-celery-k8s`, newest 1.13.24 (published 2026-09-21), confirming the org's live 1.13.x image names.
- [S6] Docker Hub search API - `https://hub.docker.com/v2/search/repositories/?query=marquez`, used to find the community images; `ilum/marquez` manifest index checked at 0.54.0 (`sha256:6e1d709d...`) and `latest`.
- [S7] Docker Hub tags - `ilum/marquez` (`0.52.0`, `0.53.0`, `0.53.1`, `0.53.2`, `0.54.0`, `latest`), the only arm64 Marquez build found.
- [S8] Docker Hub tags - `marquezproject/marquez` and `marquezproject/marquez-web`, full lists ending at 0.51.1 (no arm64 tag).
- [S9] ClickHouse tag list - `clickhouse/clickhouse-server`, newest 26.8 patch = 26.8.14.
- [S10] PostgreSQL tag list - `library/postgres`, newest 18.x patch = 18.6.
- [S11] Grafana tag list - `grafana/grafana`, newest 13.x patch = 13.2.2.
- [S12] Apache Flink and Apache Spark tag lists - `apache/flink` (2.1.3 java17 variants) and `apache/spark` (4.1.3 java17 variants).
- [S13] MarquezProject/marquez - `Dockerfile` on `main` - https://raw.githubusercontent.com/MarquezProject/marquez/main/Dockerfile (`FROM eclipse-temurin:17`; builds `:api:shadowJar`).
- [S14] MarquezProject/marquez - arm64-tagged issues - https://github.com/MarquezProject/marquez/issues?q=arm64 (`#2755` "Cannot run Docker Backend on Mac", closed 2024-02-23; `#1818` "Error when running marquez-api on Apple M1", closed 2022-01-07).
- [S15] `docs/research/13-lineage-backend-comparison.md` - fixes the deployment as `marquezproject/marquez:0.51.1` (API) plus `marquezproject/marquez-web:0.51.1` (UI), with the OpenSearch service skipped.
- [S16] Dagster documentation - Deploying Dagster using Docker Compose - https://docs.dagster.io/deployment/oss/deployment-options/docker (`FROM python:3.10-slim` + `pip install dagster dagster-graphql dagster-webserver dagster-postgres dagster-docker`; no official `dagster/dagster` runtime image).
- [S17] `docs/technology-selection.md` - the nineteen components and their pins, which define the rows of Section 2.
- [S18] `docs/research/21-aws-pricing-snapshot.md`, `22-aws-network-and-address-pricing.md`, `23-aws-larger-graviton-prices.md` - the pricing companions; nothing here restates their figures.
