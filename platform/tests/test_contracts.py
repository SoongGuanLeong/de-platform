"""The contract loader returns a gold contract's schema (issue #33).

The loader parses no YAML itself. `platform/` is the leaf of the packaging
graph (.importlinter rule 3) and cannot import `de_governance.yaml_loader`, the
single YAML entry point (#85), so the parse is injected: `load_contract` takes
the callable that reads the file, and the call site passes
`de_governance.yaml_loader.load_mapping`. The unit tests here pass a stub, so
they need no YAML and no distribution.

The expected schema is the worked example docs/data-contracts.md section 2
gives, and the field rules (the `pii_class` requirement is ADR-0017) are
asserted against it.
"""

from __future__ import annotations

import pytest
from de_platform import contracts

CONTRACT = {
    "table": "commerce.gold.fact_order_line",
    "spine": "commerce",
    "layer": "gold",
    "grain": "one row per order line",
    "contract_version": "1.0",
    "columns": [
        {"name": "w_id", "type": "int", "nullable": False, "pii_class": "none"},
        {"name": "ol_quantity", "type": "int", "nullable": False, "pii_class": "none"},
        {"name": "ol_amount", "type": "decimal(12,2)", "nullable": False, "pii_class": "none"},
    ],
    "business_keys": ["w_id", "d_id", "o_id", "ol_number"],
}


def test_schema_is_the_contract_columns_in_order():
    contract = contracts.contract_from_mapping(CONTRACT)
    assert [column.name for column in contract.schema] == ["w_id", "ol_quantity", "ol_amount"]
    assert contract.schema[2].type == "decimal(12,2)"
    assert contract.grain == "one row per order line"


def test_the_table_must_agree_with_its_spine_and_layer():
    with pytest.raises(contracts.ContractError):
        contracts.contract_from_mapping({**CONTRACT, "layer": "silver"})


def test_a_non_gold_contract_is_refused_even_when_it_agrees_with_its_table():
    # Bronze is governed by the Avro subject and silver by the schema check;
    # neither carries a contract file (docs/data-contracts.md section 4).
    silver = {**CONTRACT, "table": "commerce.silver.fact_order_line", "layer": "silver"}
    with pytest.raises(contracts.ContractError):
        contracts.contract_from_mapping(silver)


def test_every_column_carries_a_pii_class():
    bad = {
        **CONTRACT,
        "columns": [{"name": "w_id", "type": "int", "nullable": False}],
    }
    with pytest.raises(contracts.ContractError):
        contracts.contract_from_mapping(bad)


def test_a_missing_required_field_is_refused():
    without_grain = {key: value for key, value in CONTRACT.items() if key != "grain"}
    with pytest.raises(contracts.ContractError):
        contracts.contract_from_mapping(without_grain)


def test_load_contract_opens_the_file_and_parses_through_the_injected_loader(tmp_path):
    path = tmp_path / "fact_order_line.yml"
    path.write_text("placeholder: true\n", encoding="utf-8")
    seen = []

    def loader(handle):
        seen.append(handle.name)
        assert handle.read() == "placeholder: true\n"
        return CONTRACT

    contract = contracts.load_contract(str(path), loader)
    assert seen == [str(path)]
    assert contract.table == "commerce.gold.fact_order_line"
