# 21 - AWS pricing snapshot

**Date of research:** 2026-09-28. Every figure below was read on 2026-09-28 from a live source and carries that source's URL and the source's own publication or last-modified date.

**Scope:** on-demand list prices for the AWS services the platform's deployment arm would consume, in two regions - **ap-southeast-5 (Asia Pacific / Malaysia)** and **us-east-1 (US East / N. Virginia)**. Services: EKS, EC2, EC2 Spot, EBS, RDS for PostgreSQL, S3, NAT Gateway, Application Load Balancer, data transfer out, Secrets Manager, MSK, and the AWS Free Tier.

**Question answered:** what does each line item cost today, at list, in these two regions - and with EKS plus RDS in the design, is a genuinely 0-dollar AWS deployment possible?

**Ticket:** cost-model input (no issue number was supplied with this assignment).

## 1. Method, and what "observed" means

Two kinds of source are used, and the two are kept distinct:

1. **The AWS Price List Bulk API** - machine-readable, per-region JSON at `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<Service>/current/<region>/index.json`. This is AWS's own published price list. Each file carries a `publicationDate`; the date is quoted per service below. These files are the authority for every numeric price in this document.
2. **AWS marketing and documentation pages** - used only for terms that are not in the price list: free-tier eligibility, the Spot discount band, the gp3 baseline, the RDS 7-day stop limit, and MSK's minimum broker count.

A figure is only recorded if it was read from one of those sources. **Where a price could not be confirmed from a live source, this document says so and gives no number** (see Section 16).

All USD. "List" means on-demand, no Savings Plan, no Reserved Instance, no Enterprise Discount Programme.

## 2. Price-list provenance

| Service | Offer code | Publication date (both regions) | URL pattern |
|---|---|---|---|
| EKS | `AmazonEKS` | 2026-09-18T16:42:36Z | `.../AmazonEKS/current/<region>/index.json` [S1] |
| EC2 (compute, EBS, NAT) | `AmazonEC2` | 2026-09-25T17:45:21Z | `.../AmazonEC2/current/<region>/index.json` [S2] |
| RDS | `AmazonRDS` | 2026-09-24T21:10:11Z | `.../AmazonRDS/current/<region>/index.json` [S3] |
| S3 | `AmazonS3` | 2026-09-26T01:55:12Z | `.../AmazonS3/current/<region>/index.json` [S4] |
| Data transfer | `AWSDataTransfer` | 2026-09-16T13:22:08Z | `.../AWSDataTransfer/current/<region>/index.json` [S5] |
| MSK | `AmazonMSK` | 2026-09-11T12:44:56Z | `.../AmazonMSK/current/<region>/index.json` [S6] |
| Secrets Manager | `AWSSecretsManager` | 2026-09-11T12:46:10Z | `.../AWSSecretsManager/current/<region>/index.json` [S7] |
| ELB (ALB) | `AWSELB` | 2026-09-11T12:45:44Z | `.../AWSELB/current/<region>/index.json` [S8] |

The top-level offer index (`https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json`) reported `publicationDate` **2026-09-28T14:40:21Z** when read on 2026-09-28 [S9].

## 3. EKS

| Item | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| Control plane, per cluster-hour (standard Kubernetes version support) | $0.100000 | $0.100000 | Price list [S1]; page states "$0.10 per cluster per hour" [S10] |
| Control plane, per cluster-hour (extended Kubernetes version support) | $0.60 (page-stated, region-invariant) | $0.60 (page-stated) | [S10] |

Standard support covers the first 14 months after a Kubernetes version is released; extended support is the next 12 months at standard + $0.50 per cluster-hour [S10].

**Free tier or credit on the control plane: none found.** The EKS pricing page lists no free tier and no credit specific to the control plane [S10]; the price list contains only the per-cluster-hour charges [S1]. EKS is not in the AWS Free Tier page's list of free-plan-eligible services (Section 14). Whether general Free Tier credits may be applied to EKS control-plane usage is not stated on the pages read; the EKS page shows no such offer. **Treated as a charge with no free allowance.**

## 4. EC2 on-demand (Linux, shared tenancy, `Used` capacity, no pre-installed software)

| Instance | Family / ISA | us-east-1 $/hour | ap-southeast-5 $/hour | Source |
|---|---|---|---|---|
| t4g.medium | General purpose, **Graviton2 (Arm)** | 0.033600 | 0.038200 | [S2] |
| m7g.large | General purpose, **Graviton3 (Arm)** | 0.081600 | 0.086700 | [S2] |
| m7i.large | General purpose, **x86 (Intel)** | 0.100800 | 0.107100 | [S2] |

