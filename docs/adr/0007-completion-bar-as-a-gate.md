# Make the completion bar a validated gate, not a written convention

**Status:** accepted

A capability counts as finished only when it appears in the capability register with the evidence the completion bar requires, and the CI validates that register. The alternative, a written standard that a reader is trusted to apply, fails at exactly the point the standard exists to defend: a portfolio project that looks finished from the outside. Prose cannot distinguish an implemented capability from a plausible description of one, and the author is the least reliable judge of their own coverage. The register converts the claim into a list of named instances, and the CI converts the list into a check that can fail.

The gate is deliberately cheap. It validates fields and links only, and never re-runs evidence: that every class has a representative instance, that every complete instance carries at least one behaviour item, that every evidence link and budget reference resolves, that every not-applicable entry carries a reason, and that compose files stay inside the portable subset. Expensive evidence is judged by a human, from the raw artifacts the evidence items point at.

## Considered options

- **A written convention only.** Rejected: it cannot fail, so it proves nothing about coverage, and it is the shape the failure mode takes.
- **A gate that re-runs the evidence.** Rejected: the load-bearing evidence needs the streaming or benchmark profile, which cannot run in CI at 7 to 8 GB of free RAM, so a re-running gate would either be skipped or would force the claims down to what fits in CI.
- **Per-capability documents instead of a register.** Rejected: eleven documents drift apart and cannot be validated mechanically, and the register is what makes the instance list auditable.
- **A register without a behaviour-versus-signal distinction.** Rejected: most available metrics prove the mechanism is observable rather than that the claim holds, so a signal-only register would pass while the platform remained unproven under fault.

## Consequences

The standard lives in `docs/completion-bar.md`, the register in `docs/completion-bar.yaml`, the thresholds in `docs/budgets.yaml`, and the evidence under `docs/evidence/`. A claim of completion now requires a named instance, at least one behaviour item, and a resolving budget reference, which raises the cost of claiming completion and lowers the cost of checking it.

Two consequences are easy to get wrong. The register is forward-looking: it ships empty, because the map is planning-only and no platform code exists, so an empty register is the correct state rather than an unfinished task. And the gate checks paperwork, not truth: a dishonest evidence item passes the gate, which is why the evidence standard requires the raw artifact and the exact command, so that a sceptic checks the claim rather than the register.

The instance granularity is deliberately per instance rather than per class, so that one working topic cannot speak for Kafka ingestion as a whole, with one representative instance per class carrying the deeper benchmark-grade evidence to bound the cost. Evidence: the ticket is [The completion bar](https://github.com/SoongGuanLeong/de-platform/issues/6) on map #9.
