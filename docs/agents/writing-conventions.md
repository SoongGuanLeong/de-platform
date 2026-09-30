# Writing Conventions

Prose conventions for this repo's documents. Each exists because a term or a marker had drifted into more than one form. Every example below uses `<angle-bracket>` placeholders, so a marker scan can tell an example from a real marker without excluding this file.

Scope: this file holds conventions about prose, not vocabulary. A term that names a platform domain concept belongs in `CONTEXT.md` rather than here; [domain.md](domain.md) covers how to use it.

## Name the research input "the assignment"

A report in `docs/research/` is produced from a task document. That document is **the assignment**.

| Write | Do not write | Why |
| --- | --- | --- |
| the assignment | the brief | "the brief" already names the Project Mission in `docs/mission/MISSION.md:1` |
| the assignment | the task | "the task" collides with Flink's `TaskManager`, Airflow and Prefect tasks, and task graphs |

Use it for the input and for the claims made in it: "the assignment says", "the assignment's premise", "corrections to the assignment". Four research documents already use this form in their own header metadata, as `**Ticket:** ... (no issue number was supplied with this assignment)`.

`docs/mission/MISSION.md` is a verbatim preservation copy and keeps its own "this brief", which refers to the Project Mission rather than to a research assignment. Do not edit that file.

## Mark a revision with `**Correction, <date> (<authority>).**`

When a document is revised after it was written, mark the revision in place rather than editing the original claim silently.

```
**Correction, <date> (<authority or circumstance>).**
```

- Bold the marker only; the claim that follows is not bold.
- The date is ISO, after a comma. A numbered correction puts the number first: `**Correction <n>, <date> (<authority>):**`.
- The parenthetical carries the authority (`ticket #15`) or the circumstance (`after peer review`, `after this ADR was accepted`). Every dated marker carries one.
- The terminator follows grammar: `.` when a new sentence follows, `:` when the marker's own sentence continues.
- A correction that is a whole section rather than a paragraph takes a heading instead, `## Correction, <date> (<authority>)`, with no terminator.

Do not use another noun. `Amended on`, `Amendment dated`, `Redaction` and `Revised` were all in use and are all replaced by this form. The action is still named in the sentence that follows, as "the values were redacted under ADR-0028".

A correction to the input itself, a wrong premise or framing in the assignment, is part of the report's argument from the start and carries no date: `**Correction to the assignment's premise (<subject>).**`, or `**Correction <n>:**` for a numbered series inside one document.

### Checking a document for conformance

Scope the check to the marker substring, not to the line. A line-level scan both over-counts and under-counts:

- `docs/research/11-schema-registry-comparison.md:29` is `**Correction 2:**`, which is undated, but the sentence after it cites the Apicurio ADR's own date. A line-level scan reads that as a dated marker. There are nine dated markers in the repository, not ten.
- A heading-form marker is only a marker at the start of a line. One shown mid-line, as the bullet above does, matches neither a bold pattern nor an anchored heading pattern, so a line-level scan misses it entirely.

A marker containing `<` and `>` is an example rather than a real marker. That one rule separates this file's examples from the corpus, so no path exclusion is needed.