Graviton is materially cheaper than x86 at the same size: m7g.large is ~19% below m7i.large in us-east-1 and ~19% below in ap-southeast-5. Note these are the "Used" shared-tenancy rates; the price list also carries Dedicated and Dedicated-Host rates at different values (not reproduced).

## 5. EC2 Spot

| Item | Value | Source |
|---|---|---|
| Documented discount band | **up to 90% off On-Demand** | Spot pricing page, read 2026-09-28 [S11] |
| Current price-history source | EC2 console **Spot Instance pricing history**, backed by the `DescribeSpotPriceHistory` API (AWS CLI / SDK, requires credentials) | AWS docs [S12]; CLI reference [S13] |
| Per-family spot price for t4g.medium / m7g.large / m7i.large | **Not confirmed** | see below |

**Why no per-family number is given.** AWS's legacy public Spot feeds still resolve, but they are stale and do not contain the families asked for. `https://website.spot.ec2.aws.a2z.com/spot.json` and `https://spot-price-gamma-iad.s3.us-east-1.amazonaws.com/spot.json` were both fetched on 2026-09-28; in us-east-1 the "generalCurrentGen" list begins at m4, and in ap-southeast-5 it contains only m6g/c6g - **no t4g, m7g, or m7i entries at all**. They are therefore unusable as a current price for these families and no figure is taken from them. A live spot price requires `DescribeSpotPriceHistory` with AWS credentials, which this fact-finding pass did not have. The honest statement is: the discount band is AWS-stated at up to 90%, and the current per-instance price must be read from the console's Spot pricing history or the credentialed API.

## 6. EBS

gp3 baseline per volume (free, included in the storage price): **3,000 IOPS and 125 MB/s**. Charges apply only above that [S14].

| Item | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| gp3 storage, $/GB-month | 0.080000 | 0.086400 | [S2] |
| gp3 provisioned IOPS above 3,000, $/IOPS-month | 0.005000 | 0.005400 | [S2] |
| gp3 provisioned throughput above 125 MB/s, $/MiBps-month | 0.040000 | 0.043200 | [S2] |
| Snapshot storage, $/GB-month | 0.050000 | 0.045000 | [S2] |

(The gp3 throughput price dimension is published per GiBps-month as 40.96 and 44.2368 respectively; dividing by 1,024 gives the per-MiBps-month figures above, which match the description text "$0.04 / $0.0432 per provisioned MiBps-month of gp3".)

## 7. RDS for PostgreSQL

Instance hours (RDS for PostgreSQL):

| Instance | Deployment | us-east-1 $/hour | ap-southeast-5 $/hour | Source |
|---|---|---|---|---|
| db.t4g.micro | Single-AZ | 0.016000 | 0.023000 | [S3] |
| db.t4g.micro | Multi-AZ | 0.032000 | 0.046000 | [S3] |
| db.t4g.small | Single-AZ | 0.032000 | 0.046000 | [S3] |
| db.t4g.small | Multi-AZ | 0.065000 | 0.091000 | [S3] |

Storage, backup, snapshot:

| Item | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| gp3 storage, Single-AZ, $/GB-month | 0.115000 | 0.124000 | [S3] |
| gp3 storage, Multi-AZ, $/GB-month | 0.230000 | 0.248000 | [S3] |
| gp3 provisioned IOPS, Single-AZ, $/IOPS-month | 0.020000 | 0.022000 | [S3] |
| Backup storage beyond the free allocation, $/GB-month | 0.095000 | 0.086000 | [S3] |
| Snapshot export to S3, $/GB | 0.010000 | 0.009900 | [S3] |

**Free backup allocation:** "There is no additional charge for backup storage up to 100% of your total database storage for a region." Multi-AZ and Single-AZ are treated the same for backup storage [S15]. Backup storage here means automated backups plus customer-initiated snapshots.

**7-day stop limit: it applies.** "The instance stops running, up to a maximum of 7 consecutive days"; "If you don't manually start your DB instance after it is stopped for seven consecutive days, RDS automatically starts your DB instance for you" [S16]. So a stopped RDS instance still bills compute for at least part of the month - stopping is not a way to make RDS free.

## 8. S3

Storage, $/GB-month:

