# Engine pins follow Iceberg's supported connector matrix

**Status:** accepted

The pinned engines are **Apache Iceberg 1.11.0, Apache Flink 2.1.3 and Apache Spark 4.1.3**. Iceberg 1.11.0 is the current GA release and it ships connector modules for Flink up to 2.1 and Spark up to 4.1 only (at tag `apache-iceberg-1.11.0`, `flink/` holds v1.20, v2.0 and v2.1; `spark/` holds v3.4, v3.5, v4.0 and v4.1), and the matching runtime artifacts resolve on Maven Central at 1.11.0 only. Flink 2.2/2.3 and Spark 4.2 support landed after that release, under Iceberg 1.12.0, which is RC2 and not GA. The engines therefore move to the newest patch of the newest minor Iceberg supports, and each pin is the latest patch of its line.

## Considered options

- **Keep Flink 2.3.0 and Spark 4.2.0, and move Iceberg to 1.12.0 at GA.** Rejected for now: it is not takeable today, and it would gate a locked proposal on an external release date. Revisit under the re-review condition below.
- **Adopt Iceberg 1.12.0-RC2 now, to keep the newer engines.** Rejected: an RC in a locked proposal is a claim that cannot be checked, and it may still change.
- **Run the Flink 2.1 module on Flink 2.3.0.** Rejected: unsupported. Flink 2.2 moved the variant API, so the 2.1 module needed new `org.apache.flink.types.variant` code (PR #17849, merged 2026-08-28).
- **Pin Flink 2.1.0 and Spark 4.1.0 exactly.** Rejected: the Iceberg connector targets the minor (`flink/v2.1`, `spark/v4.1`), not a patch, and patches within a minor are bugfix-only, so a `.0` pin ships already-fixed bugs for no compatibility gain.

## Consequences

Spark 4.2's headline addition is Java 25 support, and every JVM image pins **JDK 17**, so the newer engine bought nothing here; the Java caution on the Spark row is withdrawn. The version column in `docs/research/14-licence-and-cost-audit.md` moves with the pins, because it is a live claim about what ships. The dated research snapshots (`03-longevity-audit.md`, `06`, `10`) keep their version figures as historical records.

**Re-review condition.** Re-run this reconciliation when **Apache Iceberg 1.12.0 is GA** and both `org.apache.iceberg:iceberg-flink-runtime-2.3` and `org.apache.iceberg:iceberg-spark-runtime-4.2_2.13` resolve on Maven Central. Check the Maven repository metadata or directory listing, not the search API, which served a stale index on 2026-09-28. Evidence: ticket [Reconcile the engine version pins with Iceberg's supported connector matrix](https://github.com/SoongGuanLeong/de-platform/issues/19); research 03, 06 and 10.
