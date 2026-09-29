# 22 - AWS network and address pricing

**Date of research:** 2026-09-29. Every figure below was read on 2026-09-29 from a live source and carries that source's URL and the source's own publication or last-modified date.

**Scope:** the gaps left open by `21-aws-pricing-snapshot.md` (dated 2026-09-28), and nothing that 21 already covers. Seven items, for **us-east-1 (US East / N. Virginia)** and **ap-southeast-5 (Asia Pacific / Malaysia)** unless stated: the public IPv4 hourly charge (in-use and idle), VPC interface endpoints (AWS PrivateLink), the S3 gateway endpoint, the EKS cluster subnet/AZ minimum, the ap-southeast-5 Availability Zone count and instance-family coverage, public IPv4 Free Tier eligibility, and EKS managed-node-group / add-on / control-plane charges beyond the $0.10 cluster-hour recorded in 21.

**Question answered:** what do public IPv4 addresses and VPC endpoints cost, what are the hard structural minimums and free-tier terms that 21 did not record, and does EKS bill anything beyond the $0.10 per cluster-hour already recorded?

**Ticket:** cost-model input (no issue number was supplied with this assignment).

## 1. Method, and what "observed" means

Two kinds of source are used, kept distinct:

1. **The AWS Price List Bulk API** - machine-readable, per-region JSON at `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<Service>/current/<region>/index.json`, and its line-oriented CSV twin `.../index.csv`. Each file carries a `publicationDate`; the date is quoted per service below. These files are the authority for every numeric price in this document. Where a figure is stated as a price dimension, the **exact usage-type string and unit** are quoted so the row can be re-found.
2. **AWS documentation and pricing pages** - used for terms the price list does not carry: what "in-use" vs "idle" means, that interface endpoints bill per endpoint per AZ, that gateway endpoints are free, the EKS subnet/AZ minimum, Free Tier eligibility, and whether node groups and add-ons are charged.

A figure is only recorded if it was read from one of those sources. **Where a figure could not be confirmed from a live source, this document says so and gives no number** (see Section 11). All USD. "List" means on-demand, no Savings Plan, no Reserved Instance, no Enterprise Discount Programme. Nothing in 21 is restated; the EKS $0.10 cluster-hour and the Free Tier credit model are taken as read.

**Correction to the assignment's premise (public IPv4).** The assignment says the *EC2* price list carries the `PublicIPv4:InUseAddress` dimension. It does not. The string `IPv4` does not occur anywhere in the us-east-1 `AmazonEC2` CSV (0 matches in 393,635 lines). Both public IPv4 dimensions live in the **`AmazonVPC`** offer, under usage types `<REGION>-PublicIPv4:InUseAddress` and `<REGION>-PublicIPv4:IdleAddress` [S1]. The numbers below are taken from there.

## 2. Price-list provenance

| Service | Offer code | Publication date (both regions) | URL pattern |
|---|---|---|---|
| Public IPv4, VPC endpoints (PrivateLink) | `AmazonVPC` | 2026-09-17T19:05:28Z | `.../AmazonVPC/current/<region>/index.json` [S1] |
| EC2 (instance-family coverage) | `AmazonEC2` | 2026-09-25T17:45:21Z | `.../AmazonEC2/current/<region>/index.json` [S2] |
| EKS (control plane, Auto Mode, Capabilities) | `AmazonEKS` | 2026-09-28T19:42:55Z | `.../AmazonEKS/current/<region>/index.json` [S3] |

Note that `AmazonEKS` was republished after 21 was written (21 recorded 2026-09-18T16:42:36Z); the current file is 2026-09-28T19:42:55Z and carries the extra dimensions in Section 9.

## 3. Gap 1 - public IPv4 address, hourly charge

Offer code `AmazonVPC` [S1]. The price list publishes two separate dimensions, one for an address that is attached to a resource and one for an address that is merely allocated:

