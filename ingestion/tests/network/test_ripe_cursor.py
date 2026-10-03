"""Rate limiting, backoff and the persisted timepoint cursor.

The rate limiter and backoff are driven by an injected clock, so the assertions
are on state and computed waits rather than on wall-clock timing
(docs/testing-strategy.md section 9).
"""

from __future__ import annotations

import json
from pathlib import Path

from de_ingestion.network.ripe.cursor import CursorStore, TimepointCursor
from de_ingestion.network.ripe.ratelimit import Backoff, RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_rate_limiter_lets_the_first_call_through_and_spaces_the_rest() -> None:
    clock = FakeClock()
    limiter = RateLimiter(1.0, clock=clock.monotonic, sleep=clock.sleep)
    assert limiter.wait() == 0.0
    assert limiter.wait() == 1.0
    assert limiter.wait() == 1.0
    assert clock.slept == [1.0, 1.0]


def test_backoff_doubles_to_a_ceiling_and_resets() -> None:
    backoff = Backoff(base=1.0, factor=2.0, max_delay=8.0)
    assert [backoff.next() for _ in range(5)] == [1.0, 2.0, 4.0, 8.0, 8.0]
    backoff.reset()
    assert backoff.next() == 1.0


def test_a_missing_cursor_file_reads_as_empty(tmp_path: Path) -> None:
    store = CursorStore(tmp_path / "cursor.json")
    assert store.read().values == {}


def test_the_cursor_round_trips_through_disk(tmp_path: Path) -> None:
    path = tmp_path / "cursor.json"
    store = CursorStore(path)
    cursor = TimepointCursor()
    cursor.advance(1001, 1790994632)
    cursor.advance(38813297, 1790994999)
    store.write(cursor)
    assert store.read().values == {1001: 1790994632, 38813297: 1790994999}
    assert json.loads(path.read_text(encoding="utf-8"))["timepoints"] == {
        "1001": 1790994632,
        "38813297": 1790994999,
    }


def test_advance_never_moves_a_cursor_backwards() -> None:
    cursor = TimepointCursor()
    cursor.advance(1001, 200)
    cursor.advance(1001, 100)
    assert cursor.get(1001) == 200


def test_a_write_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    path = tmp_path / "cursor.json"
    store = CursorStore(path)
    store.write(TimepointCursor())
    store.write(TimepointCursor())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cursor.json"]


def test_resume_start_uses_the_cursor_when_present_and_a_window_when_not() -> None:
    cursor = TimepointCursor()
    assert cursor.resume_start(1001, now=1000, window=900) == 100
    cursor.advance(1001, 500)
    assert cursor.resume_start(1001, now=1000, window=900) == 500


def test_resume_start_clamps_a_cursor_ahead_of_the_server_clock() -> None:
    cursor = TimepointCursor()
    cursor.advance(1001, 1500)
    assert cursor.resume_start(1001, now=1000, window=900) == 1000
