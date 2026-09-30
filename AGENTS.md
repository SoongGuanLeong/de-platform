# de-platform

A vendor-neutral data lakehouse / data platform, built as a portfolio project that demonstrates senior-level data-engineering depth.

The design is driven by a specific target job posting, cached verbatim at `~/projects/career-ops/data/jd-cache/031.md` (Senior Data Engineer - Data Lakehouse). The platform is scoped to that posting's actual requirements rather than to a generic tutorial or a collection of technologies.

**Current phase: implementation, at Phase 0 of `docs/implementation-roadmap.md`.** The planning map on this repo's issue tracker (labelled `wayfinder:map`) is closed, and the repository layout of `docs/adr/0026-one-repository-path-first.md` exists.

## Agent skills

### Issue tracker

Issues are tracked as GitHub Issues in `SoongGuanLeong/de-platform`, operated with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles with default label strings: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Writing conventions

Which word to use for a thing, how to mark a revision in place, how headings are cased and levelled, how a section of another document and an issue are cited, and what a table cell holds when it has nothing to hold - where more than one form was in use. See `docs/agents/writing-conventions.md`.
