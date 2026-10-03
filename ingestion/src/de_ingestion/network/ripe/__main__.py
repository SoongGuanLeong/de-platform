"""The RIPE Atlas collector entrypoint.

Reads the declared configuration, opens one producer, backfills the gap from
the persisted cursor into the topic, then streams the declared subscription set
into the same topic. Both paths share the one producer (ADR-0014).
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_config
from .cursor import CursorStore
from .pipeline import RipePipeline
from .producer import KafkaProducer

DEFAULT_CURSOR_PATH = Path("/var/lib/de-platform/ripe-cursor.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="The RIPE Atlas collector (issue #48).")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--cursor", type=Path, default=DEFAULT_CURSOR_PATH)
    parser.add_argument(
        "--bootstrap-servers",
        default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="stop after this many results (a bounded run for a local check)",
    )
    parser.add_argument(
        "--no-backfill",
        action="store_true",
        help="skip the REST backfill and stream only",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    store = CursorStore(args.cursor)
    producer = KafkaProducer(args.bootstrap_servers)
    pipeline = RipePipeline(config, producer, store)
    try:
        produced = pipeline.run(
            now=int(time.time()), limit=args.limit, backfill=not args.no_backfill
        )
    finally:
        producer.close()
    print("produced " + str(produced) + " result(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
