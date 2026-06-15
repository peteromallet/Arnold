"""Creative form registry and shared form data structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Provocation:
    id: str
    vector: Literal["cut", "force", "spark"]
    subtype: str
    prompt_text: str
    targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProvocationCatalog:
    cuts: tuple[Provocation, ...] = ()
    forces: tuple[Provocation, ...] = ()
    sparks: tuple[Provocation, ...] = ()


@dataclass(frozen=True)
class ProvocateurVoice:
    id: str
    persona_text: str
    vector_bias: tuple[Literal["cut", "force", "spark"], ...] = ()


@dataclass(frozen=True)
class Form:
    id: str
    display_name: str
    output_extension: str
    beat_ids: tuple[str, ...]
    prep_checklist: tuple[str, ...]
    provocations: ProvocationCatalog
    stance_voice_hint: str
    provocateur_voices: tuple[ProvocateurVoice, ...]
    execution_schema_key: str = "execution_doc.json"


FORMS: dict[str, Form] = {}


def register(form: Form) -> Form:
    FORMS[form.id] = form
    return form


def get_form(form_id: str) -> Form:
    return FORMS[form_id]


def available_form_ids() -> tuple[str, ...]:
    return tuple(sorted(FORMS))


from . import joke as _joke  # noqa: E402,F401
from . import poem as _poem  # noqa: E402,F401


__all__ = [
    "FORMS",
    "Form",
    "Provocation",
    "ProvocationCatalog",
    "ProvocateurVoice",
    "available_form_ids",
    "get_form",
    "register",
]
