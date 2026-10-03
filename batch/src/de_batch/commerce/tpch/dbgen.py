"""Building dbgen from source, and the provenance of that source.

dbgen is not committed: it is built from a pinned source at a pinned revision,
and the revision, the source URL and the checksum of the downloaded archive are
recorded so a run can declare which generator produced the data (the TPC-H
licence position, docs/dataset-selection.md section 10).

The source is the TPC-H dbgen 2.14.0 C source. It is fetched from a pinned
public mirror of that source rather than the TPC tools zip, because the tools zip
is gated behind a EULA form that cannot be accepted unattended. The generator is
still dbgen, built from source; the provenance records the mirror and the exact
revision, and the gap to the official tools zip is recorded as a limitation.

The build carries the two flags a modern compiler needs: the C dialect in which
an empty parameter list means unspecified (-std=gnu89), and the fortify check
disabled, because dbgen's open() call predates the check glibc now enforces.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

# The pinned source. The commit is the whole pin: the archive is content-addressed
# by the commit and the checksum below is of the archive this revision produced.
DBGEN_COMMIT = "32f1c1b92d1664dba542e927d23d86ffa57aa253"
DBGEN_URL = "https://codeload.github.com/electrum/tpch-dbgen/tar.gz/" + DBGEN_COMMIT
DBGEN_SHA256 = "01d8a4fa0fff4be83a9f43dbdc5a69f560d34f5ff0b4dbff1fc3a5320baf6318"
DBGEN_VERSION = "2.14.0"

# The compiler flags, in one place so the build and the provenance agree.
BUILD_CFLAGS = (
    "-O2",
    "-std=gnu89",
    "-w",
    "-U_FORTIFY_SOURCE",
    "-D_FORTIFY_SOURCE=0",
    "-DDBNAME=dss",
    "-DLINUX",
    "-DORACLE",
    "-DTPCH",
    "-D_FILE_OFFSET_BITS=64",
)


@dataclass(frozen=True)
class Provenance:
    """Where the generator came from, so a run can declare it."""

    url: str
    commit: str
    sha256: str
    version: str


def provenance() -> Provenance:
    return Provenance(
        url=DBGEN_URL, commit=DBGEN_COMMIT, sha256=DBGEN_SHA256, version=DBGEN_VERSION
    )


def build_argv(make: str = "make") -> list[str]:
    """The command that compiles dbgen in its source directory."""
    return [
        make,
        "CC=gcc",
        "MACHINE=LINUX",
        "DATABASE=ORACLE",
        "WORKLOAD=TPCH",
        "CFLAGS=" + " ".join(BUILD_CFLAGS),
    ]


def generate_argv(dbgen_path: str, scale_factor: int) -> list[str]:
    """The command that generates every table at a scale factor.

    dbgen writes all eight tables and overwrites existing files with -f, so the
    command is deterministic and re-runnable.
    """
    return [dbgen_path, "-s", str(scale_factor), "-f"]


def generate(
    dbgen_path: str,
    source_dir: str,
    out_dir: str,
    scale_factor: int,
    runner: Callable[..., int] | None = None,
) -> list[str]:
    """Run dbgen into out_dir, returning the command that ran.

    dbgen reads its distribution file from the working directory, so the file is
    copied beside the output and dbgen runs with the output directory as its
    working directory.
    """
    run = runner or _run
    os.makedirs(out_dir, exist_ok=True)
    shutil.copyfile(os.path.join(source_dir, "dists.dss"), os.path.join(out_dir, "dists.dss"))
    argv = generate_argv(dbgen_path, scale_factor)
    code = run(argv, out_dir)
    if code != 0:
        raise RuntimeError("dbgen exited " + str(code) + " generating " + out_dir)
    # dbgen writes part.tbl with a mode that denies other-read, which a loader
    # running as a different user cannot read. Normalise every generated file so
    # the output is readable by whoever loads it.
    for name in sorted(os.listdir(out_dir)):
        if name.endswith(".tbl"):
            os.chmod(os.path.join(out_dir, name), 0o644)
    return argv


def _run(argv: list[str], cwd: str) -> int:
    return subprocess.run(argv, cwd=cwd, check=False).returncode
