"""Operator-only SP-20 HNSW index builder and measured recall/latency CLI.

This is not a public API and never embeds text or changes document rows.
Only 'build --confirm-build' runs the potentially expensive concurrent DDL.
"""

import argparse
import asyncio
import json
import math
import sys
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from spurel.db import get_database_url
from spurel.retrieval.hnsw import (
    HnswBenchmarkError,
    HnswBenchmarkOptions,
    HnswConfigurationError,
    HnswIndexOptions,
    benchmark_index,
    build_index,
    index_state,
)


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise HnswConfigurationError(message)


def _build_parser() -> _SafeParser:
    parser = _SafeParser(prog="spurel-hnsw")
    parser.add_argument("--json", action="store_true", dest="json_output")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_SafeParser)

    for name in ("status", "build", "benchmark"):
        item = sub.add_parser(name)
        item.add_argument("--dimensions", type=int, required=True)
        if name == "build":
            item.add_argument("--confirm-build", action="store_true")
            item.add_argument("--m", type=int, default=16)
            item.add_argument("--ef-construction", type=int, default=64)
        if name == "benchmark":
            item.add_argument("--knowledge-base-id", type=UUID, required=True)
            item.add_argument("--provider", required=True)
            item.add_argument("--model", required=True)
            item.add_argument("--top-k", type=int, default=10)
            item.add_argument("--samples", type=int, default=20)
            item.add_argument("--ef-search", type=int, default=100)
            item.add_argument("--min-recall", type=float)
    return parser


async def _perform(args, database_url: str) -> dict:
    if args.command == "build":
        if not args.confirm_build:
            raise HnswConfigurationError(
                "build requires --confirm-build; index construction may take time and disk space"
            )
        return await build_index(
            database_url,
            HnswIndexOptions(
                dimensions=args.dimensions,
                m=args.m,
                ef_construction=args.ef_construction,
            ),
        )

    if args.command == "status":
        options = HnswIndexOptions(dimensions=args.dimensions)
        engine = create_async_engine(database_url)
        try:
            state = await index_state(engine, options)
        finally:
            await engine.dispose()
        return state or {
            "name": options.index_name,
            "dimensions": options.dimensions,
            "status": "not_built",
        }

    if args.command == "benchmark":
        if args.min_recall is not None and (
            not 0 <= args.min_recall <= 1 or not math.isfinite(args.min_recall)
        ):
            raise HnswConfigurationError("--min-recall must be a finite number from 0 to 1")
        return await benchmark_index(
            database_url,
            HnswBenchmarkOptions(
                knowledge_base_id=args.knowledge_base_id,
                provider=args.provider,
                model=args.model,
                dimensions=args.dimensions,
                top_k=args.top_k,
                samples=args.samples,
                ef_search=args.ef_search,
            ),
        )
    raise HnswConfigurationError("unsupported command")


def run_hnsw_cli(argv: Sequence[str] | None = None, *, stdout=None, stderr=None) -> int:
    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    try:
        args = _build_parser().parse_args(argv)
        # Validate the confirmation and all bounds before opening the database.
        if args.command == "build":
            HnswIndexOptions(args.dimensions, args.m, args.ef_construction)
            if not args.confirm_build:
                raise HnswConfigurationError("build requires --confirm-build")
        elif args.command == "status":
            HnswIndexOptions(args.dimensions)
        else:
            HnswBenchmarkOptions(
                knowledge_base_id=args.knowledge_base_id,
                provider=args.provider,
                model=args.model,
                dimensions=args.dimensions,
                top_k=args.top_k,
                samples=args.samples,
                ef_search=args.ef_search,
            )
        result = asyncio.run(_perform(args, get_database_url()))
        if args.json_output:
            print(json.dumps(result, sort_keys=True), file=output)
        else:
            for key, value in result.items():
                print(f"{key}: {value}", file=output)
        if (
            args.command == "benchmark"
            and args.min_recall is not None
            and result["mean_recall_at_k"] < args.min_recall
        ):
            print("HNSW recall is below the requested threshold", file=errors)
            return 2
        return 0
    except (HnswConfigurationError, HnswBenchmarkError) as exc:
        print(f"spurel-hnsw: {exc}", file=errors)
        return 3
    except (OSError, SQLAlchemyError, ValueError):
        # Avoid leaking DATABASE_URL or other driver internals.
        print("spurel-hnsw: PostgreSQL operation failed; inspect local server logs", file=errors)
        return 3


def main() -> None:
    raise SystemExit(run_hnsw_cli())


if __name__ == "__main__":
    main()
