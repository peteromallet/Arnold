from __future__ import annotations

import argparse

from vibecomfy.ingest.sources import sync_sources


def _cmd_sources_sync(args: argparse.Namespace) -> int:
    result = sync_sources(
        official=args.official,
        external=args.external,
        custom_nodes=args.custom_nodes,
    )
    print(f"indexed official={result.official} external={result.external} nodes={result.nodes}")
    return 0


def register(subparsers) -> None:
    sources = subparsers.add_parser("sources")
    sources_sub = sources.add_subparsers(dest="subcmd", required=True)
    sync = sources_sub.add_parser("sync")
    sync.add_argument("--official", default="workflow_corpus/official")
    sync.add_argument("--external", default="workflow_corpus/custom_nodes")
    sync.add_argument("--custom-nodes", default="custom_nodes")
    sync.set_defaults(func=_cmd_sources_sync)
