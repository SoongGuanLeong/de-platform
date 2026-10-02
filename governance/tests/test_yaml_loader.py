"""The strict YAML loader: the one reader every other reader goes through."""

from __future__ import annotations

import io

import pytest
import yaml
from de_governance.yaml_loader import load_mapping


def test_a_clean_mapping_parses() -> None:
    assert load_mapping("a: 1\nb: 2\n") == {"a": 1, "b": 2}


def test_a_stream_and_a_string_are_both_accepted() -> None:
    assert load_mapping(io.StringIO("a: 1\n")) == {"a": 1}


def test_a_duplicate_top_level_key_is_rejected() -> None:
    # SafeLoader would keep the second value and drop the first without a word.
    with pytest.raises(yaml.constructor.ConstructorError):
        load_mapping("a: 1\na: 2\n")


def test_a_duplicate_nested_key_is_rejected() -> None:
    with pytest.raises(yaml.constructor.ConstructorError):
        load_mapping("services:\n  db:\n    image: one\n    image: two\n")


def test_the_error_names_the_duplicated_key() -> None:
    with pytest.raises(yaml.constructor.ConstructorError) as caught:
        load_mapping("threshold: 1\nthreshold: 2\n")
    assert "threshold" in str(caught.value)


def test_a_sequence_is_not_a_mapping_and_still_parses() -> None:
    assert load_mapping("- one\n- two\n") == ["one", "two"]
