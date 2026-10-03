"""The ONSPD loader against the real ONS release (issue #50).

This is the integration half of the loader's evidence. It reads the bounded
subset of the ONS Postcode Directory, May 2026, that the pinned generator
`ingestion/scripts/fetch_onspd_fixture.py` writes to `runtime/`, and asserts the
behaviours the ticket names against real publisher rows: the licence-restricted
Northern Ireland subset is excluded, the SCD2 interval comes from DOINTR and
DOTERM with null meaning live, and a boundary-straddling postcode resolves to
more than one geography.

It runs under the batch profile's command (`pytest tests/batch`) rather than in
CI: it reads a fetched dataset, and docs/testing-strategy.md section 6 keeps the
fetched fixtures and the profile suites out of CI. The subset is bounded, so the
full release volume is a registered limitation, not a silent reduction.
"""

from __future__ import annotations

import os

import pytest
from de_ingestion.network import onspd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE = os.path.join(ROOT, "runtime/fixtures/onspd_may2026_subset.csv")


@pytest.fixture(scope="module")
def rows():
    if not os.path.exists(FIXTURE):
        onspd.fetch_subset(FIXTURE)
    loaded = onspd.load_onspd(FIXTURE)
    assert loaded, "the ONSPD fixture is empty"
    return loaded


def test_the_northern_ireland_subset_is_present_and_excluded(rows):
    raw_bt = [row for row in rows if onspd.is_northern_ireland(onspd.postcode_of(row))]
    assert raw_bt, "the fixture carries no BT postcode to exercise the exclusion"
    kept = onspd.exclude_northern_ireland(rows)
    assert len(kept) == len(rows) - len(raw_bt)
    assert onspd.assert_no_northern_ireland(kept) == len(kept)
    with pytest.raises(onspd.OnspdError):
        onspd.assert_no_northern_ireland(rows)


def test_a_real_terminated_postcode_resolves_for_a_point_in_time(rows):
    kept = onspd.exclude_northern_ireland(rows)
    versions = onspd.dim_postcode_versions(kept)
    terminated = [version for version in versions if not version.is_live]
    assert terminated, "the fixture carries no terminated postcode"
    sample = terminated[0]
    assert onspd.dim_postcode_as_of(versions, sample.postcode, sample.valid_from) == sample
    assert onspd.dim_postcode_as_of(versions, sample.postcode, sample.valid_from - 1) is None
    assert onspd.dim_postcode_as_of(versions, sample.postcode, sample.valid_to) is None


def test_a_real_boundary_straddling_postcode_resolves_to_several_geographies(rows):
    kept = onspd.exclude_northern_ireland(rows)
    bridge = onspd.build_postcode_geography(kept)
    # B14 5TU is assigned to two Local Enterprise Partnerships in the release.
    resolved = onspd.resolve_geographies(bridge, "B14 5TU")
    assert resolved["local_enterprise_partnership"] == ("E37000012", "E37000038")
    assert len(resolved) > 1

    # And the straddling case is not a one-off: some postcode resolves to more
    # than one code of the same geography type.
    by_type: dict[tuple[str, str], list[str]] = {}
    for row in bridge:
        by_type.setdefault((row.postcode, row.geography_type), []).append(row.geography_code)
    straddling = [key for key, codes in by_type.items() if len(set(codes)) > 1]
    assert straddling, "no straddling postcode found in the fixture"


def test_every_kept_postcode_resolves_to_at_least_one_geography(rows):
    kept = onspd.exclude_northern_ireland(rows)
    bridge = onspd.build_postcode_geography(kept)
    resolved = {row.postcode for row in bridge}
    missing = [row["pcds"] for row in kept if onspd.postcode_of(row) not in resolved]
    assert missing == []
