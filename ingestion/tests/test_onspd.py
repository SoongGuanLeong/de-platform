"""The ONSPD loader and the SCD2 postcode dimension (issue #50).

The loader reads the ONSPD's own record shape: one very wide row per postcode,
with `DOINTR` and `DOTERM` as `YYYYMM` and a null `DOTERM` meaning a live
postcode. These tests pin the behaviours the acceptance criteria name, against
real rows fetched from the ONS May 2026 release (the hosted table the loader
reads). The rows are literals rather than a committed fixture: the dataset
fixture itself is fetched by a pinned script and declared in `tests/fixtures.yaml`
(docs/testing-strategy.md section 4), and a handful of worked rows is a test
input, not a fixture.

The module is `de_ingestion.network.onspd` because
docs/testing-strategy.md section 4 places the ONSPD loader in
`ingestion/network/`. The catalog-facing functions go through the platform core's
Iceberg REST client and never through a Polaris-proprietary API (ADR-0010).
"""

from __future__ import annotations

import pytest
from de_ingestion.network import onspd
from de_platform import catalog as platform_catalog

# Real rows from the ONS Postcode Directory, May 2026 (hosted table), fetched
# 2026-10-03. A live English postcode.
LIVE = {
    "pcd7": "E1  0AA",
    "pcds": "E1 0AA",
    "dointr": "198001",
    "doterm": None,
    "ctry25cd": "E92000001",
    "rgn25cd": "E12000007",
    "lad25cd": "E09000030",
    "wd25cd": "E05009332",
    "lsoa21cd": "E01004298",
    "msoa21cd": "E02000885",
    "oa21cd": "E00021641",
    "icb26cd": "E54000029",
    "pcon24cd": "E14001086",
    "lep21cd1": "E37000051",
    "lep21cd2": None,
}

# A terminated Scottish postcode: dointr 198001, doterm 199606.
TERMINATED = {
    "pcd7": "AB1  0AA",
    "pcds": "AB1 0AA",
    "dointr": "198001",
    "doterm": "199606",
    "ctry25cd": "S92000003",
    "rgn25cd": "S99999999",
    "lad25cd": "S12000033",
    "wd25cd": "S13002843",
    "lsoa21cd": "S01013490",
    "msoa21cd": "S02002516",
    "oa21cd": "S00137176",
    "icb26cd": "S99999999",
    "pcon24cd": "S14000061",
    "lep21cd1": "S99999999",
    "lep21cd2": None,
}

# A postcode that genuinely straddles two Local Enterprise Partnerships: the
# hosted table carries both lep21cd1 and lep21cd2 (real boundary-straddling).
STRADDLING = {
    "pcd7": "B14  5TU",
    "pcds": "B14 5TU",
    "dointr": "198001",
    "doterm": None,
    "ctry25cd": "E92000001",
    "rgn25cd": "E12000005",
    "lad25cd": "E07000234",
    "wd25cd": "E05009857",
    "lsoa21cd": "E01033641",
    "msoa21cd": "E02001901",
    "oa21cd": "E00186300",
    "icb26cd": "E54000061",
    "pcon24cd": "E14001092",
    "lep21cd1": "E37000012",
    "lep21cd2": "E37000038",
}

# A Northern Ireland postcode: the licence permits internal business use only,
# so it is excluded from the published tables (ADR-0009).
NORTHERN_IRELAND = {
    "pcd7": "BT1  1AA",
    "pcds": "BT1 1AA",
    "dointr": "199002",
    "doterm": None,
    "ctry25cd": "N92000002",
    "rgn25cd": "N99999999",
    "lad25cd": "N09000003",
    "wd25cd": "N08000322",
    "lsoa21cd": "N21000192",
    "msoa21cd": "N99999999",
    "oa21cd": "N20000855",
    "icb26cd": "N99999999",
    "pcon24cd": "N05000002",
    "lep21cd1": "N99999999",
    "lep21cd2": None,
}


def test_valid_from_and_valid_to_are_derived_from_dointr_and_doterm():
    version = onspd.parse_version(TERMINATED)
    assert version.postcode == "AB1 0AA"
    assert version.valid_from == 198001
    assert version.valid_to == 199606


def test_a_null_doterm_means_a_live_postcode():
    version = onspd.parse_version(LIVE)
    assert version.valid_from == 198001
    assert version.valid_to is None
    assert version.is_live is True


def test_the_postcode_key_is_normalised_from_the_onspd_representations():
    # PCD7 and PCD8 carry padding blanks; PCDS is the canonical spacing.
    assert onspd.normalise_postcode("B14  5TU") == "B14 5TU"
    assert onspd.normalise_postcode("E1   0AA") == "E1 0AA"


def test_a_terminated_postcode_resolves_for_a_point_in_time():
    versions = [onspd.parse_version(TERMINATED)]
    assert onspd.dim_postcode_as_of(versions, "AB1 0AA", 199001).valid_to == 199606
    assert onspd.dim_postcode_as_of(versions, "AB1 0AA", 200001) is None
    assert onspd.dim_postcode_as_of(versions, "AB1 0AA", 197912) is None


