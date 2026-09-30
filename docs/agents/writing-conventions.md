# Writing Conventions

Prose conventions for this repo's documents. Each exists because a term or a marker had drifted into more than one form.

## Name the research input "the assignment"

A report in `docs/research/` is produced from a task document. That document is **the assignment**.

| Write | Do not write | Why |
| --- | --- | --- |
| the assignment | the brief | "the brief" already names the Project Mission in `docs/mission/MISSION.md:1` |
| the assignment | the task | "the task" collides with Flink's `TaskManager`, Airflow and Prefect tasks, and task graphs |

Use it for the input and for the claims made in it: "the assignment says", "the assignment's premise", "corrections to the assignment". Four research documents already use this form in their own header metadata, as `**Ticket:** ... (no issue number was supplied with this assignment)`.

`docs/mission/MISSION.md` is a verbatim preservation copy and keeps its own "this brief", which refers to the Project Mission rather than to a research assignment. Do not edit that file.
