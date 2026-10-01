"""The smoke profile's container checks.

The cases, the helpers and the assertions live in conftest.py, because the
workspace collects with --import-mode=importlib and a test module cannot import
its own conftest by name under it. One case per unit, one unit at a time.
"""

from __future__ import annotations


def test_smoke_unit(running):
    running.verify()
