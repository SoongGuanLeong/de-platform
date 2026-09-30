# Writing conventions

Prose conventions for this repo's documents. Each exists because a term or a marker had drifted into more than one form. Every marker example below uses `<angle-bracket>` placeholders, so a marker scan can tell an example from a real marker without excluding this file.

Scope: this file holds conventions about prose, not vocabulary. A term that names a platform domain concept belongs in `CONTEXT.md` rather than here; [domain.md](domain.md) covers how to use it.

## Name the research input "the assignment"

A report in `docs/research/` is produced from a task document. That document is **the assignment**.

| Write | Do not write | Why |
| --- | --- | --- |
| the assignment | the brief | "the brief" already names the Project Mission in `docs/mission/MISSION.md:1` |
| the assignment | the task | "the task" collides with Flink's `TaskManager`, Airflow and Prefect tasks, and task graphs |

Use it for the input and for the claims made in it: "the assignment says", "the assignment's premise", "corrections to the assignment". Four research documents already use this form in their own header metadata, as `**Ticket:** ... (no issue number was supplied with this assignment)`.

`docs/mission/MISSION.md` is a verbatim preservation copy and keeps its own "this brief", which refers to the Project Mission rather than to a research assignment. Do not edit that file: it is one of the preservation copies listed under Headings below.

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

## Headings

- One H1 per document, and it is the document's title. Sections below it use `##`, and their subsections `###`.
- Sentence case, leaving proper nouns and acronyms alone: `# 13 - Lineage backend comparison`, not `# 13 - Lineage Backend Comparison`.
- A research report's H1 carries its number, as `NN - <title>`.

Do not add a level because content feels important. A section is `##` because it is a section. A document that puts its section titles at H1 flattens the outline and breaks any table of contents built from it.

### Preservation copies are exempt

A document that reproduces another document verbatim is not edited to conform. It keeps its own headings, in their original case and at their original level, because the copy's value is that it is unaltered.

| Copy | Exempt portion | Why |
| --- | --- | --- |
| `docs/mission/MISSION.md` | the whole file, 36 H1s in title case | the brief is reproduced verbatim from its own `# Project Mission` heading |
| `docs/research/09-olist-repo-inventory.md` | line 15 to the end, whose H1 is the report's own title in title case | the body matches `opencode.db` row `prt_0e141f8df0015Z8W9wa1i0yx9p` line for line, 443 lines |

The exemption covers the reproduced portion only. In `09`, lines 1 to 13 are this repo's own header and do follow the rules above: the H1 is sentence case and carries the `NN - ` prefix.

A heading in a preservation copy is not a defect, and both entries above were checked against their source before being left alone.

## Tables

A table cell that has nothing in it carries one of two words, both lower case:

| Write | Meaning |
| --- | --- |
| `n/a` | the column does not apply to that row |
| `none` | the column applies, and there is nothing |

`N/A` and `None` were each in use as well, for the same two meanings, in 72 cells, and are replaced. Choosing between `n/a` and `none` is not mechanical: ask whether the column applies to the row at all.

Lower case when the word names an absent value, including at the start of a longer cell: `none published`, `n/a (Java)`, `none; [section 13 item 11](completion-bar.md) records it`, `none needed. ClickHouse Cloud ...`.

Capitalise it when it opens a sentence instead, because there it is ordinary prose and a cell's first word is capitalised everywhere else: `None of its own; it is derived`, `None. Writes data files only [S4], [S6], [S12]`. A bolded verdict follows the same rule, as `**None.** Synthetic, US-shaped geography against UK postcodes` in a column whose other values are `**Genuine.**` and `**Time-only.**`. The test is whether the word names the absence of a value or is the subject of a sentence.

Do not use `-`. It was doing both jobs, in 29 cells across six tables, so a reader cannot tell which of the two it means.

A cell left blank is not a way to say nothing either. Two tables have blank cells, and both are structural rather than a placeholder: the `**Total**` row in `docs/system-architecture.md` has no members to list, and the 10x and 100x rows in `docs/cloud-architecture.md` section 6.1 leave the per-class split unasserted on purpose.

Table shape is uniform and stays that way: a leading and a trailing pipe, a plain `---` separator row, and a blank line before the table. Two tables lack that blank line, and both are legitimate: `docs/research/02-object-storage.md` indents one inside a list item, and `docs/research/09-olist-repo-inventory.md` has one inside its preserved body.