| Storage class | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| Standard - first 50 TB | 0.023000 | 0.022500 | [S4] |
| Standard - next 450 TB | 0.022000 | 0.021600 | [S4] |
| Standard - over 500 TB | 0.021000 | 0.020700 | [S4] |
| Intelligent-Tiering - Frequent Access (first 50 TB) | 0.023000 | 0.022500 | [S4] |
| Intelligent-Tiering - Infrequent Access | 0.012500 | 0.012420 | [S4] |
| Intelligent-Tiering - Archive Instant Access | 0.004000 | 0.004500 | [S4] |
| Intelligent-Tiering - Archive Access | 0.003600 | 0.004050 | [S4] |
| Intelligent-Tiering - Deep Archive Access | 0.000990 | 0.001800 | [S4] |

Requests and lifecycle:

| Item | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| PUT / COPY / POST / LIST, per 1,000 | 0.005000 | 0.004500 | [S4] |
| GET and all other requests, per 1,000 | 0.000400 | 0.000360 | [S4] |
| Lifecycle transition, per 1,000 (to Intelligent-Tiering / SIA / ZIA) | 0.010000 | 0.010000 | [S4] |
| Lifecycle transition to Glacier Instant Retrieval, per 1,000 | 0.020000 | 0.020000 | [S4] |
| Intelligent-Tiering monitoring & automation, per 1,000 objects-month | 0.002500 | 0.002500 | [S4] |

(The price list publishes GET/other as $0.004 per 10,000 in us-east-1 and $0.0036 per 10,000 in ap-southeast-5; the per-1,000 figures above are those values divided by ten.)

Early-deletion charges, $/GB-month prorated, first 50 TB band:

| Class | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| Intelligent-Tiering | 0.023000 | 0.022500 | [S4] |
| Standard-Infrequent Access | 0.012500 | (not read) | [S4] |
| One Zone-Infrequent Access | 0.010000 | (not read) | [S4] |
| Glacier Instant Retrieval | 0.004000 | (not read) | [S4] |

**Standard has no early-deletion charge** - the price list carries `EarlyDelete-` dimensions only for the infrequent-access and archive classes. Deleting or overwriting an object before 90 days (INT/GIR) or 30 days (SIA/ZIA) incurs the prorated charge.

## 9. NAT Gateway

| Item | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| Per hour | 0.045000 | 0.050150 | [S2] |
| Per GB processed | 0.045000 | 0.050150 | [S2] |

Both dimensions carry the same value in each region (0.045 in us-east-1, 0.05015 in ap-southeast-5); the raw price list was checked directly and the ap-southeast-5 value appears six times across the standard and regional NAT-gateway dimensions.

## 10. Application Load Balancer

| Item | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| Per ALB-hour | 0.022500 | 0.022700 | [S8] |
| Per LCU-hour | 0.008000 | 0.008000 | [S8] |

(The AWSELB list also carries Network, Gateway, and base "LoadBalancing" rates; the Application-specific rows are the ones above.)

## 11. Data transfer out to the internet

| Band | us-east-1 $/GB | ap-southeast-5 $/GB | Source |
|---|---|---|---|
| First 10 TB / month (beyond the global free tier) | 0.090000 | 0.108000 | [S5] |
| Next 40 TB | 0.085000 | 0.076500 | [S5] |
| Next 100 TB | 0.070000 | 0.073800 | [S5] |
| Over 150 TB | 0.050000 | 0.072000 | [S5] |
| Free allowance | 100 GB/month, aggregated globally | 100 GB/month | [S5] |

## 12. Secrets Manager

| Item | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| Per secret per month | 0.400000 | 0.400000 | [S7] |
| Per 10,000 API requests | 0.050000 | 0.050000 | [S7] |

## 13. MSK (managed Kafka comparison)

Serverless:

| Item | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| Cluster-hour | 0.750000 | 0.796875 | [S6] |
| Partition-hour | 0.001500 | 0.00159375 | [S6] |
| Storage, $/GB-month | 0.100000 | 0.108000 | [S6] |
| Data in, $/GB | 0.100000 | 0.106250 | [S6] |
| Data out, $/GB | 0.050000 | 0.053125 | [S6] |

Provisioned (per broker-hour; entry level = smallest broker):

| Item | us-east-1 | ap-southeast-5 | Source |
|---|---|---|---|
| kafka.t3.small, $/broker-hour | 0.045600 | 0.052030 | [S6] |
| kafka.m7g.large, $/broker-hour | 0.204000 | 0.216750 | [S6] |
| Storage (gp2), $/GB-month | 0.100000 | 0.108000 | [S6] |
| Provisioned storage throughput, $/MiBps-month | 0.080000 | 0.086400 | [S6] |

