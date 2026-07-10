from __future__ import annotations

from typing import TypeAlias, TypedDict


class WorkflowIndexRow(TypedDict, total=False):
    id: str
    path: str
    source: str
    media_type: str
    package_id: str
    manifest_path: str


class CustomNodeExampleRow(TypedDict, total=False):
    id: str
    path: str
    source: str
    pack: str


class RuntimeNodeRow(TypedDict, total=False):
    id: str
    class_type: str
    name: str
    display_name: str
    pack: str
    package: str
    source: str


IndexRow: TypeAlias = WorkflowIndexRow | CustomNodeExampleRow | RuntimeNodeRow
