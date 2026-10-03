"""The TPC-C driver command line.

    python -m de_ingestion.commerce.tpcc --warehouses 1 --transactions 1000

The default warehouse count is the declared volume (W=100). A smaller count is a
declared reduction and must be labelled as one wherever its output is cited
(docs/testing-strategy.md section 4.1).
"""

from __future__ import annotations

import argparse
import sys

from de_ingestion.commerce.tpcc import counts, driver, scripted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drive the TPC-C source database.")
    parser.add_argument("--dsn", default=None, help="a PostgreSQL DSN; TPCC_DSN is the fallback")
    parser.add_argument("--warehouses", type=int, default=counts.DECLARED_WAREHOUSES)
    parser.add_argument("--seed", type=int, default=counts.DECLARED_SEED)
    parser.add_argument("--transactions", type=int, default=1_000)
    parser.add_argument("--mode", choices=("mix", "scripted", "load"), default="mix")
    parser.add_argument(
        "--case", choices=[case.value for case in scripted.Case], default=scripted.Case.ALL.value
    )
    parser.add_argument(
        "--reset", action="store_true", help="drop the source schema before loading"
    )
    parser.add_argument("--report", default=None, help="write the sequence log to this path")
    args = parser.parse_args(argv)

    with driver.connect(args.dsn) as connection:
        if args.mode == "load":
            loaded = driver.load(connection, args.warehouses, args.seed, reset=args.reset)
            result = None
        else:
            result = driver.run(
                connection,
                args.warehouses,
                args.seed,
                count=args.transactions,
                mode=args.mode,
                case=scripted.Case(args.case),
                reset=args.reset,
            )
            loaded = result.loaded

    print("warehouses=" + str(args.warehouses) + " seed=" + str(args.seed) + " mode=" + args.mode)
    for table in sorted(loaded):
        print("  " + table + "=" + str(loaded[table]))
    if result is not None:
        print("transactions=" + str(result.transactions))
        if args.report:
            with open(args.report, "w", encoding="utf-8") as handle:
                handle.write(result.sequence_log)
            print("sequence log written to " + args.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
