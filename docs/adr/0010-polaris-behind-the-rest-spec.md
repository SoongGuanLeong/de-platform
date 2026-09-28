# Reach Polaris only through the Iceberg REST spec, with Lakekeeper as the fallback

**Status:** accepted

The catalog is Apache Polaris 1.7.0, the posting's tool and an ASF Top-Level Project since 15 February 2026. The platform talks to it only through the Iceberg REST specification, never through Polaris-proprietary admin APIs, and keeps the catalog's state in PostgreSQL. The specification, not the implementation, is the asset: every engine reaches the catalog through the same REST contract, so replacing Polaris with Lakekeeper changes a URI and credentials and nothing else. The risk that would have forced the fallback is closed by measurement: Polaris 1.7.0 vends a real prefix-scoped SeaweedFS STS credential on `loadTable`, and a read outside that prefix is refused with AccessDenied.

## Considered options

- **Lakekeeper.** Not rejected; the documented fallback. Apache-2.0, Rust, the same REST spec, OpenFGA authorisation, Postgres backend, hours to switch.
- **Unity Catalog OSS, Nessie, Hudi/Hadoop catalog, Dremio OSS.** Rejected: each costs days to weeks and none is the posting's tool.
- **Design catalog-agnostic with SeaweedFS's own catalog as the default.** Rejected: it would leave the governance plane (namespaces, roles, credential vending) unexercised, and the posting names Polaris.

## Consequences

The switch to Lakekeeper costs hours only while the running platform avoids Polaris-proprietary admin APIs; the one-time bootstrap script may use the Management API. Polaris is metadata-plane only and enforces no column or row policy, so column-level control lives in ClickHouse (ADR-0004). The Polaris minor is pinned, because it ships a minor roughly every six weeks, and the catalog state stays in Postgres rather than a Polaris-specific store. The vended credential is a storage-prefix boundary, not a table-identity boundary. Evidence: ticket [The technology-selection matrix](https://github.com/SoongGuanLeong/de-platform/issues/8), research 03, 04 and 08.
