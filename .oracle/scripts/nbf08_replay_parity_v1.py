#!/usr/bin/env python3
"""Strict physical/semantic/parity verifier for an IncidentLedger root."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from arnold_pipelines.megaplan.incident.chain_control import ChainControlJournal, projection_rebuild
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--projection", required=False)
    parser.add_argument("--authority", default="file")
    parser.add_argument("--check-physical", action="store_true")
    parser.add_argument("--check-semantic", action="store_true")
    parser.add_argument("--check-parity", action="store_true")
    args = parser.parse_args(argv)
    journal = ChainControlJournal(IncidentLedger(Path(args.ledger)))
    replay = journal.replay_strict()
    projection = projection_rebuild(journal)
    if args.check_physical and replay["physical_sequence"] < -1:
        print("physical replay failed", file=sys.stderr)
        return 1
    if args.check_semantic and "semantic_by_chain" not in replay:
        print("semantic replay failed", file=sys.stderr)
        return 1
    if args.check_parity:
        if projection["physical_tip_digest"] != replay["physical_tip_digest"]:
            print("projection parity mismatch", file=sys.stderr)
            return 1
        if args.projection:
            recorded = json.loads(Path(args.projection).read_text(encoding="utf-8"))
            if recorded.get("physical_tip_digest") not in {None, replay["physical_tip_digest"]}:
                print("external projection digest mismatch", file=sys.stderr)
                return 1
    print(json.dumps({"ok": True, "physical_sequence": replay["physical_sequence"], "authority": args.authority}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