def test_a_reintroduced_postcode_resolves_to_the_version_in_force():
    # A postcode terminated in 199606 and reintroduced in 200501 has two
    # versions; a point in time selects the one in force, and the gap between
    # them selects neither.
    versions = onspd.dim_postcode_versions(
        [
            {"pcd7": "AB1  0AA", "pcds": "AB1 0AA", "dointr": "198001", "doterm": "199606"},
            {"pcd7": "AB1  0AA", "pcds": "AB1 0AA", "dointr": "200501", "doterm": None},
        ]
    )
    assert [(v.valid_from, v.valid_to) for v in versions] == [
        (198001, 199606),
        (200501, None),
    ]
    assert onspd.dim_postcode_as_of(versions, "AB1 0AA", 199001).valid_from == 198001
    assert onspd.dim_postcode_as_of(versions, "AB1 0AA", 200601).valid_from == 200501
    assert onspd.dim_postcode_as_of(versions, "AB1 0AA", 199801) is None


def test_a_boundary_straddling_postcode_resolves_to_several_geographies():
    bridge = onspd.build_postcode_geography([STRADDLING])
    resolved = onspd.resolve_geographies(bridge, "B14 5TU")
    # The postcode sits in two Local Enterprise Partnerships, not one.
    assert resolved["local_enterprise_partnership"] == ("E37000012", "E37000038")
    # And it resolves to several geographies of different types as well.
    assert resolved["country"] == ("E92000001",)
    assert len(resolved) > 1


def test_a_plain_postcode_resolves_to_one_geography_per_type():
    bridge = onspd.build_postcode_geography([LIVE])
    resolved = onspd.resolve_geographies(bridge, "E1 0AA")
    assert resolved["local_enterprise_partnership"] == ("E37000051",)
    assert resolved["lsoa"] == ("E01004298",)


def test_northern_ireland_postcodes_are_excluded():
    rows = [LIVE, TERMINATED, STRADDLING, NORTHERN_IRELAND]
    assert onspd.is_northern_ireland("BT1 1AA") is True
    assert onspd.is_northern_ireland("E1 0AA") is False
    kept = onspd.exclude_northern_ireland(rows)
    assert [row["pcds"] for row in kept] == ["E1 0AA", "AB1 0AA", "B14 5TU"]
    assert all(not onspd.is_northern_ireland(row["pcds"]) for row in kept)


def test_the_northern_ireland_exclusion_is_asserted_over_the_loaded_set():
    rows = [LIVE, NORTHERN_IRELAND]
    kept = onspd.exclude_northern_ireland(rows)
    assert onspd.assert_no_northern_ireland(kept) == 1
    with pytest.raises(onspd.OnspdError):
        onspd.assert_no_northern_ireland(rows)


class FakeCatalog:
    """A catalog that records the REST calls the loader makes.

    The loader's job is to address the catalog through the Iceberg REST
    specification; whether the table exists is the catalog's answer, so the fake
    replays the specification's own NoSuchTableException.
    """

    def __init__(self) -> None:
        self.namespaces = []
        self.loaded = []

    def create_namespace(self, namespace):
        self.namespaces.append(tuple(namespace))
        return {"namespace": list(namespace)}

    def load_table(self, namespace, table):
        self.loaded.append((tuple(namespace), table))
        raise platform_catalog.NoSuchTableError(table)


def test_the_loader_creates_the_network_namespaces_through_rest():
    fake = FakeCatalog()
    onspd.ensure_namespaces(fake)
    assert fake.namespaces == [("network",), ("network", "gold")]


def test_the_loader_addresses_both_gold_tables_through_rest():
    fake = FakeCatalog()
    with pytest.raises(onspd.CatalogWriteGated):
        onspd.address_tables(fake)
    assert fake.loaded == [
        (("network", "gold"), "dim_postcode"),
        (("network", "gold"), "postcode_geography"),
    ]


def test_the_write_gate_names_the_table_and_the_phase_that_opens_it():
    fake = FakeCatalog()
    with pytest.raises(onspd.CatalogWriteGated) as raised:
        onspd.address_tables(fake)
    assert raised.value.identifier == "network.gold.dim_postcode"
    assert "Phase 7" in str(raised.value)


def test_an_arcgis_response_is_read_as_attribute_mappings():
    payload = {
        "features": [
            {"attributes": {"pcds": "E1 0AA", "dointr": "198001", "doterm": None}},
            {"attributes": {"pcds": "BT1 1AA", "dointr": "199002", "doterm": "200204"}},
        ]
    }
    records = onspd.records_from_response(payload)
    assert [record["pcds"] for record in records] == ["E1 0AA", "BT1 1AA"]
    assert set(records[0]) == set(onspd.ONSPD_FIELDS)


def test_a_response_without_features_is_refused():
    with pytest.raises(onspd.OnspdError):
        onspd.records_from_response({"error": "invalid where"})
