from __future__ import annotations

import ast
from pathlib import Path

from arnold_pipelines.megaplan.editorial import EditorialError, EditorialOperation, EditorialResult


class RecordingStore:
    def __init__(self) -> None:
        self.transaction_epic_ids: list[str] = []

    def transaction(self, epic_id: str | None = None):
        self.transaction_epic_ids.append(str(epic_id))
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


def test_editorial_operation_uses_store_transaction_with_epic_id() -> None:
    store = RecordingStore()
    operation = EditorialOperation(store=store, epic_id="epic_1", actor_id="actor_1")

    with operation.transaction():
        pass

    assert store.transaction_epic_ids == ["epic_1"]


def test_editorial_result_and_error_payloads_are_structured() -> None:
    result = EditorialResult(epic_id="epic_1", actor_id="actor_1", changed=True, data={"ok": True})
    error = EditorialError("failed", details={"field": "state"})

    assert result.data == {"ok": True}
    assert error.to_dict() == {
        "error": "editorial_error",
        "message": "failed",
        "details": {"field": "state"},
    }


def test_editorial_foundation_imports_stay_store_only() -> None:
    package = Path(__file__).resolve().parents[1] / "arnold" / "pipelines" / "megaplan" / "editorial"
    forbidden_roots = {"supabase", "psycopg"}
    forbidden_modules = {
        "arnold_pipelines.megaplan.store.file",
        "arnold_pipelines.megaplan.store.db",
        "arnold_pipelines.megaplan.store.plan_repository",
    }

    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                assert module.split(".", 1)[0] not in forbidden_roots, (path.name, module)
                assert module not in forbidden_modules, (path.name, module)
