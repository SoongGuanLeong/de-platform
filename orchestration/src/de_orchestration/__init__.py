"""The Dagster code location, the composition root (ADR-0026).

The composition root is the only module permitted to import both spines. It
holds no business logic.
"""
