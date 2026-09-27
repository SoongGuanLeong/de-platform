# Use OpenTofu instead of Terraform, deviating from the posting's wording

**Status:** accepted

Infrastructure is authored in OpenTofu rather than Terraform, even though the posting names Terraform explicitly. HashiCorp relicensed Terraform from MPL-2.0 to BUSL 1.1 in August 2023, which is a source-available licence rather than an open-source one, and Terraform has no foundation steward, so it fails the support-and-longevity rubric by which this effort admits every dependency. OpenTofu was created in September 2023 as the direct response to that relicensing, is governed by the Linux Foundation, is MPL-2.0, and is compatible with HCL, the Terraform state format and the provider ecosystem by design.

## Considered options

- **Use Terraform, because the posting names it.** Rejected: the rubric is the admission test for every dependency and Terraform fails it on both licence and governance. A deviation is defensible where the ADR records why, and the posting accepts equivalents.
- **Use a community fork without a foundation behind it.** Rejected: that is what OpenTofu is, except that OpenTofu carries Linux Foundation governance and a funded maintenance commitment.

## Consequences

The infrastructure modules are a deliberate deviation from the posting's wording, and this ADR is the record of that deviation rather than an accident of tooling. The swap is cheap in both directions: HCL is the lingua franca and the state and provider ecosystems are compatible by design, so reverting costs under a day if the rubric ever changes. One thing to re-check rather than assume: OpenTofu's founding commitment was a minimum of 18 full-time developers for at least five years from September 2023, a window that expires at the same five-year horizon this project is planned against, so it should be revisited around 2028. Evidence is the support-and-longevity audit in `docs/research/03-longevity-audit.md`; matrix row M19.
