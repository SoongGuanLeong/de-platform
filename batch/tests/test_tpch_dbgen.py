"""Building dbgen from source, and the provenance of that source.

dbgen is not committed: it is built from a pinned source at a pinned revision,
and the revision, the source URL and the checksum of the downloaded archive are
recorded so a run can declare which generator produced the data. The build
carries the two flags a modern compiler needs: the C dialect where an empty
parameter list means "unspecified", and the fortify check disabled, because
dbgen's open() call predates the check glibc now enforces.
"""

from __future__ import annotations

from de_batch.commerce.tpch import dbgen


def test_the_source_is_pinned_to_a_commit() -> None:
    provenance = dbgen.provenance()
    assert provenance.commit in provenance.url
    assert len(provenance.sha256) == 64


def test_the_provenance_names_the_generator_version() -> None:
    assert dbgen.provenance().version == "2.14.0"


def test_the_build_command_carries_the_two_modern_compiler_flags() -> None:
    argv = dbgen.build_argv("make")
    joined = " ".join(argv)
    assert "-std=gnu89" in joined
    assert "FORTIFY_SOURCE=0" in joined
    assert "-DLINUX" in joined
    assert "-DTPCH" in joined


def test_the_generate_command_forces_overwrite_at_the_scale_factor() -> None:
    assert dbgen.generate_argv("/opt/dbgen/dbgen", 10) == [
        "/opt/dbgen/dbgen",
        "-s",
        "10",
        "-f",
    ]


def test_generate_runs_in_the_output_directory_with_the_distribution_file(tmp_path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "dists.dss").write_text("distribution", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()

    calls = []

    def runner(argv, cwd):
        calls.append((argv, cwd))
        return 0

    dbgen.generate(
        dbgen_path=str(source / "dbgen"),
        source_dir=str(source),
        out_dir=str(out),
        scale_factor=10,
        runner=runner,
    )

    assert (out / "dists.dss").read_text(encoding="utf-8") == "distribution"
    assert calls == [([str(source / "dbgen"), "-s", "10", "-f"], str(out))]


def test_a_nonzero_dbgen_exit_is_raised(tmp_path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "dists.dss").write_text("x", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()

    def runner(argv, cwd):
        return 3

    try:
        dbgen.generate(str(source / "dbgen"), str(source), str(out), 1, runner)
    except RuntimeError as error:
        assert "dbgen" in str(error)
        return
    raise AssertionError("a nonzero dbgen exit must be raised")
