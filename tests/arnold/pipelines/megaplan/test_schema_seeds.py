from __future__ import annotations

from copy import deepcopy

from arnold.pipelines.megaplan.schema_seeds import (
    canonical_v1_step_schemas,
    legacy_v0_step_schemas,
)
from arnold.pipelines.megaplan.schemas import SCHEMAS
from arnold.pipelines.megaplan.workers import STEP_SCHEMA_FILENAMES


def test_legacy_v0_step_schemas_are_top_level_lenient_and_preserve_sources() -> None:
    original = deepcopy(SCHEMAS)

    seeded = legacy_v0_step_schemas()

    assert set(seeded) == set(STEP_SCHEMA_FILENAMES)
    assert seeded["plan"]["additionalProperties"] is True
    assert seeded["prep"]["required"] == SCHEMAS["prep.json"]["required"]
    assert SCHEMAS == original


def test_canonical_v1_step_schemas_close_objects_without_promoting_optionals() -> None:
    seeded = canonical_v1_step_schemas()
    prep = seeded["prep"]

    assert prep["additionalProperties"] is False
    assert prep["required"] == SCHEMAS["prep.json"]["required"]

    key_evidence_item = prep["properties"]["key_evidence"]["items"]
    assert key_evidence_item["additionalProperties"] is False
    assert key_evidence_item["required"] == ["point", "source", "relevance"]
    assert "primary_criterion" not in prep["required"]
