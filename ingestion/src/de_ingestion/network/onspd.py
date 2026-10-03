"""The ONSPD loader: the postcode dimension and the geography bridge (issue #50).

The ONS Postcode Directory is one very wide row per postcode, with live and
terminated postcodes, and a published temporal pair: `DOINTR` (date of
introduction, `YYYYMM`) and `DOTERM` (date of termination, `YYYYMM`, **null
meaning live**). This module turns that row into the two network-spine tables
docs/data-architecture.md section 4 names:

- `dim_postcode`, a Type 2 dimension keyed on the postcode with `valid_from` and
  `valid_to` derived from `DOINTR` and `DOTERM`. The validity interval is
  half-open: a postcode introduced in `198001` and terminated in `199606` is in
  force from 198001 up to, but not including, 199606. That is the convention that
  makes reintroduction clean, because a reintroduced postcode starts a new
  version exactly where the terminated one stops being in force.
- `postcode_geography`, a bridge table, because one postcode maps to several
  geographies. In the straddling cases the publisher assigns one postcode to more
  than one geography of the same type (the hosted table carries `lep21cd1` and
  `lep21cd2` for exactly this reason), so the bridge holds several rows for that
  postcode and type rather than one.

The Northern Ireland `BT` subset is licence-restricted (internal business use
only, ADR-0009), so it is excluded before any published table is built, and the
exclusion is asserted rather than assumed.

The loader writes through the platform core's Iceberg REST client
(`de_platform.catalog`), never through a Polaris-proprietary API (ADR-0010).

Documented limitations, each with the test that would close it:

- The fixture is a bounded subset (920 rows), not the full release (235 MB,
  approximately 2.7 million postcodes). The reduction is declared in
  `tests/fixtures.yaml`, and no claim here is volume-dependent, so the reduction
  is legitimate under docs/testing-strategy.md section 4. The full release would
  be read by the same loader unchanged.
- The Iceberg write is gated on the catalog bootstrap that lands with the
  credential-vending work in Phase 7: Polaris writes a new table's metadata to
  the warehouse, which needs the catalog's region, the SeaweedFS STS role and the
  grants. The loader addresses both gold tables through the Iceberg REST
  specification and raises `CatalogWriteGated` rather than pretending to write.
  The test that closes it is a create-and-append of `network.gold.dim_postcode`
  and `network.gold.postcode_geography` against a bootstrapped catalog, under the
  `batch` profile.
"""

from __future__ import annotations

import csv
import json
import os
import re
import urllib.parse
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from de_platform import catalog as platform_catalog
from de_platform import naming

# The ONSPD geography columns the bridge carries, mapped to the geography type
# the bridge's `geography_type` column holds. The 2021 census geographies and
# the 2025/2026 statutory and health geographies are the current vintages. The
# two LEP columns are deliberately the same type: a postcode assigned to both is
# the boundary-straddling case the bridge exists to represent.
GEOGRAPHY_COLUMNS: dict[str, str] = {
    "ctry25cd": "country",
    "rgn25cd": "region",
    "lad25cd": "local_authority_district",
    "wd25cd": "ward",
    "lsoa21cd": "lsoa",
    "msoa21cd": "msoa",
    "oa21cd": "output_area",
    "icb26cd": "integrated_care_board",
    "pcon24cd": "parliamentary_constituency",
    "lep21cd1": "local_enterprise_partnership",
    "lep21cd2": "local_enterprise_partnership",
}

NORTHERN_IRELAND_PREFIX = "BT"

# The ONSPD's pseudo-code for "no such geography": a leading letter and eight
# nines, e.g. S99999999 for a Scottish postcode with no region. It is not a
# geography and does not belong in the bridge.
_PSEUDO_CODE = re.compile(r"^[A-Za-z]9{8}$")


class OnspdError(ValueError):
    """An ONSPD row or set that violates the loader's contract."""


@dataclass(frozen=True)
class PostcodeVersion:
    """One version of a postcode in the Type 2 dimension.

    `valid_to` is `None` for a live postcode, which is the source's own
    null-means-live semantic.
    """

    postcode: str
    valid_from: int
    valid_to: int | None

    @property
    def is_live(self) -> bool:
        return self.valid_to is None


