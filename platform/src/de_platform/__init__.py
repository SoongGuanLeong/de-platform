"""The shared Python core of de-platform.

The distribution is named `platform` and the import package is
`platform_core`, because a top-level package named `platform` would shadow the
standard library module of the same name.

Every path may import this one. It imports no path: it is the leaf of the
packaging graph (ADR-0026, and `.importlinter` rule 3).
"""
