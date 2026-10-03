"""The collector's persisted timepoint cursor.

The live RIPE stream is at-most-once and has no resume token, so the cursor is
the REST backfill's resume point: the last probe timestamp already produced for
each measurement. It is written atomically (a temporary file then
`os.replace`) so a crash mid-write leaves the previous cursor intact rather
than a truncated file, and a restart resumes from the cursor rather than
re-fetching the whole backfill window (ADR-0014).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

FORMAT_VERSION = 1


@dataclass
class TimepointCursor:
    """A per-measurement last-produced probe timestamp, in epoch seconds."""

    values: dict[int, int] = field(default_factory=dict)

    def get(self, msm_id: int) -> int | None:
        return self.values.get(msm_id)

    def advance(self, msm_id: int, timepoint: int) -> None:
        current = self.values.get(msm_id)
        if current is None or timepoint > current:
            self.values[msm_id] = timepoint

    def resume_start(self, msm_id: int, *, now: int, window: int) -> int:
        """Where the backfill starts: the cursor, or `window` seconds back.

        Clamped to `now`: a probe clock can run ahead of the server's, so a
        cursor recorded from a probe timestamp can be later than the request
        time, and the results endpoint rejects a start in the future.
        """
        current = self.values.get(msm_id)
        if current is None:
            return now - window
        return min(current, now)


class CursorStore:
    """Reads and atomically writes a `TimepointCursor` as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def read(self) -> TimepointCursor:
        if not self.path.exists():
            return TimepointCursor()
        with open(self.path, encoding="utf-8") as handle:
            document = json.load(handle)
        raw = document.get("timepoints", {}) if isinstance(document, dict) else {}
        return TimepointCursor({int(key): int(value) for key, value in raw.items()})

    def write(self, cursor: TimepointCursor) -> None:
        payload = {
            "version": FORMAT_VERSION,
            "timepoints": {str(key): int(value) for key, value in sorted(cursor.values.items())},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
