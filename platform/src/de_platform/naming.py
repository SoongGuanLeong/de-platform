"""The platform's naming conventions, defined once.

The names below are the conventions docs/data-architecture.md section 3 and
docs/data-contracts.md section 4 fix, and every path imports them from here
rather than spelling them out again, so a convention change is one edit.

- An Iceberg table is `<spine>.<layer>.<table>`, in a spine-then-layer
  namespace: `commerce.bronze`, `commerce.silver`, `commerce.gold`,
  `network.bronze`, `network.silver`, `network.gold`, and the control-plane
  namespace `platform`.
- ClickHouse mirrors the serving domains in four databases: `commerce`,
  `network`, `governance` and `lakehouse`.
- A CDC topic is Debezium's default `<server>.<schema>.<table>`, and its Avro
  subject is `<topic>-value` (docs/data-contracts.md section 4).
- A consumer-facing serving view is `<name>_v<version>`, and a breaking change
  is a new version rather than an edit (ADR-0021).
"""

from __future__ import annotations

SPINES = ("commerce", "network")
LAYERS = ("bronze", "silver", "gold")

# The control-plane namespace is not a spine and not a layer
# (docs/data-architecture.md section 3).
CONTROL_NAMESPACE = "platform"

CLICKHOUSE_DATABASES = ("commerce", "network", "governance", "lakehouse")


class NamingError(ValueError):
    """A name that does not follow the platform's convention."""


def _check_spine(spine: str) -> None:
    if spine not in SPINES:
        raise NamingError("unknown spine " + repr(spine) + "; expected one of " + repr(SPINES))


def _check_layer(layer: str) -> None:
    if layer not in LAYERS:
        raise NamingError("unknown layer " + repr(layer) + "; expected one of " + repr(LAYERS))


def iceberg_namespace(spine: str, layer: str | None = None) -> str:
    """The Iceberg namespace for a spine and layer, or the control namespace.

    `iceberg_namespace("commerce", "gold")` is `commerce.gold`;
    `iceberg_namespace("platform")` is `platform`, which carries no layer.
    """
    if layer is None:
        if spine != CONTROL_NAMESPACE:
            raise NamingError(
                "a spine namespace needs a layer; only " + repr(CONTROL_NAMESPACE) + " has none"
            )
        return CONTROL_NAMESPACE
    _check_spine(spine)
    _check_layer(layer)
    return spine + "." + layer


def iceberg_table(spine: str, layer: str, table: str) -> str:
    """The fully-qualified Iceberg table name, `<spine>.<layer>.<table>`."""
    if not isinstance(table, str) or not table or "." in table:
        raise NamingError("a table name is one non-empty component with no dot; got " + repr(table))
    return iceberg_namespace(spine, layer) + "." + table


def parse_table(identifier: str) -> tuple[str, str, str]:
    """Split a fully-qualified Iceberg table name into (spine, layer, table)."""
    parts = identifier.split(".")
    if len(parts) != 3 or not all(parts):
        raise NamingError("an Iceberg table is <spine>.<layer>.<table>; got " + repr(identifier))
    spine, layer, table = parts
    _check_spine(spine)
    _check_layer(layer)
    return spine, layer, table


def clickhouse_database(spine: str) -> str:
    """The ClickHouse database that mirrors a spine's serving domain."""
    _check_spine(spine)
    return spine


def cdc_topic(server: str, schema: str, table: str) -> str:
    """The Debezium CDC topic name, `<server>.<schema>.<table>`."""
    return ".".join((server, schema, table))


def cdc_subject(topic: str) -> str:
    """The Confluent subject for a CDC topic's value schema."""
    return topic + "-value"
