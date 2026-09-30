# 14 - Licence and cost audit

**Date of research:** 2026-09-28. All evidence accessed 2026-09-28 unless stated.
**Scope:** the nineteen components in `docs/technology-selection.md`, the four documented fallbacks (Lakekeeper, RustFS, Karapace, Apache Airflow), the four datasets (TPC-C, TPC-H, RIPE Atlas, ONSPD), and the base images and runtimes (Eclipse Temurin JDK 17, Python 3.12, and the OCI images the components publish).
**Question answered:** is every chosen component and data source actually free to use - no payment, no commercial-use restriction, open source rather than merely source-available - and what obligation or paid-only capability does each one carry?
**Ticket:** [#20 Licence and cost audit](https://github.com/SoongGuanLeong/de-platform/issues/20) is issue #20 on map #9. Related decision: [ADR-0009](../adr/0009-dataset-licence-position-and-obligations.md).

## The method

Every row is read from a **primary source**: the project's own `LICENSE` or `COPYRIGHT` file in its canonical repository, the rights holder's own licence or pricing page, or the dataset owner's own terms document. Secondary write-ups are used only to locate the primary source, never as the authority. The licence text for each repository was read on 2026-09-28; licence files are stable across minor versions, so the read is representative of the pinned major.

"OSI-approved" means the identifier appears in the Open Source Initiative's approved-licence list. "Free of charge" means no payment is required to run the component or use the data for the platform's purpose. "Copyleft obligation" records the obligation that a *public portfolio* could trigger, not the obligation in the abstract. "Paid-only capabilities" records whether the platform depends on anything that sits behind a commercial edition.

## 1. The nineteen components

| Component | Pin | Licence | OSI-approved | Free of charge | Commercial-use restriction | Copyleft obligation | Paid-only capabilities the platform needs | Source | Accessed |
|---|---|---|---|---|---|---|---|---|---|
| Apache Iceberg | 1.11.0 | Apache-2.0 | Yes | Yes | none | none | none | `apache/iceberg` LICENSE [S1] | 2026-09-28 |
| Apache Polaris | 1.7.0 | Apache-2.0 | Yes | Yes | none | none | none (ASF project; vendor support optional) | `apache/polaris` LICENSE [S2] | 2026-09-28 |
| SeaweedFS | 4.47 | Apache-2.0 | Yes | Yes | none | none | none | `seaweedfs/seaweedfs` LICENSE [S3] | 2026-09-28 |
| Apache Kafka | 4.3.1 | Apache-2.0 | Yes | Yes | none | none | none | `apache/kafka` LICENSE [S4] | 2026-09-28 |
| Debezium | 3.6.1 | Apache-2.0 | Yes | Yes | none | none | none (Red Hat build is optional support, not a feature gate) | `debezium/debezium` LICENSE.txt [S5] | 2026-09-28 |
| Apache Flink | 2.1.3 | Apache-2.0 | Yes | Yes | none | none | none | `apache/flink` LICENSE [S6] | 2026-09-28 |
| Apache Spark | 4.1.3 | Apache-2.0 | Yes | Yes | none | none | none | `apache/spark` LICENSE [S7] | 2026-09-28 |
| ClickHouse | 26.8 LTS | Apache-2.0 | Yes | Yes | none on the OSS edition | none | none needed. ClickHouse Cloud (managed backups, ClickPipes, compute-compute separation, multi-zone HA) is a separate paid service; the self-hosted OSS edition carries MergeTree, Iceberg, and row policies in full | `ClickHouse/ClickHouse` LICENSE [S8]; pricing [S9] | 2026-09-28 |
| PostgreSQL | 18.x | PostgreSQL License | Yes | Yes | none | none (permissive) | none | `postgres/postgres` COPYRIGHT [S10] | 2026-09-28 |
| Dagster | 1.13.x | Apache-2.0 | Yes | Yes | none on the OSS edition | none | none needed. Dagster+ (managed infrastructure, catalog search, cost insights, SSO/RBAC, uptime SLA) is a separate paid product from $10/month; `@asset_check`, the capability the platform depends on, is in the OSS edition | `dagster-io/dagster` LICENSE [S11]; pricing [S12] | 2026-09-28 |
| Apicurio Registry | 3.3.x | Apache-2.0 | Yes | Yes | none | none | none | `Apicurio/apicurio-registry` LICENSE [S13] | 2026-09-28 |
| OpenLineage | 1.53.0 | Apache-2.0 | Yes | Yes | none | none | none | `OpenLineage/OpenLineage` LICENSE [S14] | 2026-09-28 |
| Marquez | 0.51.x | Apache-2.0 | Yes | Yes | none | none | none | `MarquezProject/marquez` LICENSE [S15] | 2026-09-28 |
| Prometheus | 3.14.0 | Apache-2.0 | Yes | Yes | none | none | none (CNCF project; vendor support optional) | `prometheus/prometheus` LICENSE [S16] | 2026-09-28 |
| Grafana | 13.x | AGPL-3.0 | Yes | Yes | none (AGPL permits commercial use) | **Strong network copyleft.** If Grafana is modified and offered over a network, the modified source must be offered to users. Using it unmodified and provisioning dashboards as code does not trigger this | none needed. Grafana Enterprise and paid Grafana Cloud add exclusive data-source plugins, RBAC/team sync, reporting, SSO and query caching; all outside the platform's dependency set | `grafana/grafana` LICENSE [S17]; licensing page [S18]; Enterprise docs [S19] | 2026-09-28 |
| Alertmanager | 0.34.x | Apache-2.0 | Yes | Yes | none | none | none | `prometheus/alertmanager` LICENSE [S20] | 2026-09-28 |
| Helm | 4.3.0 | Apache-2.0 | Yes | Yes | none | none | none | `helm/helm` LICENSE [S21] | 2026-09-28 |
| OpenTofu | 1.12.0 | MPL-2.0 | Yes | Yes | none | **Weak, file-level copyleft.** Modifications to MPL-licensed files must be published under the MPL. Using it unmodified, as the platform does, creates no obligation | none | `opentofu/opentofu` LICENSE [S22] | 2026-09-28 |
| Podman | 6.1.x | Apache-2.0 | Yes | Yes | none | none | none | `containers/podman` LICENSE [S23] | 2026-09-28 |

**Verdict on the nineteen: all nineteen are OSI-approved open source, free of charge, with no commercial-use restriction and no paid-only capability the platform depends on.** Two carry an obligation worth recording: Grafana's AGPL network copyleft (Section 3) and OpenTofu's MPL file-level copyleft. Neither is triggered by the platform's intended use.

## 2. The four documented fallbacks

| Component | Licence | OSI-approved | Free of charge | Commercial-use restriction | Copyleft obligation | Paid-only capabilities the platform needs | Source | Accessed |
|---|---|---|---|---|---|---|---|---|
| Lakekeeper | Apache-2.0 | Yes | Yes | none | none | none | `lakekeeper/lakekeeper` LICENSE [S24] | 2026-09-28 |
| RustFS | Apache-2.0, with a discretionary contributor agreement | Yes | Yes | none on the software itself | none on the software. **Governance risk:** the CLA grants RustFS, Inc. a copyright licence to relicense contributions "under any license, including proprietary or commercial licenses and open-source licenses, at RustFS's sole discretion", so a future release could be relicensed | none | `rustfs/rustfs` LICENSE and CLA.md [S25] | 2026-09-28 |
| Karapace | Apache-2.0 | Yes | Yes | none | none | none | `Aiven-Open/karapace` LICENSE [S26] | 2026-09-28 |
| Apache Airflow | Apache-2.0 | Yes | Yes | none | none | none | `apache/airflow` LICENSE [S27] | 2026-09-28 |

**Verdict on the fallbacks: all four are free and OSI-approved.** RustFS's risk is a *governance* risk (the vendor can relicense future code), not a use restriction on the version in hand. That is consistent with its current status as a fallback that must not hold irreplaceable data, and it does not change the licence verdict for the code as shipped.

## 3. The four datasets

| Dataset | Licence | OSI-approved | Free of charge | Commercial-use restriction | Copyleft obligation | Source | Accessed |
|---|---|---|---|---|---|---|---|
| TPC-C | TPC End User License Agreement v2.2 (permission-with-notice) | No - not an open-source licence | Yes ("THE TPC SOFTWARE IS AVAILABLE WITHOUT CHARGE FROM TPC") | Not prohibited, but the grant is "restricted, non-exclusive, revocable"; public disclosure of performance results is restricted to a TPC Benchmark Result, an academic or research effort that states no marketing position, or a use that labels the results not comparable to TPC Benchmark Results. No fee may be charged for distributing the software. No warranty and no express patent grant. Subject to US export control | none | TPC EULA v2.2 [S28] | 2026-09-28 |
| TPC-H | TPC End User License Agreement v2.2 (same terms as TPC-C) | No | Yes | As TPC-C | none | TPC EULA v2.2 [S28] | 2026-09-28 |
| RIPE Atlas | RIPE Atlas Service Terms and Conditions (v2.0; current v3.4/v4 carries the same clause) | No - data terms, not a software licence | Yes | **Research use is explicitly permitted; "any commercial use of the RIPE Atlas Data is subject to prior permission by the RIPE NCC".** No copyleft or share-alike on the data. The Atlas probe source code is GPLv3, but the platform consumes data, not probe software | none on the data | RIPE Atlas Terms v2.0 [S29]; current terms [S30]; RIPE Atlas legal page [S31] | 2026-09-28 |
| ONSPD | Open Government Licence v3.0 for Great Britain (derived from Code-Point Open); Northern Ireland `BT` postcodes under a Northern Ireland End User Licence (internal business use only) | No - OGL v3.0 is an open-data licence, not OSI-approved | Yes for GB data | **GB data is free to reuse with three mandatory attributions** (OS, Royal Mail, ONS). **NI `BT` postcodes are internal-business-use only; commercial use requires a separate licence from Land and Property Services.** The data.gov.uk catalogue records "No Licence Provided", which is a metadata gap; the authoritative licence is the ONSPD user guide | none | ONSPD User Guide [S32] | 2026-09-28 |

**ADR-0009 verification: both recorded positions still hold.** The RIPE Atlas commercial carve-out and the ONSPD Northern Ireland restriction are unchanged in the current terms, and the three ONSPD attributions are confirmed (the user guide states "Contains OS data (c) Crown copyright and database right", "Contains Royal Mail data (c) Royal Mail copyright and database right", and "Source: Office for National Statistics licensed under the Open Government Licence v.3.0"). The RIPE Atlas clause is present verbatim in both the v2.0 PDF that ADR-0009 cites and the current v3.4/v4 document.

## 4. Base images and runtimes

| Item | Licence | OSI-approved | Free of charge | Commercial-use restriction | Copyleft obligation | Paid-only capabilities the platform needs | Source | Accessed |
|---|---|---|---|---|---|---|---|---|
| Eclipse Temurin JDK 17 | GPLv2 with the Classpath Exception | Yes | Yes | none | **Weak, scoped copyleft.** Modifications to the JDK itself must be GPL; the Classpath Exception means applications that run on or link against it are unaffected. The platform runs Temurin unmodified | none (Adoptium is free; commercial support vendors exist but are not required) | `adoptium/jdk` LICENSE [S33] | 2026-09-28 |
| Python 3.12 | Python Software Foundation License Version 2 (PSF-2.0) | Yes | Yes | none | none (permissive) | none | `python/cpython` LICENSE [S34] | 2026-09-28 |
| OCI images published by the components | Covered by the component licence above; images may bundle additional third-party components under their own licences | n/a | Yes for the official free images used | none known for the images the platform uses | Inherited from bundled components (for example, the Grafana image is AGPL) | none known | Component repositories above | 2026-09-28 |

The base image line is a **partial** verification. The official images for every component in the stack are free to pull and run, and none of the platform's chosen images is a paid or gated image. What was *not* done is a full enumeration of every transitive licence inside each image; that requires an SBOM, which is listed under "Could not verify".

## 5. Not free, or restricted - and the consequence for the platform

Nothing in the nineteen components or the four fallbacks is non-free, source-available-only, or gated. The restrictions are all on **data**, plus two obligations that are conditional. This is the separated list the ticket asked for.

| Item | What is restricted | Consequence for the platform |
|---|---|---|
| **RIPE Atlas data** | Research use permitted; **commercial use requires prior permission from the RIPE NCC** | The portfolio must stay non-commercial. It must not be monetised or presented inside a commercial context, and any commercial use needs prior written permission. This is why the portfolio's non-commercial framing is stated rather than assumed. No action needed for the current use |
| **ONSPD Northern Ireland `BT` postcodes** | Internal business use only under the NI End User Licence; commercial use needs a separate LPS licence | The `BT` exclusion filter in the ONSPD ingest is mandatory, not optional. Published silver and gold tables must exclude `BT` postcodes and document that they did. The three attributions (OS, Royal Mail, ONS) must be displayed wherever the data is used |
| **TPC-C and TPC-H** | Permission-with-notice, not open source; revocable; publication of performance results restricted; no fee may be charged for distribution; no express patent grant; US export control | Keep the TPC EULA and its notices in the repository. Do not charge for distributing the TPC tools. Any published result must be labelled as not comparable to a TPC Benchmark Result unless it is an authorised result or a non-marketing academic or research effort. Do not rely on a patent indemnity, because none is granted. The TPC-H generator must be declared (the official TPC tools, not the unlicensed mirror) |
| **Grafana AGPL-3.0** | Conditional: strong network copyleft if modified and offered over a network | Keep Grafana unmodified. Dashboards-as-code live in Git and are applied through provisioning, which does not modify Grafana and so does not trigger the source-offer obligation. If a patch to Grafana is ever needed, publish the patch. The AGPL does **not** restrict commercial use and does **not** restrict running Grafana for the platform |
| **OpenTofu MPL-2.0** | Conditional: file-level copyleft | Use OpenTofu unmodified, as intended. Any modification to an MPL-licensed file must be published under the MPL. Configuration written in HCL is not a modification of OpenTofu and carries no obligation |
| **RustFS** | Not a use restriction. The CLA lets RustFS relicense contributions under a proprietary licence at its sole discretion | Keep RustFS a fallback only. Do not make it load-bearing for data that cannot be lost, consistent with the object-storage decision. This is a longevity risk, not a licence failure |
| **Eclipse Temurin JDK 17** | Conditional: GPLv2 for the JDK itself, Classpath Exception for applications | Run Temurin unmodified. Applications built and run on it are not GPL-encumbered. Any modification to the JDK itself would have to be released under the GPL |

**Context on already-rejected items, confirmed by this audit.** Terraform upstream is BUSL-1.1, source-available and not OSI-approved, which is why OpenTofu replaced it. Confluent Schema Registry is under the Confluent Community License, source-available with an excluded-purpose non-compete, which is why Apicurio and Karapace were chosen instead. MinIO Community Edition is AGPL and its repository was archived on 2026-04-25, which is why SeaweedFS was chosen. None of these reappears in the stack.

## 6. Paid-only (open-core) capabilities - none that the platform depends on

Three components in the stack have a commercial edition. In each case the capability the platform depends on is in the free edition, and the paid features are outside the platform's scope.

- **Grafana Enterprise and Grafana Cloud.** Grafana's own documentation states that Enterprise "is a commercial edition of Grafana that includes additional features not found in the open source version", including exclusive data-source plugins. The platform's use is dashboards-as-code against Prometheus and ClickHouse, all of which is in the AGPL OSS edition. [S18][S19]
- **ClickHouse Cloud.** The paid service adds managed backups, ClickPipes, compute-compute separation and multi-zone availability. The self-hosted Apache-2.0 edition carries MergeTree, the Iceberg integration and row policies, which is what the serving layer uses. [S8][S9]
- **Dagster+.** The paid product adds managed infrastructure, catalog search, cost insights and SSO/RBAC from $10/month. The data-quality gate the platform depends on, `@asset_check` with `blocking=True`, is in the Apache-2.0 OSS edition. [S11][S12]

No other component in the stack gates a needed feature behind a paid edition.

## 7. Could not verify

- **The full transitive licence set inside each OCI image.** The official images are free and none is gated, but no SBOM was generated, so the complete list of bundled third-party licences (base OS packages, native libraries) is not enumerated. Recommendation: generate an SBOM per pinned image digest as part of the build, and re-check the Grafana image specifically because its top-level licence is AGPL.
- **Every optional plugin for every component.** Feature lists were checked for the capabilities the platform names, but a component with a plugin ecosystem (Grafana, Dagster, Airflow) could in principle have an optional plugin that is paid. The platform's declared plugin set is free.
- **RustFS's future licence.** The CLA permits a proprietary relicense; the current code is Apache-2.0. This is unknowable in advance and is why RustFS stays a fallback.
- **The ONSPD catalogue metadata.** data.gov.uk records "No Licence Provided" for the ONSPD; the authoritative licence is the user guide, which was read. The metadata gap is a catalogue defect, not a licence gap.
- **The RIPE Atlas terms version numbering.** The v2.0 PDF cited by ADR-0009 and the current document (hosted as v3.4 with a v4 filename) both carry the commercial-use clause verbatim; the clause is stable, but the version label on the current document is inconsistent between the file name and its contents.

## 8. Sources

All accessed 2026-09-28.

- [S1] Apache Iceberg LICENSE - https://raw.githubusercontent.com/apache/iceberg/main/LICENSE
- [S2] Apache Polaris LICENSE - https://raw.githubusercontent.com/apache/polaris/main/LICENSE
- [S3] SeaweedFS LICENSE - https://raw.githubusercontent.com/seaweedfs/seaweedfs/master/LICENSE
- [S4] Apache Kafka LICENSE - https://raw.githubusercontent.com/apache/kafka/trunk/LICENSE
- [S5] Debezium LICENSE.txt - https://raw.githubusercontent.com/debezium/debezium/main/LICENSE.txt
- [S6] Apache Flink LICENSE - https://raw.githubusercontent.com/apache/flink/master/LICENSE
- [S7] Apache Spark LICENSE - https://raw.githubusercontent.com/apache/spark/master/LICENSE
- [S8] ClickHouse LICENSE - https://raw.githubusercontent.com/ClickHouse/ClickHouse/master/LICENSE
- [S9] ClickHouse pricing and cloud tiers - https://clickhouse.com/pricing ; https://clickhouse.com/docs/products/cloud/features/cloud-tiers
- [S10] PostgreSQL COPYRIGHT - https://raw.githubusercontent.com/postgres/postgres/master/COPYRIGHT
- [S11] Dagster LICENSE - https://raw.githubusercontent.com/dagster-io/dagster/master/LICENSE
- [S12] Dagster pricing - https://dagster.io/pricing/
- [S13] Apicurio Registry LICENSE - https://raw.githubusercontent.com/Apicurio/apicurio-registry/main/LICENSE
- [S14] OpenLineage LICENSE - https://raw.githubusercontent.com/OpenLineage/OpenLineage/main/LICENSE
- [S15] Marquez LICENSE - https://raw.githubusercontent.com/MarquezProject/marquez/main/LICENSE
- [S16] Prometheus LICENSE - https://raw.githubusercontent.com/prometheus/prometheus/main/LICENSE
- [S17] Grafana LICENSE (AGPL-3.0) - https://raw.githubusercontent.com/grafana/grafana/main/LICENSE
- [S18] Grafana licensing page - https://grafana.com/licensing/
- [S19] Grafana Enterprise documentation - https://grafana.com/docs/grafana/latest/introduction/grafana-enterprise/
- [S20] Alertmanager LICENSE - https://raw.githubusercontent.com/prometheus/alertmanager/main/LICENSE
- [S21] Helm LICENSE - https://raw.githubusercontent.com/helm/helm/main/LICENSE
- [S22] OpenTofu LICENSE (MPL-2.0) - https://raw.githubusercontent.com/opentofu/opentofu/main/LICENSE
- [S23] Podman LICENSE - https://raw.githubusercontent.com/containers/podman/main/LICENSE
- [S24] Lakekeeper LICENSE - https://raw.githubusercontent.com/lakekeeper/lakekeeper/main/LICENSE
- [S25] RustFS LICENSE and CLA - https://raw.githubusercontent.com/rustfs/rustfs/main/LICENSE ; https://raw.githubusercontent.com/rustfs/rustfs/main/CLA.md ; https://rustfs.org/developer/license
- [S26] Karapace LICENSE - https://raw.githubusercontent.com/Aiven-Open/karapace/main/LICENSE
- [S27] Apache Airflow LICENSE - https://raw.githubusercontent.com/apache/airflow/main/LICENSE
- [S28] TPC End User License Agreement v2.2 - https://www.tpc.org/TPC_Documents_Current_Versions/txt/eula.txt
- [S29] RIPE Atlas Service Terms and Conditions v2.0 - https://www-static.ripe.net/static/rnd-ui/atlas/media/legal/RIPEAtlasServiceTermsandConditionsV2.0.pdf
- [S30] RIPE Atlas Service Terms and Conditions, current - https://www.ripe.net/documents/4136/RIPE_Atlas_Service_Terms_and_Conditions_v3.4.pdf
- [S31] RIPE Atlas legal information - https://atlas.ripe.net/docs/legal-Information
- [S32] ONS Postcode Directory User Guide - https://www.ons.gov.uk/file?uri=/aboutus/transparencyandgovernance/freedomofinformationfoi/listofpostcodesandcorrespondinglocalauthorities/onspduserguideaug2023.pdf
- [S33] Eclipse Temurin JDK LICENSE (GPLv2 with Classpath Exception) - https://raw.githubusercontent.com/adoptium/jdk/master/LICENSE
- [S34] CPython LICENSE (PSF-2.0) - https://raw.githubusercontent.com/python/cpython/main/LICENSE
