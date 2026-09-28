# Treat the prior Olist repository as reference-only, and licence this repository Apache-2.0

**Status:** accepted

`github.com/SoongGuanLeong/data_pipelines_batch_stream_vector` is a reference and a source of design evidence, not a codebase to port. No code, configuration or SQL is copied from it by default, and its assets are recorded by disposition in [`docs/salvage-list.md`](../salvage-list.md) rather than transplanted. The reason is engineering, not legal. The inventory of that repository ([`docs/research/09-olist-repo-inventory.md`](../research/09-olist-repo-inventory.md)) found 16 verified logic bugs, zero tests across 2,718 lines of PySpark, and the reasoning behind its hardest code living in notebook markdown rather than in modules, so a port would carry coupling that no reader could see. Copying remains available as a recorded exception: a future copy must name its source, the reason the source cannot be explained and rewritten, and the test that pins the copied behaviour.

This repository is licensed Apache-2.0. The prior repository is left unlicensed and archived, because it is a frozen reference copy and licensing it would invite reuse of code this project is deliberately rewriting.

## Considered options

- **Copy the assets the inventory calls reusable.** Rejected: the inventory's own defect list is the argument against it. `replace_by_key` was described as "concurrency-safe and correct" and its DELETE and INSERT commit as two separate snapshots, so a reader between them sees the affected keys missing. `gold/facts/orders.py:91-95` carries a filter whose only explanation is a comment. A port inherits both without inheriting the understanding.
- **Reimplement only the assets the inventory doubts, and copy the rest.** Rejected: it draws the line in the wrong place. The assets that look mechanically safe are the configuration files, and those are the ones whose contents are dictated by components this platform has already replaced.
- **Copy nothing, and license the prior repository permissively.** Rejected: adding a licence to a repository being retired licenses the code this decision exists to keep out.
- **Leave this repository unlicensed.** Rejected: an unlicensed repository is all-rights-reserved, so a portfolio repository that reviewers cannot reuse is a strange artifact.

## Consequences

The provenance question is closed. Every line in this repository is authored here, so there is no third-party code, no attribution obligation and no inherited coupling. The cost is concentrated in the two places the prior repository did unusual work, the Polaris Management API automation and the Iceberg write patterns, both of which are reimplemented from their written design rather than lifted.

The prior repository is public and contains committed credentials: a PostgreSQL password, two Polaris OAuth2 client secrets, MinIO credentials and a Polaris administrator password. The root cause is mechanical rather than careless, since its Polaris bootstrap script copies a tracked file to `.bak` and mints a fresh secret into it on every run, while `.gitignore` does not exclude `*.bak`. The repository was never deployed, so no running service accepts those values. Retiring the repository is the remedy rather than rotation, and it is tracked separately. History rewriting is rejected because it does not unpublish a value that forks, clones and crawlers have already seen, and because it would rewrite the reference copy this decision depends on.

The reference-only rule is what makes the no-hidden-coupling claim defensible, so it is load-bearing rather than stylistic. If a future copy is ever made, the exception record is what keeps that claim true. See [`docs/salvage-list.md`](../salvage-list.md) for the per-asset dispositions and the mapping from prior-repository assets to the map's unspecified items.