**Cluster minimum:** MSK Provisioned requires at least **two** subnets in two different Availability Zones for Standard brokers (two or three may be specified), and **three** subnets in three AZs for Express brokers [S17]. The entry-level cluster cost is therefore two brokers, not one: at t3.small that is 2 x 0.0456 = **$0.0912/hour** in us-east-1 and 2 x 0.05203 = **$0.10406/hour** in ap-southeast-5, before storage. AWS's own pricing example uses three brokers [S18].

## 14. AWS Free Tier, as read on 2026-09-28

Source: the AWS Free Tier page [S19] and its FAQ [S20], read 2026-09-28. The change date quoted by AWS is **"Starting July 15, 2025, new AWS customers will receive up to $200 in AWS Free Tier credits"** [S14].

**New account, current model:**

- **Credits:** $100 on sign-up, plus up to $100 more earned by exploring services = **up to $200**, over **6 months** [S19].
- **Free plan expiry:** the earlier of (1) 6 months from the date the account was opened, or (2) exhaustion of the Free Tier credits. The plan cannot be extended beyond 6 months [S20].
- **On expiry:** AWS closes the account; data is retained for 90 days and can be downloaded only after upgrading to a Paid plan [S20].
- **Credit expiry:** credits expire **12 months** from the date the account was created (not 6) [S20].
- **Eligibility:** only for new AWS customers; an existing or past AWS account makes you ineligible [S20].
- **Access:** over 90 services for up to 6 months on the Free plan; 30+ services are "always free" within monthly usage limits on both plans [S19].
- **Free-plan-eligible compute/database instances explicitly named:** EC2 **T3.micro, T3.small, T4g.micro, T4g.small, C7i-flex.large, M7i-flex.large**; RDS **db.t3.micro and db.t4g.micro** on MySQL, PostgreSQL, MariaDB, SQL Server; Aurora PostgreSQL serverless up to 4 ACU and 1 GiB storage per cluster; S3, Bedrock, SageMakerAI [S19].
- EKS, MSK, NAT Gateway, Application Load Balancer and Secrets Manager are **not** in the free-plan-eligible list on the Free Tier page [S19].

**What is free for 12 months:** the 12-month tier is now the **Legacy Free Tier**, available only to accounts created before the change. "These free tier offers are only available to Legacy Free Tier AWS customers, and are available for 12 months following your AWS sign-up date" [S21]. Its headline offers include 750 hours/month of Linux/RHEL/SLES t2.micro or t3.micro plus 750 hours/month of a public IPv4 address; 5 GB of S3 Standard storage; 750 hours/month of Single-AZ RDS db.t3.micro **and** db.t4g.micro on MySQL/MariaDB/PostgreSQL, 20 GB gp2 storage and 20 GB of backup/snapshot storage [S21]. **A new account today does not receive this 12-month tier** - the only 12-month element is the credit-expiry window, not the plan [S19][S20].

## 15. The 0-dollar question

**With EKS plus RDS in the design, a genuinely 0-dollar AWS deployment is not possible.** The single line item that makes it impossible is the **EKS control plane at $0.10 per cluster-hour** [S1][S10].

Why this is the impossible item, and not RDS:

- EKS control plane: no free tier, no free-plan eligibility, no allowance of any kind found on the EKS pricing page or in the price list [S1][S10][S19]. It bills every hour the cluster exists, whether or not a node runs. At list, one cluster is 0.10 x 730 = **$73.00 per month**.
- RDS: db.t4g.micro is a free-plan-eligible instance and is also one of the legacy 12-month free instances [S19][S21]. RDS is therefore *coverable* on a new account (by credits, for a limited window) or on a legacy account (12 months). It is not the hard floor.
- Everything else in the design (NAT Gateway, ALB, S3, data transfer) is also a charge, but each can in principle be removed or reduced by design choices (no NAT gateway, no public ALB, etc.). The EKS control plane cannot: if the design uses EKS, the charge exists.

Even the strongest free-tier path only defers it. On a new account, the up-to-$200 credit pool would cover roughly 2.7 months of a single EKS control plane ($73/month) before the credit is gone, and the free plan cannot be extended past 6 months [S19][S20]. After that the deployment is not 0-dollar. So the correct answer to "is a genuinely 0-dollar deployment possible" is **no**, and the line item is the **EKS control-plane charge**.

If a 0-dollar demonstration is required, the design must drop EKS (for example, run Kubernetes locally, or use a single EC2 instance on the free tier, or run the control plane outside AWS) - that is a design decision, not a pricing one, and is out of scope for this snapshot.

