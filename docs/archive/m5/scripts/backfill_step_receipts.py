#!/usr/bin/env python3
"""Backfill missing tokens and cost on historical megaplan step_receipt_*.json files.

Three sources of historical gaps this addresses:

1. **Claude tokens** — Receipts where ``agent == "claude"`` and ``cost_usd > 0``
   but ``prompt_tokens == 0 / completion_tokens == 0``. The original CLI envelope
   carried the ``usage`` dict; we never read it. Cannot be recovered after the
   fact unless the raw envelope was stored — we flag these but do not invent
   numbers.

2. **Fireworks-hosted hermes cost** — Receipts where ``agent == "hermes"``,
   ``prompt_tokens + completion_tokens > 0``, ``cost_usd == 0``, and
   ``model_actual`` (or ``model_configured``) is a known Fireworks model.
   ``fireworks_pricing.cost_from_usage`` is authoritative here; we compute and
   write back additively.

3. **Execute multi-batch token aggregation** — Receipts for ``phase == "execute"``
   where ``prompt_tokens == 0`` but sibling ``execution_batch_*.json`` files in
   the same plan dir carry per-batch usage. We sum them into the parent receipt.

## Output

By default the script is **dry-run** — it prints what it would change. Pass
``--apply`` to actually write. Enriched values are added as new fields
``cost_usd_backfilled``, ``prompt_tokens_backfilled``, ``completion_tokens_backfilled``
plus ``backfilled_at`` and ``backfill_source``. The original ``cost_usd`` and
``*_tokens`` fields are NEVER overwritten — readers that prefer the corrected
values should check ``*_backfilled`` first and fall back to the original.

## Usage

```
# Dry-run (default) — survey the whole machine, summarize what would change
./scripts/backfill_step_receipts.py

# Restrict to a specific root
./scripts/backfill_step_receipts.py --root ~/Documents/megaplan

# Apply the changes
./scripts/backfill_step_receipts.py --apply

# Verbose — print every receipt that would change
./scripts/backfill_step_receipts.py --verbose
```

## Safety

- Never overwrites existing non-zero values.
- Adds additive fields only.
- Each write records ``backfilled_at`` (UTC ISO timestamp) and
  ``backfill_source`` so the provenance is traceable.
- Idempotent — re-running over already-backfilled receipts is a no-op.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add repo root to sys.path so we can import the pricing module without installing.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from arnold.pipelines.megaplan.pricing.fireworks import FIREWORKS_PRICING, cost_from_usage  # noqa: E402
from arnold.pipelines.megaplan.pricing.claude import (  # noqa: E402
    DEFAULT_PROMPT_COMPLETION_RATIO,
    estimate_tokens_from_cost,
)


DEFAULT_SCAN_ROOTS = [
    Path.home() / "Documents",
    Path.home() / "code",
    Path.home() / "projects",
    Path.home() / ".megaplan",  # global plans
]


@dataclass
class Summary:
    receipts_scanned: int = 0
    plans_seen: set[str] = field(default_factory=set)
    hermes_cost_filled: int = 0
    hermes_cost_total_usd: float = 0.0
    execute_tokens_filled: int = 0
    execute_tokens_total: int = 0
    claude_tokens_estimated: int = 0
    claude_tokens_estimated_total: int = 0
    claude_tokens_estimated_total_cost_usd: float = 0.0
    claude_tokens_unrecoverable: int = 0
    already_backfilled: int = 0
    skipped_unknown_model: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors: list[tuple[Path, str]] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _model_for_receipt(r: dict[str, Any]) -> str | None:
    return r.get("model_actual") or r.get("model_configured")


def _short_model(model: str | None) -> str | None:
    if not model:
        return None
    return model.rsplit("/", 1)[-1]


def _try_aggregate_batches(plan_dir: Path) -> tuple[int, int] | None:
    """Sum prompt/completion tokens across execution_batch_*.json siblings.

    Returns (prompt, completion) or None if no batch files exist or summed to 0.
    """
    total_prompt = 0
    total_completion = 0
    found_any = False
    for batch_path in sorted(plan_dir.glob("execution_batch_*.json")):
        try:
            data = json.loads(batch_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        # Batch artifacts vary in shape — try a few likely keys.
        for key_set in (
            ("prompt_tokens", "completion_tokens"),
            ("input_tokens", "output_tokens"),
        ):
            p_key, c_key = key_set
            if p_key in data and c_key in data:
                total_prompt += int(data.get(p_key) or 0)
                total_completion += int(data.get(c_key) or 0)
                found_any = True
                break
        # Some batches nest under "worker" or "usage".
        for nest_key in ("worker", "usage"):
            nested = data.get(nest_key)
            if isinstance(nested, dict):
                total_prompt += int(nested.get("prompt_tokens", 0) or 0)
                total_completion += int(nested.get("completion_tokens", 0) or 0)
                if nested.get("prompt_tokens") or nested.get("completion_tokens"):
                    found_any = True
    if not found_any or (total_prompt == 0 and total_completion == 0):
        return None
    return total_prompt, total_completion


def _enrich_receipt(
    receipt_path: Path,
    dry_run: bool,
    summary: Summary,
    verbose: bool,
    *,
    estimate_claude_tokens: bool = False,
    claude_ratio: float = DEFAULT_PROMPT_COMPLETION_RATIO,
    assume_claude_model: str = "claude-opus-4",
) -> bool:
    """Returns True if a change was made (or would be in dry-run)."""
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        summary.errors.append((receipt_path, str(exc)))
        return False

    summary.receipts_scanned += 1
    plan_id = receipt.get("plan_id") or receipt_path.parent.name
    summary.plans_seen.add(plan_id)
    plan_dir = receipt_path.parent

    # Skip if already backfilled by a previous run.
    if "backfilled_at" in receipt:
        summary.already_backfilled += 1
        return False

    agent = (receipt.get("agent") or "").lower()
    phase = receipt.get("phase") or ""
    cost = float(receipt.get("cost_usd") or 0.0)
    p_tok = int(receipt.get("prompt_tokens") or 0)
    c_tok = int(receipt.get("completion_tokens") or 0)
    model = _model_for_receipt(receipt)

    updates: dict[str, Any] = {}
    sources: list[str] = []

    # --- 1. Hermes/Fireworks cost backfill ---
    if agent == "hermes" and cost == 0.0 and (p_tok > 0 or c_tok > 0):
        short = _short_model(model)
        if short and short in FIREWORKS_PRICING:
            computed = cost_from_usage(p_tok, c_tok, model)
            if computed > 0:
                updates["cost_usd_backfilled"] = round(computed, 6)
                sources.append(f"fireworks_pricing:{short}")
                summary.hermes_cost_filled += 1
                summary.hermes_cost_total_usd += computed
        else:
            summary.skipped_unknown_model[short or "<no-model>"] += 1

    # --- 2. Execute multi-batch token aggregation ---
    if phase == "execute" and p_tok == 0 and c_tok == 0:
        aggregated = _try_aggregate_batches(plan_dir)
        if aggregated is not None:
            agg_p, agg_c = aggregated
            updates["prompt_tokens_backfilled"] = agg_p
            updates["completion_tokens_backfilled"] = agg_c
            updates["total_tokens_backfilled"] = agg_p + agg_c
            sources.append("execution_batches")
            summary.execute_tokens_filled += 1
            summary.execute_tokens_total += agg_p + agg_c
            # If we now have hermes tokens for an execute receipt, also try cost.
            if agent == "hermes" and "cost_usd_backfilled" not in updates:
                short = _short_model(model)
                if short and short in FIREWORKS_PRICING:
                    computed = cost_from_usage(agg_p, agg_c, model)
                    if computed > 0:
                        updates["cost_usd_backfilled"] = round(computed, 6)
                        if "fireworks_pricing" not in ",".join(sources):
                            sources.append(f"fireworks_pricing:{short}")
                        summary.hermes_cost_filled += 1
                        summary.hermes_cost_total_usd += computed

    # --- 3. Claude tokens — estimate from cost (lossy) ---
    if agent == "claude" and cost > 0.0 and p_tok == 0 and c_tok == 0:
        if estimate_claude_tokens:
            # Use model_actual if it's a real model id; otherwise assume default family.
            # Strings like "claude", "claude:low", "claude:high" are profile slots,
            # not model ids — fall back to the assumed family for those.
            model_for_estimate = model if (model and "-" in (model.rsplit("/", 1)[-1])) else assume_claude_model
            estimate = estimate_tokens_from_cost(cost, model_for_estimate, ratio=claude_ratio)
            if estimate is not None:
                est_p, est_c = estimate
                updates["prompt_tokens_backfilled"] = est_p
                updates["completion_tokens_backfilled"] = est_c
                updates["total_tokens_backfilled"] = est_p + est_c
                updates["claude_estimate_ratio"] = claude_ratio
                updates["claude_estimate_model"] = model_for_estimate
                sources.append(
                    f"claude_pricing_estimate(ratio={claude_ratio:g}:1,model={model_for_estimate})"
                )
                summary.claude_tokens_estimated += 1
                summary.claude_tokens_estimated_total += est_p + est_c
                summary.claude_tokens_estimated_total_cost_usd += cost
            else:
                summary.claude_tokens_unrecoverable += 1
        else:
            summary.claude_tokens_unrecoverable += 1

    if not updates:
        return False

    updates["backfilled_at"] = _now_iso()
    updates["backfill_source"] = ",".join(sources)

    if verbose:
        print(f"  {receipt_path.relative_to(REPO_ROOT.parent) if REPO_ROOT.parent in receipt_path.parents else receipt_path}")
        for k, v in updates.items():
            print(f"    {k}: {v}")

    if not dry_run:
        receipt.update(updates)
        tmp = receipt_path.with_suffix(receipt_path.suffix + ".tmp")
        tmp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, receipt_path)

    return True


def _find_receipts(roots: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    receipts: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("step_receipt_*.json"):
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            receipts.append(path)
    return receipts


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes. Default is dry-run.",
    )
    parser.add_argument(
        "--root",
        action="append",
        default=None,
        type=Path,
        help=f"Scan root. Repeatable. Defaults: {[str(r) for r in DEFAULT_SCAN_ROOTS]}",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print every receipt that gets a change.",
    )
    parser.add_argument(
        "--estimate-claude-tokens",
        action="store_true",
        help=(
            "Reverse-estimate prompt/completion tokens for Claude receipts that "
            "captured cost_usd but no tokens. Lossy — assumes a fixed "
            "prompt:completion ratio. Off by default."
        ),
    )
    parser.add_argument(
        "--claude-ratio",
        type=float,
        default=DEFAULT_PROMPT_COMPLETION_RATIO,
        help=(
            "Prompt:completion token ratio assumed when estimating Claude "
            f"tokens from cost. Default {DEFAULT_PROMPT_COMPLETION_RATIO:g}:1."
        ),
    )
    parser.add_argument(
        "--assume-claude-model",
        default="claude-opus-4",
        help=(
            "Claude model family to assume when model_actual is missing or "
            "generic (e.g. 'claude:low'). Default 'claude-opus-4' (megaplan's "
            "default premium slot)."
        ),
    )
    args = parser.parse_args()

    roots = args.root or DEFAULT_SCAN_ROOTS
    print(f"Scanning roots: {[str(r) for r in roots]}")
    receipts = _find_receipts(roots)
    print(f"Found {len(receipts)} step_receipt_*.json files\n")

    summary = Summary()
    changed = 0
    for receipt_path in receipts:
        if _enrich_receipt(
            receipt_path,
            dry_run=not args.apply,
            summary=summary,
            verbose=args.verbose,
            estimate_claude_tokens=args.estimate_claude_tokens,
            claude_ratio=args.claude_ratio,
            assume_claude_model=args.assume_claude_model,
        ):
            changed += 1

    print()
    print("=" * 60)
    print(f"{'DRY RUN — no files written' if not args.apply else 'APPLIED — files updated'}")
    print("=" * 60)
    print(f"Receipts scanned:               {summary.receipts_scanned}")
    print(f"Unique plans seen:              {len(summary.plans_seen)}")
    print(f"Receipts {'changed' if args.apply else 'that would change'}: {changed}")
    print(f"Receipts already backfilled:    {summary.already_backfilled}")
    print()
    print("Hermes/Fireworks cost backfill:")
    print(f"  receipts:                     {summary.hermes_cost_filled}")
    print(f"  total cost recovered:         ${summary.hermes_cost_total_usd:,.2f}")
    print()
    print("Execute multi-batch tokens:")
    print(f"  receipts:                     {summary.execute_tokens_filled}")
    print(f"  total tokens recovered:       {summary.execute_tokens_total:,}")
    print()
    if summary.claude_tokens_estimated > 0:
        print("Claude tokens estimated (lossy — ratio-based reverse):")
        print(f"  receipts:                     {summary.claude_tokens_estimated}")
        print(f"  total tokens estimated:       {summary.claude_tokens_estimated_total:,}")
        print(f"  total cost covered:           ${summary.claude_tokens_estimated_total_cost_usd:,.2f}")
    print(f"Claude receipts missing tokens (unrecoverable): {summary.claude_tokens_unrecoverable}")
    if summary.skipped_unknown_model:
        print()
        print("Hermes receipts skipped — model not in FIREWORKS_PRICING:")
        for short, count in sorted(summary.skipped_unknown_model.items(), key=lambda kv: -kv[1]):
            print(f"  {short!r}: {count}")
    if summary.errors:
        print()
        print(f"Errors reading {len(summary.errors)} receipts:")
        for path, err in summary.errors[:10]:
            print(f"  {path}: {err}")
        if len(summary.errors) > 10:
            print(f"  ... and {len(summary.errors) - 10} more")

    if not args.apply and changed > 0:
        print()
        print(f"Re-run with --apply to write {changed} change(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
