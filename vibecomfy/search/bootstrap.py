from __future__ import annotations

from pathlib import Path

from vibecomfy.ingest.sources import sync_sources

REQUIRED_INDEXES = (
    "node_index.json",
    "template_index.json",
    "external_workflow_index.json",
)


class SearchBootstrapError(RuntimeError):
    pass


def _missing_indexes() -> list[str]:
    return [name for name in REQUIRED_INDEXES if not Path(name).exists()]


def ensure_indexes(*, auto_sync: bool = False) -> None:
    missing = _missing_indexes()
    if not missing:
        return
    if not auto_sync:
        raise SearchBootstrapError("indexes missing; run 'vibecomfy sources sync' first")

    sync_sources()
    missing_after_sync = _missing_indexes()
    if missing_after_sync:
        missing_text = ", ".join(missing_after_sync)
        raise SearchBootstrapError(
            f"indexes missing after auto-sync ({missing_text}); run 'vibecomfy sources sync' first"
        )
