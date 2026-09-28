# Record the dataset licence position and the obligations it creates

**Status:** accepted

The four selected sources are usable for a published portfolio, but each carries an obligation a reviewer will ask about, so the obligations are recorded here rather than left in dated research notes.

**RIPE Atlas** is the one real boundary. The RIPE Atlas Service Terms V2.0 permit research use explicitly and impose no copyleft or share-alike, but "any commercial use of the RIPE Atlas Data is subject to prior permission by the RIPE NCC". A public portfolio is non-commercial research and is permitted. Presenting this work inside a commercial context, or monetising it, would need prior written permission. The same terms state that RIPE may supply Atlas data to third parties for scientific and statistical purposes and that this may continue after the service ends, which is a longevity argument worth keeping.

**ONSPD** is OGL v3.0 for England, Wales, Scotland, the Channel Islands and the Isle of Man, with three mandatory attributions (OS, Royal Mail and ONS). The exception is Northern Ireland: postcodes beginning with `BT` are supplied under a Northern Ireland End User Licence for **internal business use only**, and commercial use needs a separate licence from Land and Property Services. **The platform excludes `BT` postcodes from published silver and gold tables and documents that it did.** The data.gov.uk catalogue records the licence as "No Licence Provided", which is a catalogue metadata gap; the authoritative licence is the ONSPD user guide.

**TPC-C and TPC-H** are TPC permission-with-notice, which is a permission notice rather than an open-source licence: attribution is mandatory, and there is no warranty and no patent grant. The official TPC tools zip is used for TPC-H rather than the `databricks/tpch-dbgen` mirror, which has no licence file. Because DuckDB's `tpch` extension documents that its output differs from the specification, any published answer states which generator produced the data. The same EULA restricts publication of performance results: any throughput or latency figure measured on TPC-C or TPC-H data is labelled a result on TPC-derived data and is not presented as a TPC Benchmark Result, which needs TPC authorisation.

**Olist is excluded on licence.** Its data is CC BY-NC-SA 4.0: non-commercial and share-alike, and share-alike propagates to derived tables, so silver and gold tables built from it would inherit the restriction. A second and independent reason is that its change events would be synthesised from a static historical snapshot rather than being genuine live CDC. The restriction belongs to the dataset itself, separate from and additional to any code licence.

## Considered options

- **Record the licence position in the research reports only.** Rejected: research reports are dated evidence, not decisions, and an obligation that exists only in a research report is one that gets missed when the tables are built.
- **Keep the Northern Ireland `BT` postcodes and state the restriction.** Rejected: shipping a licence-restricted subset behind a note is a weaker position than excluding it and saying why.
- **Publish without stating the RIPE Atlas commercial carve-out.** Rejected: it is the kind of omission that turns a defensible non-commercial portfolio into a misrepresentation.
- **Reinstate Olist for its real data-quality defects.** Rejected: share-alike would propagate to every derived table, and the defects are not worth that.

## Consequences

The licence obligations are engineering requirements, not paperwork: a `BT` exclusion filter in the ONSPD ingest, the three ONSPD attribution statements displayed wherever the data is used, the TPC notices kept in the repository, and a declared TPC-H generator. The RIPE Atlas boundary constrains how the work may be presented, and it is why the portfolio's non-commercial framing is stated rather than assumed. The per-source licence table is in [`docs/dataset-selection.md`](../dataset-selection.md).

Evidence: the ticket is [The dataset combination and the data story](https://github.com/SoongGuanLeong/de-platform/issues/7) on map #9.
