"""The one place YAML is read.

PyYAML's own `safe_load` keeps the last of a repeated mapping key, so a document
with a duplicated field is silently judged as the document the author did not
write. Every reader in this repository therefore goes through `load_mapping`,
which raises instead, and `deployment/scripts/check-yaml-loading.sh` fails on any
`safe_load` left in the source tree, so a reader that bypasses this module is
caught rather than reviewed for.

A duplicate key is not hypothetical here. The register, the budget file and the
compose files all carry ceilings, limits and thresholds that a check exists to
enforce, and a duplicated key would let a check approve a value that is not the
one on disk.
"""

from __future__ import annotations

import yaml


class _UniqueKeyLoader(yaml.SafeLoader):
    """A SafeLoader that rejects a duplicate mapping key instead of shadowing it."""


def _construct_unique_mapping(loader, node, deep=False):
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found a duplicate key " + repr(key),
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def load_mapping(stream):
    """Parse YAML, rejecting a duplicate mapping key.

    SafeLoader keeps the last of a repeated key, so a duplicated field would
    silently shadow the one the author wrote and the caller would judge a
    document other than the one on disk.
    """
    return yaml.load(stream, Loader=_UniqueKeyLoader)
