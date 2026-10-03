"""The declared volume, the reduction label and the throughput label.

Phase 1 permits a reduced volume (docs/implementation-roadmap.md section 3), and
the testing strategy fixes the correctness slice at SF1 and the declared volume
at SF100 (docs/testing-strategy.md section 4.1). A run therefore states both
factors, and a reduction is visible rather than implied.

The TPC-H tools are used under the TPC permission notice. That notice does not
license calling a figure a TPC Benchmark Result, so every throughput figure this
package produces is labelled TPC-derived and the forbidden label is refused.
"""

from __future__ import annotations

from dataclasses import dataclass

DECLARED_SCALE_FACTOR = 100

# The label every throughput figure carries, and the label none may carry.
TPC_DERIVED = "TPC-derived"
FORBIDDEN_LABEL = "TPC Benchmark Result"


@dataclass(frozen=True)
class Volume:
    """The declared scale factor and the one a run actually used."""

    declared: int
    used: int

    def is_reduced(self) -> bool:
        return self.used < self.declared

    def label(self) -> str:
        if self.is_reduced():
            return "SF" + str(self.used) + " (reduced; declared SF" + str(self.declared) + ")"
        return "SF" + str(self.used)


def assert_tpc_derived(text: str) -> None:
    """Refuse a throughput label that is not a TPC-derived result."""
    if FORBIDDEN_LABEL in text:
        raise ValueError(
            "a throughput figure must not be labelled "
            + repr(FORBIDDEN_LABEL)
            + "; the TPC permission notice permits a TPC-derived result only"
        )
    if TPC_DERIVED not in text:
        raise ValueError("a throughput figure must carry the " + repr(TPC_DERIVED) + " label")


def throughput(rows: int, seconds: float) -> str:
    """A throughput figure, always labelled TPC-derived."""
    rate = rows / seconds if seconds > 0 else 0.0
    figure = (
        str(rows)
        + " rows in "
        + format(seconds, "g")
        + " s = "
        + format(rate, ",.0f")
        + " rows/s ("
        + TPC_DERIVED
        + ")"
    )
    assert_tpc_derived(figure)
    return figure
