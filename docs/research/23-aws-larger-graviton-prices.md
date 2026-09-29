# 23 - AWS larger Graviton prices

**Date of research:** 2026-09-29. Every figure below was read on 2026-09-29 from the AWS Price List Bulk API and carries that source's URL and its own publication date.

**Scope:** the observed on-demand list price, per hour, for four `m7g` (Graviton3, Arm) General-purpose instance sizes - `m7g.large`, `m7g.xlarge`, `m7g.2xlarge`, `m7g.4xlarge` - in **us-east-1 (US East / N. Virginia)** and **ap-southeast-5 (Asia Pacific / Malaysia)**. This extends `21-aws-pricing-snapshot.md` (2026-09-28), which recorded `m7g.large` only; the other figures in 21 are not restated here.

**Question answered:** what are the observed hourly on-demand prices for the larger Graviton3 nodes, on the same "Linux, shared tenancy, no pre-installed software" basis as 21 - and are the larger sizes priced linearly against `m7g.large`?

**Ticket:** cost-model input (no issue number was supplied with this assignment).

## 1. Method, and what "observed" means

Source: the **AWS Price List Bulk API**, offer code `AmazonEC2`. For each region the region index `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/<region>/index.json` was read for its `publicationDate` and `version`, and then the line-oriented CSV at `.../current/<region>/index.csv` - the file the same version points at - was read in full and filtered row by row. The CSV was **not** trusted through any summary endpoint.

Rows were selected on the price list's own product attributes: `TermType = OnDemand`, `Tenancy = Shared`, `Operating System = Linux`, `Pre Installed S/W = NA`, `CapacityStatus = Used`. Exactly one row per instance type per region matched, so the figures below are single observed values, not ranges. The exact `usageType` and `SKU` of the matched row are quoted so each can be re-found. All values are **USD per hour** (`Unit = Hrs`). us-east-1 and ap-southeast-5 are separate price files and were read separately.

**Cross-check against 21.** The `m7g.large` row was re-read here and gives 0.081600 (us-east-1) and 0.086700 (ap-southeast-5), identical to the values 21 recorded on 2026-09-28. The selection basis is therefore provably the same, and the three new sizes are observed on that same basis.

## 2. us-east-1

All rows: `Tenancy=Shared`, `Operating System=Linux`, `Pre Installed S/W=NA`, `License Model=No License required`, `CapacityStatus=Used`, `Unit=Hrs`, `EffectiveDate=2026-09-01`, `Current Generation=Yes`, `Physical Processor=AWS Graviton3 Processor`.

| Instance | vCPU | Memory | usageType | SKU | $/hour | Ratio to m7g.large |
|---|---|---|---|---|---|---|
| m7g.large | 2 | 8 GiB | `BoxUsage:m7g.large` | `Y4JWUCG93UEP6MPT` | 0.081600 | 1.000000 |
| m7g.xlarge | 4 | 16 GiB | `BoxUsage:m7g.xlarge` | `Y7X6HJY9G859NU23` | 0.163200 | 2.000000 |
| m7g.2xlarge | 8 | 32 GiB | `BoxUsage:m7g.2xlarge` | `99CC4R2S7FWPBV2Y` | 0.326400 | 4.000000 |
| m7g.4xlarge | 16 | 64 GiB | `BoxUsage:m7g.4xlarge` | `KR9EVAFX4677NQ9A` | 0.652800 | 8.000000 |

## 3. ap-southeast-5

All rows: `Tenancy=Shared`, `Operating System=Linux`, `Pre Installed S/W=NA`, `License Model=No License required`, `CapacityStatus=Used`, `Unit=Hrs`, `EffectiveDate=2026-09-01`, `Current Generation=Yes`, `Physical Processor=AWS Graviton3 Processor`.

| Instance | vCPU | Memory | usageType | SKU | $/hour | Ratio to m7g.large |
|---|---|---|---|---|---|---|
| m7g.large | 2 | 8 GiB | `APS7-BoxUsage:m7g.large` | `WWKXWK4KT6Q4C2QN` | 0.086700 | 1.000000 |
| m7g.xlarge | 4 | 16 GiB | `APS7-BoxUsage:m7g.xlarge` | `TANJWUT55FJXY9P8` | 0.173400 | 2.000000 |
| m7g.2xlarge | 8 | 32 GiB | `APS7-BoxUsage:m7g.2xlarge` | `AZVF55KSFABRCX69` | 0.346800 | 4.000000 |
| m7g.4xlarge | 16 | 64 GiB | `APS7-BoxUsage:m7g.4xlarge` | `P26QNQ7E4YHRFWM9` | 0.693600 | 8.000000 |

## 4. Linearity

**Yes - the m7g sizes are priced exactly linearly against m7g.large in both regions, to all six published decimal places.** `m7g.xlarge` is 2 x `m7g.large`, `m7g.2xlarge` is 4 x, and `m7g.4xlarge` is 8 x, in both us-east-1 and ap-southeast-5. The published rates are not rounded: 0.0816 x 2 = 0.1632, x 4 = 0.3264, x 8 = 0.6528, and 0.0867 x 2 = 0.1734, x 4 = 0.3468, x 8 = 0.6936.

The regional multiplier is also constant: ap-southeast-5 is exactly **1.0625 x** us-east-1 (17/16) for all four sizes (0.0867 / 0.0816 = 1.0625, and likewise for xlarge, 2xlarge, 4xlarge).

**Consequence:** on this observed basis a `m7g` size not in this table can be interpolated from the published `m7g.large` rate by multiplying by the vCPU ratio (size / 2), rather than derived by halving a larger size. That said, this is an observation about these four sizes as published on 2026-09-25; a future price-list republication should be re-read before the multiplier is relied on.

## 5. Not confirmed

- **Larger m7g sizes beyond 4xlarge** (8xlarge, 12xlarge, 16xlarge, metal) were not read; linearity is established only over large -> 4xlarge. Whether the multiplier continues to hold above 4xlarge is **not confirmed**.
- **Other Graviton generations** (Graviton2 `m6g`, Graviton4 `m8g`) and other families (`c7g`, `r7g`) were not read.
- **Spot, Reserved Instance, Savings Plan, Dedicated and Dedicated-Host rates** are out of scope; only on-demand list, shared tenancy, is recorded.
- **Any price change after the 2026-09-25 publication** is not reflected; the figures are as published in that file.

## 6. Sources

All accessed 2026-09-29. Publication dates are the source's own.

- [S1] AWS Price List Bulk API - AmazonEC2 - us-east-1 - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.json and the CSV it points at, https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv (Publication Date 2026-09-25T17:45:21Z; Version 20260925174521; HTTP Last-Modified 2026-09-25T18:44:02Z).
- [S2] AWS Price List Bulk API - AmazonEC2 - ap-southeast-5 - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/ap-southeast-5/index.json and https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/ap-southeast-5/index.csv (Publication Date 2026-09-25T17:45:21Z; Version 20260925174521; HTTP Last-Modified 2026-09-25T18:43:53Z).
- [S3] docs/research/21-aws-pricing-snapshot.md (dated 2026-09-28) - cross-check basis for the m7g.large rate (0.081600 us-east-1, 0.086700 ap-southeast-5).
