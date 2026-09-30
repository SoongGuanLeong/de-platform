"""The shared Python core of de-platform.

The distribution is named `platform` and the import package is `de_platform`,
so the package name cannot collide with the repository's own `platform/`
directory on `sys.path` or with the standard library.

Every path may import this one. It imports no path: it is the leaf of the
packaging graph (ADR-0026, and `.importlinter` rule 3).
"""
