from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ACTIVE_TASK_NATIVE_SURFACES = [
    "megaplan/auto.py",
    "megaplan/chain.py",
    "megaplan/cli.py",
    "megaplan/workers/hermes.py",
    "megaplan/runtime/doc_assembly.py",
    "megaplan/prompts/feedback.py",
    "megaplan/prompts/execute.py",
    "megaplan/prompts/finalize.py",
    "docs/ops/blocked-recovery.md",
    "megaplan/data/instructions.md",
    "megaplan/data/claude_subagent_appendix.md",
    "megaplan/data/_codex_skills/megaplan/SKILL.md",
    "megaplan/data/_composed/claude_skill.md",
    "megaplan/data/_composed/codex_skill.md",
    "megaplan/data/_composed/cursor_rule.mdc",
]

STALE_BATCH_TERMS = [
    "execution_batch_",
    "list_batch_artifacts",
    "latest_execution_batch",
    "batch_to_tier",
    'receipt_metrics["batches"]',
    "Aggregated execute batches",
    "batch-level metadata",
    "per-batch execution",
    "batch by batch",
    "Batch numbering",
]


def test_active_surfaces_keep_legacy_batch_terms_migration_scoped() -> None:
    findings: list[str] = []
    for rel_path in ACTIVE_TASK_NATIVE_SURFACES:
        path = ROOT / rel_path
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not any(term in line for term in STALE_BATCH_TERMS):
                continue
            lower = line.lower()
            if "legacy" in lower and ("migration" in lower or "diagnostic" in lower):
                continue
            findings.append(f"{rel_path}:{line_number}: {line.strip()}")

    assert findings == []
