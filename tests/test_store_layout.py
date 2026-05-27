from __future__ import annotations

import inspect
from importlib import import_module
from typing import get_args

from pydantic import BaseModel


def test_megaplan_schemas_keeps_legacy_exports() -> None:
    schemas = import_module("megaplan.schemas")

    assert "plan.json" in schemas.SCHEMAS
    assert callable(schemas.strict_schema)
    assert callable(schemas.get_execution_schema_key)
    assert issubclass(schemas.StorageModel, BaseModel)
    assert get_args(schemas.Backend) == ("file", "db")
    assert schemas.HomeBackend is schemas.Backend


def test_store_package_exports_sprint_1_seams() -> None:
    store = import_module("megaplan.store")
    schemas = import_module("megaplan.schemas")

    assert get_args(store.Backend) == ("file", "db")
    assert store.Backend is schemas.Backend
    assert store.Store.__module__ == "megaplan.store.base"
    assert store.BlobStore.__module__ == "megaplan.store.blob"
    assert store.FileStore.__module__ == "megaplan.store.file"
    assert store.DBStore.__module__ == "megaplan.store.db"
    assert store.PlanRepository.__module__ == "megaplan.store.plan_repository"
    assert store.MultiStore.__module__ == "megaplan.store.multi"
    assert store.ArnoldStoreAdapter.__module__ == "megaplan.store.compat"


def test_store_assembly_modules_preserve_source_inspection() -> None:
    """Source-inspection must survive mixin decomposition.

    When methods are extracted into ``_file/`` or ``_db/`` slice modules and
    re-assembled via mixin inheritance, ``inspect.getsource(Class.method)``
    must still return the method body (not a stub or ``pass``).
    """
    from megaplan.store import FileStore, DBStore

    # Methods that may move to _file/ or _db/ slices during decomposition.
    file_source = inspect.getsource(FileStore.create_epic)
    assert len(file_source) > 60, "FileStore.create_epic source is too short; source inspection may be broken"
    assert "def create_epic" in file_source
    assert "title" in file_source

    db_source = inspect.getsource(DBStore.create_epic)
    assert len(db_source) > 60, "DBStore.create_epic source is too short; source inspection may be broken"
    assert "def create_epic" in db_source
    assert "title" in db_source
