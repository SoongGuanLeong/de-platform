# Minimise PII rather than mask it

**Status:** accepted

Direct PII that no query needs is dropped from the gold and serving tables rather than masked inside them. The nine named queries need `probe_id`, the resolved postcode area, RTT and ASN, and the TPC-C business keys and amounts, and none needs a name, an address, a phone or a probe IP. So the columns are removed, PII stays in restricted silver and engineering namespaces, and the one column deliberately exposed carries a ClickHouse `GRANT SELECT(col)` test. This also fits the authorisation seam: Polaris enforces no column-level access, so a gold table that kept a masked PII column would have no column-level control on the Spark path.

## Considered options

- **Keep PII in gold and mask it.** Rejected: it puts the data where the weaker engine governs it, and a masked column is still a column to classify, retain and delete.
- **Keep PII in gold and rely on table-level Polaris grants.** Rejected: it collapses a column-level requirement into a table-level control, so every consumer of the table sees the PII.
- **A separate PII register alongside the gold contracts.** Rejected: the contract already carries the column list and CI already fails on a schema break, so classification embedded in the contract cannot drift from the schema.

## Consequences

The quarantine table becomes the one place direct PII concentrates, since its payload is the rejected row, so it takes engineer and `dq_reader` access only and the shortest retention of any class, 30 days. The deletion path terminates in Iceberg because the serving CDC facts carry no customer key, and erasure completes only when the snapshots containing the row expire, so the PII-bearing tables take a shorter snapshot retention to bound that window. Evidence: ticket [Governance and data-quality specifics](https://github.com/SoongGuanLeong/de-platform/issues/14).
