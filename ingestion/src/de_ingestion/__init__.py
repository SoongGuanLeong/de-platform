"""Ingestion for both spines (ADR-0026).

`commerce` and `network` are independent: neither may import the other, in
either direction (`.importlinter` rule 1).
"""
