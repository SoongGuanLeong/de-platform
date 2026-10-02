"""The gold-contract loader.

A contract is one machine-readable YAML file per gold table at
`contracts/<spine>/<table>.yml` (docs/data-contracts.md section 2), and it is
the single source of truth for that table's schema: the DQ `schema` check is
generated from it, so the column list is written once. This module is the one
place that turns the file into a schema the rest of the platform reads.

It parses no YAML itself. `platform/` is the leaf of the packaging graph
(.importlinter rule 3) and cannot import `de_governance.yaml_loader`, the
single YAML entry point (#85), so the parse is injected: `load_contract` takes
the callable that reads the file, and a call site passes
`de_governance.yaml_loader.load_mapping`, which rejects a duplicate key.

This loader validates only the fields it consumes. The full contract validator,
the breaking-change check and the coexistence rule are the `governance/`
framework's (ADR-0019), and they land with the contract set.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import IO, Any

from de_platform import naming

# The fields the platform core consumes. A contract carries more than this; the
# validator that reads the rest is the governance framework's.
REQUIRED_FIELDS = ("table", "spine", "layer", "grain", "contract_version", "columns")


class ContractError(ValueError):
    """A contract file that does not carry the fields the core needs."""


@dataclass(frozen=True)
class Column:
    """One column of a gold contract's schema."""

    name: str
    type: str
    nullable: bool
    pii_class: str


@dataclass(frozen=True)
class Contract:
    """A gold contract, as the platform core reads it.

    `schema` is the column list in declaration order. The contract file names
    the field `columns`; the loader is what maps the file's field to the schema
    the rest of the platform reads.
    """

    table: str
    spine: str
    layer: str
    grain: str
    contract_version: str
    schema: tuple[Column, ...]
    business_keys: tuple[str, ...]


def _require_string(mapping: Mapping[str, Any], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractError("contract field " + repr(field) + " is missing or not a string")
    return value


def _column(entry: Any, index: int) -> Column:
    if not isinstance(entry, Mapping):
        raise ContractError("contract column " + str(index) + " is not a mapping")
    name = entry.get("name")
    type_ = entry.get("type")
    nullable = entry.get("nullable")
    # ADR-0017: a column without a pii_class fails CI, so the loader refuses it
    # here rather than passing a schema with an unclassified column downstream.
    pii_class = entry.get("pii_class")
    if not isinstance(name, str) or not name.strip():
        raise ContractError("contract column " + str(index) + " has no name")
    if not isinstance(type_, str) or not type_.strip():
        raise ContractError("contract column " + repr(name) + " has no type")
    if not isinstance(nullable, bool):
        raise ContractError("contract column " + repr(name) + " nullable is not a boolean")
    if not isinstance(pii_class, str) or not pii_class.strip():
        raise ContractError("contract column " + repr(name) + " has no pii_class (ADR-0017)")
    return Column(name=name, type=type_, nullable=nullable, pii_class=pii_class)


def contract_from_mapping(mapping: Mapping[str, Any]) -> Contract:
    """Build a Contract from a parsed contract document."""
    if not isinstance(mapping, Mapping):
        raise ContractError("a contract is a mapping")
    for field in REQUIRED_FIELDS:
        if field not in mapping:
            raise ContractError("contract is missing the required field " + repr(field))

    table = _require_string(mapping, "table")
    spine = _require_string(mapping, "spine")
    layer = _require_string(mapping, "layer")
    grain = _require_string(mapping, "grain")
    contract_version = _require_string(mapping, "contract_version")

    # The table name is the authority for the spine and layer (naming), so a
    # contract whose spine or layer disagrees with its own table is refused
    # rather than silently trusted.
    expected_spine, expected_layer, _ = naming.parse_table(table)
    if (spine, layer) != (expected_spine, expected_layer):
        raise ContractError(
            "contract table " + repr(table) + " disagrees with spine/layer " + repr((spine, layer))
        )

    raw_columns = mapping.get("columns")
    if not isinstance(raw_columns, list) or not raw_columns:
        raise ContractError("contract " + repr(table) + " has no columns")
    columns = tuple(_column(entry, index) for index, entry in enumerate(raw_columns))

    raw_keys = mapping.get("business_keys")
    if not isinstance(raw_keys, list) or not raw_keys:
        raise ContractError("contract " + repr(table) + " has no business_keys")
    if not all(isinstance(key, str) and key for key in raw_keys):
        raise ContractError("contract " + repr(table) + " has a business key that is not a string")

    return Contract(
        table=table,
        spine=spine,
        layer=layer,
        grain=grain,
        contract_version=contract_version,
        schema=columns,
        business_keys=tuple(raw_keys),
    )


def load_contract(path: str, loader: Callable[[IO[str]], Mapping[str, Any]]) -> Contract:
    """Read a contract file through `loader` and return the parsed contract.

    `loader` is injected so this module parses no YAML and imports no path: the
    call site passes `de_governance.yaml_loader.load_mapping`, the repository's
    single YAML entry point. The file is opened here and the open handle is
    handed to `loader`, because `load_mapping` parses a stream rather than a
    path.
    """
    with open(path, encoding="utf-8") as handle:
        return contract_from_mapping(loader(handle))
