from __future__ import annotations

from importlib import import_module
from typing import get_args

from pydantic import BaseModel


def test_megaplan_schemas_keeps_legacy_exports() -> None:
    schemas = import_module("megaplan.schemas")

    assert "plan.json" in schemas.SCHEMAS
    assert callable(schemas.strict_schema)
    assert callable(schemas.get_execution_schema_key)
    assert issubclass(schemas.StorageModel, BaseModel)


def test_store_package_exports_sprint_1_seams() -> None:
    store = import_module("megaplan.store")

    assert get_args(store.Backend) == ("file", "db")
    assert store.Store.__module__ == "megaplan.store.base"
    assert store.BlobStore.__module__ == "megaplan.store.blob"
    assert store.FileStore.__module__ == "megaplan.store.file"
    assert store.DBStore.__module__ == "megaplan.store.db"
    assert store.PlanRepository.__module__ == "megaplan.store.plan_repository"
