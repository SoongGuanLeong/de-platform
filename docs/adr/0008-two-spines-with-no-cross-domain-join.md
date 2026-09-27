# Carry two independent data spines, and join nothing across them

**Status:** accepted

The platform ingests four sources that belong to two domains with no key relationship: a commerce spine (TPC-C for genuine Debezium binlog CDC, TPC-H for batch and serving) and a network spine (RIPE Atlas for a genuine live stream, ONSPD for UK geographic reference and SCD2 history). Both spines are carried by one platform, and **nothing joins them**. The posting names two ingestion paths, CDC from a relational database and real-time event streaming, and no public dataset honestly supplies both: TPC-C is the only source that yields real binlog change events without inventing them, and RIPE Atlas is the only source that is simultaneously live, large and messy for reasons its publisher documents rather than reasons we would invent. They are different businesses.

The temptation is to manufacture a join, by assigning synthetic regions to orders and correlating them against measured network quality. That was rejected. A manufactured key would produce an analysis no reviewer could trust, and it would make the platform's most obvious weakness invisible rather than stated. The platform's unity is therefore a control-plane claim rather than a business-process claim: one catalog, one lineage graph, one data-quality framework and one serving layer carry a CDC-fed OLTP mirror and a live measurement stream, and that claim is measurable.

The only cross-spine link is a shared clock. One time-axis correlation between TPC-C order volume and UK network quality is in scope, labelled as a correlation with no causality claimed. The genuine joins are inside the network spine: the spatial join from RIPE Atlas probe coordinates to ONSPD postcodes, and ONSPD's own release-over-release SCD2 history.

A second consequence is that **geography lives only in the network spine**. TPC-C's address columns are random strings with no real-world referent and TPC-H's `nation` and `region` are fictional, so there is no conformed geography dimension spanning the platform. M6's conformed-dimension claim is scoped to a spine.

## Considered options

- **Manufacture a region key to join orders to network measurements.** Rejected: the join would be invented, and an invented join is the single thing a senior interviewer is most likely to catch.
- **Drop the network spine and keep the commerce spine only.** Rejected: streaming would then be demonstrated only by the CDC topic, with no genuinely live source, which fails the requirement for a streaming centre of gravity.
- **Add Companies House to give the network spine a second real join.** Rejected: it joins neither commerce source either, it adds a fifth source, and it still does not close the commerce and network gap.
- **Split the platform into two independently justified halves with a shared control plane.** Rejected: it abandons the single-platform claim that M1, M9, M10 and M11 rest on.

## Consequences

The dataset selection and the per-source records live in [`docs/dataset-selection.md`](../dataset-selection.md). The absence of cross-domain joins is a named constraint rather than an omission, and the per-pair analysis is recorded there so that no later ticket re-derives a join that does not exist. Two costs are accepted: the combination answers fewer cross-source business questions than a single-domain platform would, and every downstream document must resist the pull to describe the two spines as one model. The benefit is that every claim the platform makes about its data is one a sceptic can check.

Evidence: the ticket is [The dataset combination and the data story](https://github.com/SoongGuanLeong/de-platform/issues/7) on map #9.
