from __future__ import annotations

from arnold_pipelines.megaplan.prompts._shared import (
    TEST_BLAST_RADIUS_OUTPUT_CONTRACT,
)
from arnold_pipelines.megaplan.prompts.critique import _revise_prompt
from arnold_pipelines.megaplan.prompts.planning import _plan_prompt
from arnold_pipelines.megaplan.schemas.runtime import TEST_BLAST_RADIUS_SCHEMA


def test_plan_and_revise_share_schema_complete_blast_radius_instruction() -> None:
    assert "TEST_BLAST_RADIUS_OUTPUT_CONTRACT" in _plan_prompt.__code__.co_names
    assert "TEST_BLAST_RADIUS_OUTPUT_CONTRACT" in _revise_prompt.__code__.co_names

    for field in TEST_BLAST_RADIUS_SCHEMA["required"]:
        assert f'"{field}"' in TEST_BLAST_RADIUS_OUTPUT_CONTRACT

    import_graph = TEST_BLAST_RADIUS_SCHEMA["properties"]["import_graph"]
    for field in import_graph["required"]:
        assert f'"{field}"' in TEST_BLAST_RADIUS_OUTPUT_CONTRACT