@dataclass(frozen=True)
class GeographyRow:
    """One row of the postcode-to-geography bridge."""

    postcode: str
    geography_type: str
    geography_code: str


def normalise_postcode(value: str) -> str:
    """The canonical postcode key, from any of ONSPD's three representations.

    `PCD7` and `PCD8` pad the outward and inward codes with blanks; `PCDS` is the
    canonical spacing. All three collapse to upper case with a single space
    before the three-character inward code.
    """
    if not isinstance(value, str):
        raise OnspdError("a postcode is a string; got " + repr(value))
    compact = re.sub(r"\s+", "", value).upper()
    if len(compact) < 4:
        raise OnspdError("not a postcode: " + repr(value))
    return compact[:-3] + " " + compact[-3:]


def postcode_of(row: Mapping[str, Any]) -> str:
    """The postcode key of an ONSPD row, from PCDS or PCD7."""
    for key in ("pcds", "pcd7"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return normalise_postcode(value)
    raise OnspdError("an ONSPD row carries no postcode in pcds or pcd7")


def is_northern_ireland(postcode: str) -> bool:
    """Whether a postcode is in the licence-restricted Northern Ireland subset."""
    return normalise_postcode(postcode).startswith(NORTHERN_IRELAND_PREFIX)


def parse_yyyymm(value: Any) -> int | None:
    """Parse an ONSPD `YYYYMM` month, or `None` for a null/blank value."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    if not re.fullmatch(r"\d{6}", text):
        raise OnspdError("not a YYYYMM month: " + repr(value))
    return int(text)


def parse_version(row: Mapping[str, Any]) -> PostcodeVersion:
    """Derive one postcode version's validity interval from DOINTR and DOTERM."""
    valid_from = parse_yyyymm(row.get("dointr"))
    if valid_from is None:
        raise OnspdError("an ONSPD row carries no DOINTR: " + repr(postcode_of(row)))
    return PostcodeVersion(
        postcode=postcode_of(row),
        valid_from=valid_from,
        valid_to=parse_yyyymm(row.get("doterm")),
    )


def dim_postcode_versions(rows: Iterable[Mapping[str, Any]]) -> list[PostcodeVersion]:
    """The Type 2 versions over a set of ONSPD rows, ordered by key and time.

    A postcode may appear once per release. Two rows for the same key with
    different intervals are two versions; a version whose interval reaches into a
    later one is closed where the later one begins, so the versions never
    overlap and a point in time selects at most one.
    """
    by_postcode: dict[str, dict[tuple[int, int | None], PostcodeVersion]] = defaultdict(dict)
    for row in rows:
        version = parse_version(row)
        by_postcode[version.postcode][(version.valid_from, version.valid_to)] = version

    versions: list[PostcodeVersion] = []
    for postcode in sorted(by_postcode):
        ordered = sorted(by_postcode[postcode].values(), key=lambda item: item.valid_from)
        for index, version in enumerate(ordered):
            following = ordered[index + 1] if index + 1 < len(ordered) else None
            if following is not None and (
                version.valid_to is None or version.valid_to > following.valid_from
            ):
                version = PostcodeVersion(
                    version.postcode, version.valid_from, following.valid_from
                )
            versions.append(version)
    return versions


def dim_postcode_as_of(
    versions: Iterable[PostcodeVersion], postcode: str, point: int
) -> PostcodeVersion | None:
    """The version of a postcode in force at a `YYYYMM` point in time.

    The interval is half-open: `valid_from <= point < valid_to`, and a live
    version has no upper bound.
    """
    key = normalise_postcode(postcode)
    for version in versions:
        if version.postcode != key:
            continue
        if version.valid_from <= point and (version.valid_to is None or point < version.valid_to):
            return version
    return None


def build_postcode_geography(rows: Iterable[Mapping[str, Any]]) -> list[GeographyRow]:
    """The postcode-to-geography bridge, one row per assignment.

    A postcode assigned to several geographies of one type (the straddling case)
    contributes several rows of that type.
    """
    bridge: list[GeographyRow] = []
    for row in rows:
        postcode = postcode_of(row)
        for column, geography_type in GEOGRAPHY_COLUMNS.items():
            code = row.get(column)
            if not isinstance(code, str):
                continue
            code = code.strip().upper()
            if not code or _PSEUDO_CODE.match(code):
                continue
            bridge.append(GeographyRow(postcode, geography_type, code))
    return bridge


def resolve_geographies(
    bridge: Iterable[GeographyRow], postcode: str
) -> dict[str, tuple[str, ...]]:
    """Resolve a postcode through the bridge to every geography it belongs to.

    The result is keyed by geography type; a straddling postcode has more than
    one code under one type, and the codes are ordered so the result is stable.
    """
    key = normalise_postcode(postcode)
    resolved: dict[str, list[str]] = defaultdict(list)
    for row in bridge:
        if row.postcode == key:
            resolved[row.geography_type].append(row.geography_code)
    return {geography_type: tuple(sorted(codes)) for geography_type, codes in resolved.items()}


def exclude_northern_ireland(
    rows: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Drop the licence-restricted `BT` subset before a published table is built."""
    return [row for row in rows if not is_northern_ireland(postcode_of(row))]


def assert_no_northern_ireland(rows: Iterable[Mapping[str, Any]]) -> int:
    """Assert the loaded set carries no Northern Ireland postcode.

    Returns the number of rows checked, so a caller can record that the
    exclusion was asserted over a non-empty set rather than over nothing.
    """
    checked = 0
    for row in rows:
        checked += 1
        postcode = postcode_of(row)
        if is_northern_ireland(postcode):
            raise OnspdError(
                "Northern Ireland postcode "
                + postcode
                + " is licence-restricted (ADR-0009) and must be excluded "
                "before a published table is built"
            )
    return checked


# The pinned ONS release and the hosted-table query endpoint the loader reads.
# The hosted table is the ONS Postcode Directory's own record shape; the full
# multi-CSV zip is 235 MB, so a bounded subset is fetched instead and the volume
# limitation is registered (docs/testing-strategy.md section 4).
ONSPD_RELEASE = "May 2026"
ONSPD_QUERY_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "ONS_Postcode_Directory_(May_2026)_for_the_United_Kingdom_(Hosted_Table)/"
    "FeatureServer/0/query"
)
ONSPD_FIELDS = ["pcd7", "pcd8", "pcds", "dointr", "doterm", *GEOGRAPHY_COLUMNS]
FEATURE_SERVER_PAGE = 500  # the endpoint's maxRecordCount is 1000; 500 keeps each page quick


def subset_queries() -> list[tuple[str, int]]:
    """The bounded queries the fixture generator runs, and their row caps.

    Each query selects one of the behaviours the ticket names, so the bounded
    subset carries the BT subset (to be excluded), terminated postcodes (the SCD2
    interval),     straddling postcodes (the bridge's many-to-many) and plain live
    postcodes. The service's default ObjectId order is stable for a fixed
    release, so the subset is reproducible without a sort.
    """
    return [
        ("pcd7 LIKE 'BT%'", 20),
        ("doterm IS NOT NULL AND pcd7 NOT LIKE 'BT%'", 200),
        ("lep21cd1 IS NOT NULL AND lep21cd2 IS NOT NULL", 200),
        ("doterm IS NULL AND lep21cd2 IS NULL AND pcd7 NOT LIKE 'BT%'", 500),
    ]


def records_from_response(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The attribute mappings an ArcGIS FeatureServer query response carries."""
    features = payload.get("features") if isinstance(payload, Mapping) else None
    if not isinstance(features, list):
        raise OnspdError("an ArcGIS response carries no features list")
    records = []
    for feature in features:
        attributes = feature.get("attributes") if isinstance(feature, Mapping) else None
        if not isinstance(attributes, Mapping):
            raise OnspdError("an ArcGIS feature carries no attributes mapping")
        records.append({key: attributes.get(key) for key in ONSPD_FIELDS})
    return records


def _query(where: str, limit: int, transport: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    while len(records) < limit:
        count = min(FEATURE_SERVER_PAGE, limit - len(records))
        # No orderByFields: ordering by postcode forces a full sort of the
        # filtered set and the endpoint times out. The service returns in
        # ObjectId order by default, which is stable for a fixed release, so
        # paging with resultOffset is deterministic without the sort.
        query = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": ",".join(ONSPD_FIELDS),
                "resultOffset": offset,
                "resultRecordCount": count,
                "f": "json",
            }
        )
        status, _headers, text = transport("GET", ONSPD_QUERY_URL + "?" + query, {}, None)
        if status >= 400:
            raise OnspdError("the ONSPD query failed with HTTP " + str(status))
        page = records_from_response(json.loads(text))
        if not page:
            break
        records.extend(page)
        offset += len(page)
        if len(page) < count:
            break
    return records[:limit]


def fetch_subset(destination: str, transport: Any | None = None) -> int:
    """Fetch the bounded ONSPD subset and write it as CSV; return the row count.

    The transport defaults to the platform core's urllib transport, so the
    loader's network call goes through one place. The subset is bounded, so the
    full-release volume is a registered limitation rather than a silent
    reduction.
    """
    if transport is None:
        from de_platform._http import urllib_transport

        transport = urllib_transport

    rows: list[dict[str, Any]] = []
    for where, limit in subset_queries():
        rows.extend(_query(where, limit, transport))

    directory = os.path.dirname(os.path.abspath(destination))
    os.makedirs(directory, exist_ok=True)
    with open(destination, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ONSPD_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row[key] for key in ONSPD_FIELDS})
    return len(rows)


def load_onspd(path: str) -> list[dict[str, Any]]:
    """Read the fetched ONSPD subset back as rows, blanks as `None`."""
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append({key: (value if value != "" else None) for key, value in row.items()})
    return rows


# The gold tables the loader fills, in the platform's naming convention.
DIM_POSTCODE = naming.iceberg_table("network", "gold", "dim_postcode")
POSTCODE_GEOGRAPHY = naming.iceberg_table("network", "gold", "postcode_geography")


def _parse_table(identifier: str) -> tuple[str, str, str]:
    return naming.parse_table(identifier)


def ensure_namespaces(client: Any) -> list[tuple[str, ...]]:
    """Create the network-spine namespaces through the Iceberg REST client.

    Idempotent: a namespace the catalog already has is left alone. The parent
    namespace is created before the child, because the REST specification
    addresses `network.gold` as a two-level namespace under `network`.
    """
    created = []
    for namespace in (("network",), ("network", "gold")):
        try:
            client.create_namespace(namespace)
        except platform_catalog.CatalogError as error:
            if "already exists" not in str(error).lower() and "409" not in str(error):
                raise
        created.append(namespace)
    return created


def address_tables(client: Any) -> dict[str, Any]:
    """Resolve both gold tables through the Iceberg REST specification.

    Creating and appending to a table needs the catalog bootstrap that lands with
    the credential-vending work (Phase 7): Polaris writes a new table's metadata
    to the warehouse, which needs the catalog's region, the SeaweedFS STS role
    and the grants. This function therefore addresses the tables and surfaces the
    specification's own `NoSuchTableException` as a `CatalogWriteGated` naming
    that gate, rather than pretending to write.
    """
    resolved: dict[str, Any] = {}
    gated: list[tuple[str, Exception]] = []
    for identifier in (DIM_POSTCODE, POSTCODE_GEOGRAPHY):
        spine, layer, table = _parse_table(identifier)
        try:
            resolved[identifier] = client.load_table((spine, layer), table)
        except platform_catalog.NoSuchTableError as error:
            gated.append((identifier, error))
    if gated:
        # Every target is addressed before the gate is reported, so a run names
        # all the tables the write path would fill rather than stopping at the
        # first. The first gated table is the one the error identifies.
        identifier, error = gated[0]
        raise CatalogWriteGated(identifier, error) from error
    return resolved


class CatalogWriteGated(RuntimeError):
    """The table is addressable through REST, but create-and-append is gated.

    The gate is the catalog bootstrap the credential-vending work sets up in
    Phase 7 (docs/implementation-roadmap.md section 3); until then the loader can
    address a table through the specification but cannot create one. Recorded as
    a limitation rather than hidden.
    """

    def __init__(self, identifier: str, cause: Exception) -> None:
        super().__init__(
            "cannot write " + identifier + ": the table is addressable through the Iceberg REST "
            "specification but create-and-append needs the catalog bootstrap "
            "that lands with Phase 7's credential-vending work (ADR-0010, "
            "docs/implementation-roadmap.md section 3). The addressing half is "
            "verified; the write half is gated."
        )
        self.identifier = identifier
        self.cause = cause