| Dimension (usage type) | Meaning | us-east-1 $/hour | ap-southeast-5 $/hour |
|---|---|---|---|
| `USE1-PublicIPv4:InUseAddress` / `APS7-PublicIPv4:InUseAddress` | **In-use** - a public IPv4 address associated with a running resource | 0.005000 | 0.005000 |
| `USE1-PublicIPv4:IdleAddress` / `APS7-PublicIPv4:IdleAddress` | **Idle** - a public IPv4 address allocated to the account but not associated with any resource | 0.005000 | 0.005000 |

Both dimensions are unit `Hrs`. **Which is which:** the in-use dimension applies to an address in use by a resource - an EC2 instance, a NAT gateway, an internet-facing load balancer, an RDS instance, and also addresses assigned to AWS Global Accelerator and AWS Site-to-Site VPN tunnel endpoints. The idle dimension applies to an address that is allocated to your account but not used on a resource - the classic case being an Elastic IP address that is not associated with anything. AWS's own wording: "Any public IPv4 address associated with a resource launched in an Amazon VPC ... are charged as in-use public IPv4 address. Any public IPv4 address associated to your AWS account that is not used on a resource is charged as idle public IPv4 address" [S8]. The VPC pricing page states both rates as **$0.005** per hour and adds "The price is the same whether the public IPv4 address is in-use ... or an idle" [S8]; the price list shows that the equality also holds in ap-southeast-5, where both are 0.005000.

Billing granularity, from the pricing page: "The bill is calculated in one-second increments, with a minimum of 60 seconds" [S8].

The EC2 Elastic IP documentation confirms the charge is unconditional: "There is a charge for all Elastic IP addresses whether they are in use (allocated to a resource, like an EC2 instance) or idle (created in your account but unallocated)" and "AWS charges for all public IPv4 addresses, including public IPv4 addresses associated with running instances and Elastic IP addresses" [S14].

**Consequence for a cost model:** an address costs the same whether or not it is doing anything. Releasing an address is the only way to stop the charge; detaching it does not help.

## 4. Gap 2 - VPC interface endpoint (AWS PrivateLink)

Offer code `AmazonVPC` [S1]. The price dimensions used are the `<REGION>-VpcEndpoint-Hours` and `<REGION>-VpcEndpoint-Bytes` dimensions, operation `VpcEndpoint`, product family `VpcEndpoint`:

| Dimension (usage type) | Unit | us-east-1 | ap-southeast-5 |
|---|---|---|---|
| `USE1-VpcEndpoint-Hours` / `APS7-VpcEndpoint-Hours` | Hrs | 0.010000 | 0.011700 |
| `USE1-VpcEndpoint-Bytes` / `APS7-VpcEndpoint-Bytes`, first 1 PB/month | GB | 0.010000 | 0.010000 |
| same, above 1 PB and up to 5 PB/month | GB | 0.006000 | 0.006000 |
| same, above 5 PB/month | GB | 0.004000 | 0.004000 |

The byte tiers are ranges in the price list: `0 - 1048576`, `1048576 - 5242880`, `5242880 - Inf` GB, identical in both regions [S1].

**The hour dimension is billed per endpoint *per Availability Zone*.** The price list calls it "per VPC Endpoint Hour" and does not itself carry a per-AZ multiplier; the billing model comes from the PrivateLink pricing page, which states "You will be billed for each hour that your VPC endpoint remains provisioned in each Availability Zone, irrespective of the state of its association" and labels the line "Pricing per VPC endpoint per AZ ($/hour)" [S9]. So one interface endpoint placed in three AZs bills 3 x the hourly rate. The GB tiers are different: they "apply on the total data processed by all Interface Endpoints in an AWS Region" [S9], so the tier is measured per region, not per endpoint.

