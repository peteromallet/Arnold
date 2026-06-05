from __future__ import annotations

from arnold.pipelines.megaplan.forms import get_form


def test_joke_and_poem_forms_are_registered() -> None:
    joke = get_form("joke")
    poem = get_form("poem")

    assert len(joke.provocations.cuts) >= 3
    assert len(joke.provocations.forces) >= 3
    assert len(joke.provocations.sparks) >= 3
    assert len(poem.provocations.cuts) >= 3
    assert len(poem.provocations.forces) >= 3
    assert len(poem.provocations.sparks) >= 3
    assert len(joke.beat_ids) == 5
    assert len(poem.beat_ids) == 3
    assert joke.execution_schema_key == "execution_doc.json"
    assert poem.execution_schema_key == "execution_doc.json"
