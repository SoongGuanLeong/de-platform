# Cloud architecture and cost: the AWS shape, the 10x and 100x reasoning

**Ticket:** [Cloud topology and cost: the AWS shape and the 10x and 100x reasoning](https://github.com/SoongGuanLeong/de-platform/issues/17)
**Map:** [The Research & Architecture Proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Decision record:** [ADR-0027](adr/0027-self-host-what-the-platform-operates.md)
**Pricing sources:** [research 21](research/21-aws-pricing-snapshot.md), [research 22](research/22-aws-network-and-address-pricing.md), [research 23](research/23-aws-larger-graviton-prices.md), [research 24](research/24-arm64-image-availability.md)

**Every figure in this document is either an AWS list price with its publication date, or arithmetic over those prices. Nothing here was measured on AWS, because nothing here was applied.** The one measured axis, cost per GB ingested, is a local measurement defined in section 7.5 and not yet taken.

## 1. The posture: authored, not applied

The platform must be entirely free to run. The finding that decides the posture is that **the EKS control plane at $0.10 per cluster-hour is the only line item that cannot be reduced to zero**: it has no free tier, is not free-plan-eligible, and bills every hour the cluster exists, whether or not a node runs. RDS `db.t4g.micro` *is* free-plan-eligible, so RDS is not the floor.

Three postures were considered and the second was taken:

| Posture | Cash | Rejected because |
|---|---|---|
| (a) Authored-only, never run | $0 | Gives up the costed demo runbook, which is cheap to author and answers the mission's own "how would you deploy this" question |
| **(b) Authored-only as the evidence base, plus a priced, time-boxed, torn-down demo runbook** | **$0 by default; about $2.61 for a 6-hour session** | **taken** |
| (c) A running minimal deployment | about $246/month | Breaks the free-to-run constraint, and the local stack already demonstrates the runtime |

So the EKS topology is authored and statically validated, and a cluster is only ever *run* inside an optional, bounded, destroyed-afterwards demo. No claim in this proposal rests on AWS spend.

## 2. The AWS shape

### 2.1 Region and account

**ap-southeast-5 (Asia Pacific / Malaysia)** is the modelled region, because it is where the target employer would deploy; us-east-1 is carried throughout as a cheaper comparison. ap-southeast-5 has three Availability Zones, and the regional multiplier is a constant 1.0625x us-east-1 across the m7g sizes verified in research 23.

One account. Cross-region and multi-account design is out of scope on the map, so no account topology is authored beyond a single account with one VPC per arm.

### 2.2 Network

| | Minimal arm | Reference arm |
|---|---|---|
| Availability Zones | **2** (the EKS floor) | 3 |
| VPC | `10.0.0.0/16` | `10.1.0.0/16` |
| Subnet tiers | public only | public and private, per AZ |
| Egress | internet gateway | one NAT gateway per AZ |
| Object storage path | S3 **gateway endpoint** (free) | S3 gateway endpoint |

**Why the minimal arm has no NAT and no interface endpoints.** A private-subnet cluster with no NAT needs interface endpoints, and interface endpoints bill per endpoint-AZ-hour: `ecr.api`, `ecr.dkr`, `secretsmanager`, `sts` and `logs` across two AZs is $0.1170/hour in ap-southeast-5. One NAT gateway is $0.0502/hour; two, one per AZ, is $0.1003/hour. Public subnets plus the internet gateway plus the free S3 gateway endpoint is **$0.0100/hour** for two public IPv4 addresses. The option chosen to avoid NAT is therefore the most expensive of the three, and the recorded round-1 rationale that said "no NAT, VPC endpoints only" as a saving has been corrected.

EKS requires at least two subnets in two different Availability Zones, so the minimal arm's floor is two AZs, not one. Both subnets must support DNS hostname and DNS resolution or nodes cannot register.

Subnet sizing is a **verification item, not a settled figure**: EKS hands pods secondary IP addresses from the node's own subnet, so the usable pod count per node is bounded by the ENI and secondary-IP ceiling for the instance type. The public /24s in the minimal arm are sized against that ceiling and the runbook checks it, with a /22 as the fallback if a profile's pod count exceeds a /24. The reference arm's private /20s are headroom.

### 2.3 Compute

**EKS, default control plane, managed node groups.** Kubernetes version pinned to one inside standard support: extended support is $0.60 per cluster-hour, six times standard, and is a silent multiplier on the only fixed cost. The default control plane is deliberate, and the alternatives are rejected in section 5.5.

| | Minimal arm | Reference arm |
|---|---|---|
| Node groups | **1**, spanning both AZs, untainted | **2**: `general` (untainted) and `data` (tainted for Kafka, ClickHouse, Flink TaskManagers) |
| Nodes | 2 (3 for the demo's streaming profile) | 2 general + 3 data |
| Instance type | `m7g.large` | `general`: `m7g.large`; `data`: `m7g.xlarge` |
| Capacity type | on-demand | on-demand |
| Scaling | group min 2 / max 3, no autoscaler | group min/max declared, no autoscaler |

**Graviton, and the one component that forced a decision.** `m7g` is about 19% below the equivalent `m7i` x86 size, and research 24 verified the linux/arm64 manifest for 13 of the 14 components that ship an image. The single exception is **Marquez**: `marquezproject/marquez:0.51.1` and its web UI publish amd64 only. A managed node group has a single AMI type, so the fallback cannot be per-pod. The arm is kept homogeneous by **building Marquez for arm64 from its own upstream Dockerfile at the pinned 0.51.1 tag** (`FROM eclipse-temurin:17`, which publishes arm64, building an architecture-neutral shadowJar), pinned by digest with the build provenance recorded. The x86 general group is documented but **not authored**, with its cost as the trigger if that build fails.

**No autoscaling controller.** Neither Cluster Autoscaler nor Karpenter is authored: neither can be evidenced at demo scale, and both add a component to a stack the mission's sprawl test already constrains. The node groups declare min and max and nothing scales them. This is a documented gap with a trigger, not an oversight.

**No Spot.** Research 21 could not confirm per-family spot prices from any live unauthenticated source, and an interruption inside a few-hour demo would invalidate the only live run the design permits. Spot is a documented gap with a trigger: a credentialed `DescribeSpotPriceHistory`, and a demo that can tolerate interruption.

### 2.4 Identity

**IRSA, one role per component, least privilege.** Every workload assumes its own IAM role through its Kubernetes service account; there are no static keys in the cluster. The **node instance role carries no S3 and no Secrets Manager permissions**, so a compromised pod cannot borrow the node's identity, and IMDS is restricted to a hop limit of 1. The role topology is expressed as data (a per-component policy file under `deployment/`) rather than as code, so the boundary is reviewable as a diff.

Cluster add-ons are the required set only, each with its own IRSA role: VPC CNI, CoreDNS and kube-proxy (defaults), the **EBS CSI driver** (gp3 PVCs need it), and the **Secrets Store CSI driver** (which projects Secrets Manager values, per the placement decision). The **AWS Load Balancer Controller** is authored for the reference arm only, because only the reference arm has an ALB. Add-ons are infrastructure and do not enter the technology count.

### 2.5 The vended-credential boundary

This is the boundary the platform already proved against SeaweedFS, and the cloud shape mirrors it exactly rather than reinventing it. Polaris assumes a vending role and attaches an inline session policy scoped to the table's prefix:

- `s3:GetObject` and `s3:GetObjectVersion` on `arn:aws:s3:::<warehouse-bucket>/<prefix>/*`
- `s3:ListBucket` on the bucket, gated by `Condition: StringLike s3:prefix = "<prefix>/*"`
- `s3:GetBucketLocation`

Two boundaries carry over from the measured local result and are recorded as design constraints rather than rediscovered in the cloud:

1. **The 2048-byte session-policy budget.** An oversized inline policy is refused before any session is issued, which caps how many table locations one session policy can enumerate.
2. **The boundary is a prefix boundary, not a table-identity boundary.** If two tables' locations nest, or if a writer points `write.data.path` at a broader prefix inside the catalog's `allowedLocations`, the vended scope widens with the prefix.

Because nothing is applied, the second is enforced by a **static policy-scan rule**: every table location must be a distinct, non-nesting prefix under the warehouse root. The local test's permissive `Principal: "*"` trust policy and admin caller were its own recorded residual uncertainties, so the cloud shape tightens both: the vending role's trust policy names Polaris's IRSA role as the only principal.

### 2.6 Storage

**Bucket per concern**, because lifecycle, versioning and IAM policy differ per concern and a single bucket forces those differences into prefix policies that are harder to audit. One CMK per bucket.

| Bucket | Holds | Why it is separate |
|---|---|---|
| `<prefix>-lake` | the Iceberg warehouse at `warehouse/<spine>/<layer>/<table>/`, the raw landing zone at `raw/<source>/`, and quarantine as a prefix | Versioned, and the per-table prefix is the unit Polaris vends a credential against, so the layout and the IAM boundary are the same boundary |
| `<prefix>-flink` | Flink checkpoints and savepoints | High churn, short lifecycle, a different writer |
| `<prefix>-kafka` | Kafka tiered storage | Would let the time-bounded CDC history outlive broker disk. Authored as an option; no requirement depends on it |
| `<prefix>-platform` | OpenTofu state and logs | Different lifecycle and a different access set from anything above |

The prefix convention mirrors Polaris's spine-then-layer namespace and ClickHouse's mirror of it, so one path is the same path in three systems. Quarantine stays a prefix inside `-lake` rather than its own bucket, because it is an Iceberg table and a second warehouse root would widen the catalog's `allowedLocations` and with it every vended credential.

**RDS carries the platform metadata, and the OLTP source is separate in the reference arm.** One `db.t4g.micro` instance holds separate databases for Polaris, Dagster, Apicurio and Marquez in the minimal arm, with the documented risk that the TPC-C fixture's load shares an instance with the catalog's metastore. The reference arm splits them: the CDC source and the metadata store are two instances, so fixture load cannot degrade catalog availability.

### 2.7 Workload kinds and namespaces

Kubernetes namespaces mirror the repository's engineering paths, because the repository decomposition already made the toolchain and runtime the real seam.

| Namespace | Workloads |
|---|---|
| `streaming` | Kafka (StatefulSet, PVCs), Debezium (Deployment, Kafka Connect distributed), Flink operator and its three FlinkDeployment CRs |
| `batch` | Spark, submitted by Dagster with `spark-submit` on Kubernetes |
| `serving` | ClickHouse (StatefulSet, PVCs) |
| `governance` | Apicurio, Marquez |
| `orchestration` | Dagster webserver, daemon and user-code Deployments |
| `platform` | Polaris (Deployment plus bootstrap Job) |
| `observability` | Prometheus and Alertmanager (StatefulSets, PVCs), Grafana (Deployment, dashboards from ConfigMaps) |

No Strimzi, no ClickHouse Operator, no Spark Operator, no Prometheus Operator: each either replaces an artefact the platform is demonstrating or adds a component, and plain Helm charts cover the workloads.

## 3. The local-to-cloud mapping

The nineteen are the application components the platform runs. Their cloud forms are not additions.

| Component | Local form | Cloud form | Workload kind |
|---|---|---|---|
| Apache Iceberg 1.11.0 | library | library | n/a |
| Apache Polaris 1.7.0 | container | Deployment + bootstrap Job, metastore on RDS | Deployment |
| SeaweedFS 4.47 | `weed mini` | **S3** | managed |
| Apache Kafka 4.3.1 | container, KRaft | StatefulSet, 1 broker minimal / 3 reference | StatefulSet |
| Debezium 3.6.1 | container | Kafka Connect Deployment | Deployment |
| Apache Flink 2.1.3 | container | Flink Kubernetes Operator + 3 FlinkDeployment CRs | Operator + CRs |
| Apache Spark 4.1.3 | container | `spark-submit` on Kubernetes, driven by Dagster | Job |
| ClickHouse 26.8 LTS | container | StatefulSet, 1 replica minimal / 2 reference | StatefulSet |
| PostgreSQL 18.x | container | **RDS** | managed |
| Dagster 1.13.x | container | webserver + daemon + user-code Deployments | Deployments |
| Apicurio Registry 3.3.x | container | Deployment, Postgres on RDS | Deployment |
| OpenLineage 1.53.0 | library | library | n/a |
| Marquez 0.51.x | container | Deployment, **arm64 image self-built from the upstream Dockerfile** | Deployment |
| Prometheus 3.14.0 | container | StatefulSet, PVC | StatefulSet |
| Grafana 13.x | container | Deployment, dashboards from ConfigMaps | Deployment |
| Alertmanager 0.34.x | container | StatefulSet, PVC | StatefulSet |
| Helm 4.3.0 | CLI | CLI | n/a |
| OpenTofu 1.12.0 | CLI | CLI | n/a |
| Podman 6.1.x | container runtime | containerd, via EKS | n/a |

**Infrastructure, not components**: ECR (the `reference` profile only, never created by the demo window), the internet gateway, the S3 gateway endpoint, the AWS Load Balancer Controller and the ALB (reference arm only), NAT gateways (reference arm only), Secrets Manager, the EBS and Secrets Store CSI drivers, the Flink Kubernetes Operator, Spark-on-Kubernetes, the OpenTofu state bucket, and the node groups themselves. None of these is an addition to the nineteen.

## 4. The cost model

Method: on-demand list prices only, no Savings Plan, no Reserved Instance, no Enterprise Discount Programme, in USD. Every unit price traces to a numbered source in research 21, 22 or 23 with that source's publication date. Where a price could not be confirmed from a live source, this document carries no number for it and says so.

### 4.1 The minimal arm

One EKS cluster, 2 AZs, public subnets, one managed node group, 2 x `m7g.large`, RDS `db.t4g.micro` Single-AZ, 200 GB gp3, 20 GB RDS storage, 100 GB S3, one secret, no ALB, no NAT, no interface endpoints.

| Line item | us-east-1 /hr | ap-southeast-5 /hr |
|---|---|---|
| EKS control plane | 0.100000 | 0.100000 |
| 2 x m7g.large | 0.163200 | 0.173400 |
| RDS db.t4g.micro, Single-AZ | 0.016000 | 0.023000 |
| RDS 20 GB gp3 | 0.003151 | 0.003397 |
| EBS 200 GB gp3 | 0.021918 | 0.023671 |
| S3 100 GB Standard | 0.003151 | 0.003082 |
| Secrets Manager, 1 secret | 0.000548 | 0.000548 |
| Public IPv4 x 2 | 0.010000 | 0.010000 |
| **Total** | **0.317968** | **0.337098** |

| Window | us-east-1 | ap-southeast-5 |
|---|---|---|
| 6 hours, torn down | $1.91 | $2.02 |
| 24 hours, torn down | $7.63 | $8.09 |
| 30 days, left running | $232 | $246 |

### 4.2 The reference arm

Three AZs, private subnets, one NAT gateway per AZ, an ALB, `general` 2 x `m7g.large` plus `data` 3 x `m7g.xlarge`, multi-AZ RDS, 600 GB EBS, 50 GB RDS storage, 500 GB S3, five secrets, nine public IPv4 addresses (five nodes, three NAT gateways, and the ALB's, budgeted).

| Line item | us-east-1 /hr | ap-southeast-5 /hr |
|---|---|---|
| EKS control plane | 0.100000 | 0.100000 |
| general 2 x m7g.large | 0.163200 | 0.173400 |
| data 3 x m7g.xlarge | 0.489600 | 0.520200 |
| NAT gateway x 3 | 0.135000 | 0.150450 |
| ALB | 0.022500 | 0.022700 |
| RDS db.t4g.micro, Multi-AZ | 0.032000 | 0.046000 |
| RDS 50 GB gp3, Multi-AZ | 0.015753 | 0.016986 |
| EBS 600 GB gp3 | 0.065753 | 0.071014 |
| S3 500 GB Standard | 0.015753 | 0.015411 |
| Secrets Manager, 5 secrets | 0.002740 | 0.002740 |
| Public IPv4 x 9 | 0.045000 | 0.045000 |
| **Total** | **1.087299** | **1.163901** |

| | us-east-1 | ap-southeast-5 |
|---|---|---|
| Per hour | $1.09 | $1.16 |
| 30 days, left running | $794 | $850 |
| Multiple of the minimal arm | 3.42x | **3.45x** |

**The reference arm costs three and a half times the minimal arm, not two to three times as an earlier estimate had it.** Its three NAT gateways alone are $0.150/hour, which is 11% of the arm and more than an entire `m7g.large` node: the reference arm's cost is dominated by redundancy plumbing rather than by compute. Putting the larger node in the data group only, where the memory pressure is, is what keeps it at 3.45x rather than 4.0x.

### 4.3 The demo

The demo runs the minimal arm with **3 nodes** (the third for the streaming profile's Flink and ClickHouse footprint), for about **6 hours**, in ap-southeast-5: **$2.61**. That is roughly 76 sessions inside a new account's $200 credit pool, which is a one-time, non-extendable allowance: $100 on sign-up plus up to $100 for activities, a free plan lasting six months or until the credits are exhausted, and credits expiring 12 months after account creation.

Guardrails, all mandatory: an **AWS Budgets cost alarm at $5** with an email action; a **one-working-session time box**; and a teardown checklist whose last steps are `tofu destroy` followed by a verification that the four things which bill while idle are gone - the EKS cluster, the NAT gateways, the ALB, and any unattached public IPv4 address.

### 4.4 Traps

- **EKS extended support is $0.60 per cluster-hour**, six times the standard rate, if a Kubernetes version is pinned past its support window.
- **The control plane bills whether or not a node runs.** It is the reason a "stopped" demo still costs money.
- **A stopped RDS instance still bills compute.** It is stopped for at most 7 consecutive days before AWS restarts it, so stopping is not a way to make RDS free.
- **An idle public IPv4 address bills at $0.005/hour**, the same rate as an in-use one.
- **NAT Gateway bills per hour and per GB processed**, $0.05015 each in Malaysia. A chatty pod can outspend its own compute through NAT.
- **Egress to the internet is $0.108/GB** in Malaysia for the first 10 TB, with 100 GB/month free. Pulling a serving copy down to a laptop is a costed action.
- **The demo's cost is not the rate, it is forgetting the teardown.** A month of neglect is $246, which exhausts the entire credit pool and starts billing.

### 4.5 Silent multipliers, rejected

The EKS price list carries opt-in charges that would each multiply the fixed cost. The design takes none of them, and says so because they are the kind of line item that appears after provisioning: **Provisioned Control Plane** at $1.65 to $13.90 per cluster-hour depending on tier; **EKS Auto Mode** at per-instance management hours (`m7g.large` $0.0104/hour in ap-southeast-5) on top of the node; **EKS Capabilities**, which includes a managed Argo CD at $0.029108/hour plus $0.001452 per custom-resource-hour in ap-southeast-5; and **extended support**. Managed node groups and EKS add-ons themselves carry no charge beyond the control plane.

## 5. How would you make this free

The honest chain, because this is one of the mission's own interview questions:

**The EKS control plane is the only unbudgeable line item, so $0 requires dropping EKS.** Everything else can be driven to zero by design - no NAT, no ALB, public subnets, single-AZ RDS, no autoscaler - but the control plane cannot, because it has no free tier and is not free-plan-eligible. Three ways to drop it:

1. **Run Kubernetes locally.** The platform already does. This is the genuinely $0 runtime, and it is where every correctness claim is evidenced. What is lost is nothing, because no correctness claim depends on EKS.
2. **Run a single Free-Tier EC2 instance with k3s.** `t4g.micro` and `t4g.small` are free-plan-eligible, so the compute is covered. What is lost is the managed control plane, the managed node groups and the IRSA integration - that is, most of the topology the demo exists to show.
3. **Run the control plane outside AWS.** Possible, and it forfeits the JD-named EKS requirement that M19 exists to evidence.

**Headline: the platform is free to run as a design at $0, free to run as a demo only inside the credit window, and genuinely $0 at runtime only on the local compose stack.** Public IPv4 is not covered on a new account at all - the free allowance is a legacy 12-month tier benefit - so even a "free" demo spends a few cents of credit on addresses. Pretending an EKS deployment is free would be the one dishonest claim available here, and the cost model is a better portfolio artefact than a screenshot.

## 6. The 10x and 100x reasoning

### 6.1 The axis and the budget

Scale moves **volume and rate together**, because scaling volume alone would understate the streaming path, which is rate-bound rather than size-bound.

| | Volume | Iceberg | ClickHouse | Postgres | TPC-H | RIPE |
|---|---|---|---|---|---|---|
| Today (budget) | about 100 GB | 60-80 GB | 15-25 GB | 10 GB | 26 GB | 5 GB |
| 10x | about 1 TB | | | | | |
| 100x | about 10 TB | | | | | |

The five retention data classes in `docs/governance-and-data-quality.md` are the storage-growth inputs, because each carries a different retention rule and therefore a different growth curve.

### 6.2 What breaks first at 10x

1. **Compaction compute and S3 request cost.** File count grows with ingest rate, and every commit writes a manifest, so both the requests billed per 1,000 and the compute spent rewriting small files grow faster than the bytes do. This is why the one measured axis is cost per GB ingested rather than cost per GB stored.
2. **Flink state size.** The keyed operator holding the maximum `source.lsn` per key grows with key cardinality rather than with volume, and its RocksDB state is checkpointed to S3. Checkpoint duration, not throughput, is what fails first - which is why a checkpoint timeout is one of the incident laboratory's scenarios.
3. **ClickHouse part count and Kafka retention.** Both are configuration changes rather than architecture changes, and both are already named as budgets.

### 6.3 What breaks first at 100x

1. **The Iceberg metadata plane.** Manifest lists and snapshots grow with commit count, and every planning step reads metadata, so snapshot expiry stops being hygiene and becomes load-bearing.
2. **Polaris catalog contention.** One catalog serving concurrent planning requests becomes the throughput bottleneck, and this is the point at which a read-through architecture would fail while the materialised serving store holds.
3. **ClickHouse merge throughput**, then **Kafka per-broker partition and replication throughput**.

### 6.4 How each layer grows

| Layer | Grows with | Shape |
|---|---|---|
| Object storage | volume | linear |
| Compute (Flink, ClickHouse merges, compaction, Spark) | rate | with rate |
| S3 requests | file count, which rises with rate | **superlinear unless compaction keeps pace** |
| Catalog metadata | commit count | superlinear |

The requests line is the one place the curve bends, and it is the reason the measured axis was chosen where it was.

### 6.5 What is measured, and what is extrapolated

**Measured, locally, on the pinned profile**: objects written, bytes written, and compaction work per GB of CDC ingested. This is the only number the platform produces itself, and it feeds the two lines that dominate a lakehouse bill at 10x - S3 request cost and compaction compute.

**Extrapolated, and labelled so**: every figure in sections 6.1 to 6.4 above, the per-layer cost growth classification, and the constraint ordering. No AWS cost was measured, and no benchmark was run. A claim that fits no profile is a design claim, not evidence.

## 7. What is authored versus applied

| Artefact | Location | Validation |
|---|---|---|
| OpenTofu modules | `deployment/` | `tofu fmt -check`, `tofu validate`, `tflint` |
| Two tfvars profiles, `reference` and `minimal` | `deployment/` | the policy scan below |
| Policy scan | `deployment/` | `trivy config`, including the non-nesting table-prefix rule ([the CI/CD strategy](ci-cd-strategy.md) section 10) |
| Helm charts | `deployment/` | `helm lint`, `helm template` against a test values file |
| Rendered manifests | `deployment/` | `kubeconform` against a pinned schema |
| Demo runbook | `deployment/` | not validated by CI; it is a human procedure |
| The minimal arm itself | the priced demo window | **applied only by a human inside the window, and never as evidence** |
| The reference arm | nowhere | **never applied** |

**No `tofu plan` and no `apply` in CI, no LocalStack.** Both need a real account, and LocalStack was already rejected. The only apply anywhere is a human running the demo runbook inside the priced window, and that is not an evidence item. The static checks are the only evidence M19 can produce, so the gate is the deliverable rather than a preliminary to one.

## 8. Verification items and documented gaps

Carried forward rather than silently assumed:

- **Subnet sizing against the ENI and pod-density ceiling** for the chosen instance types, with a /22 as the fallback.
- **The arm64 self-build of Marquez**, which is mechanically supported but has not been built or run. The x86 general group is the documented trigger, at about $29.78/month.
- **ARM64 manifest publication is verified; arm64 execution is not.** The host is `x86_64`, so no arm64 image can be run locally without emulation. This is a documented limitation, not a pending decision.
- **KMS CMK pricing is absent from the research set.** One CMK per bucket is four keys in the minimal arm, immaterial to the arm's ranking but a required line before provisioning.
- **The reference arm's node counts are budgets**, not measured footprints, and the demo's 3-node shape is a budget too.
- **The demo has not been run**, so its cost is arithmetic rather than an observed bill.
- **Spot pricing** could not be confirmed from a live source, so Spot is authored nowhere.
- **The local-versus-cloud difference in IAM policy evaluation**: local has none, and M19 already records it. The full diff, including this row, is written in [`docs/local-development.md`](local-development.md) section 8; this document owns only the cloud half of it.
- **The Secrets Store CSI driver projects values**, and the secrets mechanism itself - what a secret is, rotation, and who may read it - is settled in [`docs/security-model.md`](security-model.md) and ADR-0028. This document owns only the cloud placement and the secret-specific local-versus-cloud difference.
- **TLS termination is not end-to-end by default.** ALB TLS termination encrypts the client-to-ALB hop only; the ALB-to-pod hop is plaintext unless it is re-encrypted or the listener is an NLB in TCP pass-through mode with TLS terminating in the pod. Any end-to-end encryption claim must name which of the two the topology uses.