**Excluded deliberately.** The same offer carries `<REGION>-VpcEndpoint-GWLBE-Hours` and `<REGION>-VpcEndpoint-GWLBE-Bytes` (us-east-1 0.010000/hour and 0.003500/GB; ap-southeast-5 0.011700/hour and 0.003500/GB). Those are **Gateway Load Balancer endpoints**, a different endpoint type, and are not the interface-endpoint (PrivateLink) charge. The offer also carries `VpcResourceConsumer` dimensions (0.020000/hour and 0.010000/GB in us-east-1; 0.023400/hour and 0.010000/GB in ap-southeast-5) for "VPC endpoint of type 'resource'" and tunnel endpoints, which are the ODB-network / resource-endpoint feature, not standard interface endpoints.

## 5. Gap 3 - S3 gateway endpoint

**Confirmed free of charge.** Two live sources, both quoted verbatim:

- Amazon VPC documentation, "Gateway endpoints", under the heading **Pricing**: "**There is no additional charge for using gateway endpoints.**" [S4]
- Amazon VPC pricing page: "There are no data processing or hourly charges for using Gateway Type VPC endpoints." [S8]

The same documentation page distinguishes the two mechanisms explicitly: "Gateway endpoints do not use AWS PrivateLink, unlike other types of VPC endpoints" [S4]. So a VPC that reaches S3 through a gateway endpoint pays nothing for the endpoint itself; the S3 request and storage charges in 21 still apply. This is the cost lever that avoids the NAT Gateway data-processing charge for S3 traffic (Section 4's byte tiers do not apply to gateway endpoints).

## 6. Gap 4 - EKS minimum subnet and Availability Zone requirement

**Minimum two subnets in two different Availability Zones.** Verbatim, from the Amazon EKS networking-requirements page: "**When you create a cluster, you specify a VPC and at least two subnets that are in different Availability Zones.**" [S5]

Related constraints from the same page: the VPC must have DNS hostname and DNS resolution support or nodes cannot register; and if subnets are changed after creation, all subnets must be in the same set of AZs as originally supplied [S5]. Note this is the cluster's minimum; it is not the same as the MSK minimum recorded in 21 (two subnets/two AZs for Standard brokers, three for Express), and it is below the "three AZs" that a region such as ap-southeast-5 offers.

## 7. Gap 5 - ap-southeast-5 Availability Zones and instance families

**Availability Zones: 3.** The AWS Regions documentation table lists: `ap-southeast-5` | `Asia Pacific (Malaysia)` | `3` | `Malaysia` | `Required` (opt-in region) [S7]. The same table gives us-east-1 six AZs. So a three-AZ spread satisfies the EKS minimum of two (Section 6) with one AZ to spare.

**Instance families from 21: all three are offered in ap-southeast-5.** Each is present in the ap-southeast-5 `AmazonEC2` price list as a real on-demand shared-tenancy Linux product, and the prices match the ap-southeast-5 column of 21:

| Instance type | Usage type in ap-southeast-5 price list | On-demand $/hour | In 21 |
|---|---|---|---|
| t4g.medium | `APS7-BoxUsage:t4g.medium` | 0.038200 | 0.038200 |
| m7g.large | `APS7-BoxUsage:m7g.large` | 0.086700 | 0.086700 |
| m7i.large | `APS7-BoxUsage:m7i.large` | 0.107100 | 0.107100 |

The price list does not enumerate AZs for these products (the `AvailabilityZone` attribute is `NA` for compute-instance rows), so the price list establishes that the family is priced in the region, not which AZ it lands in. Per-AZ capacity is a runtime question for `DescribeInstanceTypeOfferings`, which needs credentials; it is recorded as not confirmed in Section 11.

## 8. Gap 6 - public IPv4 Free Tier eligibility

**Legacy 12-month tier: yes, 750 hours per month.** The legacy Free Tier page's Amazon EC2 card, in the **12-Months Free** category (badge "12 Months Free"), lists verbatim: "**750 hours per month of public IPv4 address regardless of instance type**" [S11]. The same page states the eligibility rule for the whole category: "These free tier offers are only available to **Legacy Free Tier AWS customers**, and are available for 12 months following your AWS sign-up date" [S11].

**New (non-legacy) account today: no public IPv4 allowance found.** The current Free Tier offer set does not contain a public IPv4 offer. The current Free Tier page categorises offers as **Short-term Trial**, **Always Free**, **Available on both plans**, and **Paid Plan Exclusive** - there is no "12-Months Free" category on it, and the string "IPv4" does not occur on either the Free Tier landing page or its full offers listing [S12]. The legacy page is explicit that the 12-Month Free category, which is the only place the 750-hour public IPv4 allowance appears, is legacy-only [S11]. Combined with the model 21 already recorded (new accounts get up to $200 of credits over 6 months, plus always-free services), the reading is: **a new account has no free public IPv4 allowance, and public IPv4 usage is billed and can only be offset by drawing down the credit pool.**

Confidence differs between the two halves and is stated as such in Section 11: the legacy figure is a verbatim quote, the new-account conclusion is an absence-of-offer finding rather than an AWS sentence saying "public IPv4 is not free for new accounts".

## 9. Gap 7 - EKS charges beyond the $0.10 cluster-hour

### 9.1 Managed node groups

**No additional EKS charge.** Verbatim: "**There are no additional costs to use Amazon EKS managed node groups, you only pay for the AWS resources you provision. These include Amazon EC2 instances, Amazon EBS volumes, Amazon EKS cluster hours, and any other AWS infrastructure. There are no minimum fees and no upfront commitments.**" [S6] The EKS FAQs agree: "You pay $0.10 per hour for each Amazon EKS cluster you create and for the AWS resources you create to run your Kubernetes worker nodes" [S13]. The `AmazonEKS` price list corroborates this: it contains no node-group dimension at all [S3]. In a cost model, a managed node group costs exactly its EC2 instances plus their EBS volumes plus the $0.10 cluster-hour - the "managed" part is free.

### 9.2 EKS add-ons

**No separate EKS charge for the add-on mechanism.** The `AmazonEKS` price list contains no usage type matching `addon`, `add-on` or `add_on` in either region [S3], and the EKS pricing page carries no add-on price line [S10]. The user-guide page on add-ons states no price or charge [S15]. Add-ons run on the cluster's own compute, so what you pay for is the underlying resources they create (for example an EBS volume or a load balancer), not a per-add-on fee.

**Important distinction:** *EKS Capabilities* is a separate, newer feature and **is** charged (Section 9.3). The FAQs draw the line explicitly: "Unlike EKS add-ons which run on your cluster's compute resources and require you to manage the underlying compute capacity ... EKS Capabilities [have] AWS also take responsibility for securing, configuring, and managing" [S13]. Do not generalise "add-ons are free" to Capabilities.

### 9.3 Control plane: what the price list bills beyond $0.10

21 recorded only the standard per-cluster-hour rate. The current `AmazonEKS` price list carries several further dimensions, all additional to (not instead of) the standard rate unless noted [S3]:

| Charge | Usage type | Unit | us-east-1 | ap-southeast-5 |
|---|---|---|---|---|
| Standard control plane (already in 21) | `<REGION>-AmazonEKS-Hours:perCluster` | Hours | 0.100000 | 0.100000 |
| Extended Kubernetes-version support - **surcharge** on top of standard | `<REGION>-AmazonEKS-Hours:extendedSupport` | Hours | 0.500000 | 0.500000 |
| Provisioned Control Plane, XL tier | `<REGION>-AmazonEKS-Hours:XL-ProvisionedTier` | Hours | 1.650000 | 1.650000 |
| Provisioned Control Plane, 2XL tier | `...:2XL-ProvisionedTier` | Hours | 3.400000 | 3.400000 |
| Provisioned Control Plane, 4XL tier | `...:4XL-ProvisionedTier` | Hours | 6.900000 | 6.900000 |
| Provisioned Control Plane, 8XL tier | `...:8XL-ProvisionedTier` | Hours | 13.900000 | 13.900000 |
| EKS local clusters on AWS Outposts | `<REGION>-AmazonEKS-Local-Outposts-Hours:perCluster` | hours | 0.100000 | (not listed) |
| EKS Auto Mode, per managed instance-hour | `EKS-Auto:<type>-management-hours` | hours | per type | per type |
| EKS Capabilities, Argo CD - per capability-hour | `<REGION>-AmazonEKSCapabilities-ArgoCD-Hours:perCapability` | Hours | 0.030000 | 0.029108 |
| EKS Capabilities, Argo CD - per managed Application-hour | `...-ArgoCD-CR-Hours:perCustomResource` | Hours | 0.001500 | 0.001452 |
| EKS Capabilities, ACK - per capability-hour | `...-ACK-Hours:perCapability` | Hours | 0.005000 | 0.004949 |
| EKS Capabilities, ACK - per managed resource-hour | `...-ACK-CR-Hours:perCustomResource` | Hours | 0.000050 | 0.000049 |
| EKS Capabilities, KRO - per capability-hour | `...-KRO-Hours:perCapability` | Hours | 0.005000 | 0.004949 |
| EKS Capabilities, KRO - per RGD-instance-hour | `...-KRO-CR-Hours:perCustomResource` | Hours | 0.000050 | 0.000049 |
| Hybrid Nodes, per vCPU-hour | `<REGION>-AmazonEKSHybridNodes-Hours:pervCPU` | vCPU-Hours | 5 tier values: 0.006 / 0.008 / 0.010 / 0.014 / 0.020 | same five values |
| AWS Fargate (EKS on Fargate) | `<REGION>-Fargate-vCPU-Hours:perCPU` and `<REGION>-Fargate-GB-Hours` | hours | 0.040480 / 0.004445 | 0.045504 / 0.004977 |

Extended support is additive: the pricing page describes it as "$0.60 per cluster per hour (Standard Kubernetes version support + $0.50 per cluster per hour)" [S10], which is the 0.100000 standard rate plus the 0.500000 surcharge dimension. Provisioned Control Plane tiers are region-invariant in the two regions read. EKS Auto Mode is "in addition to the Amazon EC2 instance price, which covers the EC2 instance" [S10]; for the three families in 21 the management-hour rates are:

| Instance type | us-east-1 `EKS-Auto:<type>-management-hours` | ap-southeast-5 `APS7-EKS-Auto:<type>-management-hours` |
|---|---|---|
| t4g.medium | 0.004030 | 0.004580 |
| m7g.large | 0.009790 | 0.010400 |
| m7i.large | 0.012100 | 0.012850 |

For a cost model, the practical reading: **a plain EKS cluster with managed node groups bills $0.10/hour plus the nodes' EC2 and EBS, and nothing else.** Every extra charge in the table above is opt-in (extended support, Provisioned Control Plane, Auto Mode, Capabilities, Hybrid Nodes) or is ordinary compute that is merely listed under the EKS offer (Fargate). The $0.10 figure in 21 remains correct for the default case.

## 10. Not confirmed / limitations

- **Per-AZ capacity for t4g.medium / m7g.large / m7i.large in ap-southeast-5.** The price list proves each family is priced in the region (Section 7) but its compute rows carry `AvailabilityZone = NA`, so it cannot say which of the three AZs can launch them. Resolving this needs `DescribeInstanceTypeOfferings` with AWS credentials, which this pass did not have. No number is asserted.
- **The new-account public IPv4 answer is an absence-of-offer finding, not a quoted AWS sentence.** Section 8 shows the 750-hour allowance sits in the legacy-only 12-Month Free category and that no public IPv4 offer appears in the current Free Tier offer set, but no AWS page read says, in words, "public IPv4 is not free for new accounts". Treated as "no free allowance", with that caveat.
- **Hybrid Nodes tier boundaries were not extracted.** The price list carries five per-vCPU-hour values (0.006 / 0.008 / 0.010 / 0.014 / 0.020) but the tier ranges were not read, so the table records the value set without asserting which volume band each value applies to. Hybrid Nodes are outside the deployment design in any case.
- **Interface-endpoint per-AZ billing is a pricing-page statement, not a price-list dimension.** The number (0.010000 / 0.011700 per hour) is from the price list; the "per AZ" multiplication is from the PrivateLink pricing page [S9]. If a future AWS change made the hour dimension per-endpoint rather than per-endpoint-AZ, the price list alone would not reveal it.
- **Free Tier credits applied to public IPv4, VPC endpoints or EKS charges** is not itemised by AWS; 21's conclusion that EKS has no free allowance stands, and the credit pool is the only general offset.
- **Reserved Instances, Savings Plans, and any private pricing** remain out of scope, as in 21.

## 11. Sources

All accessed 2026-09-29. Publication dates are the source's own where the source carries one; AWS documentation pages generally do not show one.

- [S1] AWS Price List Bulk API - **AmazonVPC** - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate **2026-09-17T19:05:28Z**, both regions)
- [S2] AWS Price List Bulk API - **AmazonEC2** - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate **2026-09-25T17:45:21Z**, both regions)
- [S3] AWS Price List Bulk API - **AmazonEKS** - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEKS/current/us-east-1/index.json and .../ap-southeast-5/index.json (publicationDate **2026-09-28T19:42:55Z**, both regions)
- [S4] AWS documentation - Gateway endpoints - https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html ("There is no additional charge for using gateway endpoints.")
- [S5] AWS documentation - View Amazon EKS networking requirements for VPC and subnets - https://docs.aws.amazon.com/eks/latest/userguide/network_reqs.html ("at least two subnets that are in different Availability Zones")
- [S6] AWS documentation - Simplify node lifecycle with managed node groups - https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html ("There are no additional costs to use Amazon EKS managed node groups")
- [S7] AWS documentation - Available AWS Regions (Availability Zone counts) - https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html (table row: ap-southeast-5, Asia Pacific (Malaysia), 3 AZs)
- [S8] Amazon VPC pricing - https://aws.amazon.com/vpc/pricing/ (in-use and idle public IPv4 $0.005/hour; one-second billing increments, 60-second minimum; "There are no data processing or hourly charges for using Gateway Type VPC endpoints.")
- [S9] AWS PrivateLink pricing - https://aws.amazon.com/privatelink/pricing/ ("billed for each hour that your VPC endpoint remains provisioned in each Availability Zone"; "Pricing per VPC endpoint per AZ ($/hour)"; data tiers apply to all interface endpoints in a region)
- [S10] Amazon EKS pricing - https://aws.amazon.com/eks/pricing/ ($0.10 standard; $0.60 extended; Provisioned Control Plane tiers; EKS Auto Mode "in addition to the Amazon EC2 instance price"; EKS Capabilities per capability-hour)
- [S11] AWS Legacy Free Tier - https://aws.amazon.com/free/legacy/ (12-Months Free category, Amazon EC2: "750 hours per month of public IPv4 address regardless of instance type"; "only available to Legacy Free Tier AWS customers ... for 12 months following your AWS sign-up date")
- [S12] AWS Free Tier - https://aws.amazon.com/free/ and the offers listing https://aws.amazon.com/free/offers/ (plan-type categories: Short-term Trial, Always Free, Available on both plans, Paid Plan Exclusive; no public IPv4 offer)
- [S13] Amazon EKS FAQs - https://aws.amazon.com/eks/faqs/ ("You pay $0.10 per hour for each Amazon EKS cluster you create and for the AWS resources you create to run your Kubernetes worker nodes"; EKS Capabilities vs EKS add-ons)
- [S14] AWS documentation - Elastic IP addresses - https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html ("There is a charge for all Elastic IP addresses whether they are in use ... or idle"; "AWS charges for all public IPv4 addresses")
- [S15] AWS documentation - Amazon EKS add-ons - https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html (no price or charge stated)
- [21] `docs/research/21-aws-pricing-snapshot.md` - the companion snapshot (2026-09-28) whose gaps this file fills; not restated here.