## 16. Not confirmed / limitations

- **EC2 Spot per-instance prices for t4g.medium, m7g.large, m7i.large** could not be confirmed from a live unauthenticated source; the legacy public Spot feeds are stale and omit these families. Only the AWS-stated discount band (up to 90%) is recorded. See Section 5.
- **EKS extended-support price in ap-southeast-5** was taken from the region-invariant figure on the EKS pricing page, not from the ap-southeast-5 price list (which carries only the standard-support rate).
- **S3 early-deletion charges for SIA, ZIA, and GIR in ap-southeast-5** were not read; only the Intelligent-Tiering figure is given for that region.
- **Whether general Free Tier credits may be applied to EKS/MSK/NAT/ALB charges** is not stated on the pages read. The EKS pricing page offers no free tier or credit for the control plane, so it is treated as an uncovered charge.
- **Reserved Instances, Savings Plans, Dedicated Hosts, and any private-pricing discounts** are out of scope; only on-demand list is recorded.
- **RDS storage sizing, S3 request volumes, and NAT data volumes** are not in this document; it records unit prices only, not a modelled monthly total.

## 17. Sources

All accessed 2026-09-28. Publication dates are the source's own.

- [S1] AWS Price List Bulk API - AmazonEKS - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEKS/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate 2026-09-18T16:42:36Z)
- [S2] AWS Price List Bulk API - AmazonEC2 - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate 2026-09-25T17:45:21Z)
- [S3] AWS Price List Bulk API - AmazonRDS - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate 2026-09-24T21:10:11Z)
- [S4] AWS Price List Bulk API - AmazonS3 - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate 2026-09-26T01:55:12Z)
- [S5] AWS Price List Bulk API - AWSDataTransfer - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate 2026-09-16T13:22:08Z)
- [S6] AWS Price List Bulk API - AmazonMSK - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonMSK/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate 2026-09-11T12:44:56Z)
- [S7] AWS Price List Bulk API - AWSSecretsManager - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSSecretsManager/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate 2026-09-11T12:46:10Z)
- [S8] AWS Price List Bulk API - AWSELB - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate 2026-09-11T12:45:44Z)
- [S9] AWS Price List Bulk API - offer index - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json (publicationDate 2026-09-28T14:40:21Z)
- [S10] Amazon EKS pricing - https://aws.amazon.com/eks/pricing/
- [S11] Amazon EC2 Spot Instances pricing - https://aws.amazon.com/ec2/spot/pricing/ ("Spot Instances are available at a discount of up to 90% off compared to On-Demand pricing")
- [S12] AWS docs - Spot Instance pricing history - https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-spot-instances-history.html
- [S13] AWS CLI reference - describe-spot-price-history - https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-spot-price-history.html
- [S14] Amazon EBS pricing - https://aws.amazon.com/ebs/pricing/ (gp3 baseline "3,000 IOPS free" and "125 MB/s free"; "Starting July 15, 2025, new AWS customers will receive up to $200 in AWS Free Tier credits")
- [S15] Amazon RDS for PostgreSQL pricing - https://aws.amazon.com/rds/postgresql/pricing/ ("There is no additional charge for backup storage up to 100% of your total database storage for a region")
- [S16] AWS docs - Stopping an Amazon RDS DB instance temporarily - https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html ("up to a maximum of 7 consecutive days"; automatic restart after seven consecutive days)
- [S17] AWS docs - Creating an Amazon MSK Provisioned cluster - https://docs.aws.amazon.com/msk/latest/developerguide/msk-create-cluster.html (Standard brokers: two or three subnets in different AZs; Express brokers: three subnets in three AZs)
- [S18] Amazon MSK pricing - https://aws.amazon.com/msk/pricing/ (worked examples using 3 brokers)
- [S19] AWS Free Tier - https://aws.amazon.com/free/ ($100 + up to $100 = up to $200 over 6 months; free-plan-eligible EC2/RDS instance lists; 90+ services; 30+ always-free)
- [S20] AWS Free Tier FAQs - https://aws.amazon.com/free/free-tier-faqs/ (free plan expires at 6 months or credit exhaustion; credits expire 12 months from account creation; ineligibility for existing accounts; 90-day data retention after expiry)
- [S21] AWS Legacy Free Tier - https://aws.amazon.com/free/legacy/ (12-month offers available only to Legacy Free Tier customers; EC2 750 hrs t2/t3.micro, S3 5 GB, RDS 750 hrs db.t3.micro/db.t4g.micro, 20 GB gp2, 20 GB backup)
