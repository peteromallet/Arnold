"""
Intent oracle — text-based and vision-based judges, plus panel aggregation.

Evaluates a workflow edit against a natural-language intent using Claude LLMs.

Install the intent extra before use:
    uv pip install -e ".[intent]"

The anthropic SDK is imported lazily inside ``judge_text`` and ``judge_vision``
so that the rest of the ``vibecomfy.intent`` package can be imported without
requiring the SDK.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PROMPT_PATH = Path(__file__).parent / "prompts" / "text_judge.prompt.md"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text()

_VISION_PROMPT_PATH = Path(__file__).parent / "prompts" / "vision_judge.prompt.md"
_VISION_SYSTEM_PROMPT: str = _VISION_PROMPT_PATH.read_text()


@dataclass
class JudgeVerdict:
    pass_: bool
    criteria: dict[str, bool]
    rationale: str


def judge_text(
    pre_ir: Any,
    post_ir: Any,
    nl_intent: str,
    *,
    model: str = "claude-sonnet-4-6",
    client: Any = None,
) -> JudgeVerdict:
    """Evaluate a workflow edit against a natural-language intent.

    Parameters
    ----------
    pre_ir:
        The workflow IR (or any serialisable representation) before the edit.
    post_ir:
        The workflow IR after the edit.
    nl_intent:
        Natural-language description of the intended edit.
    model:
        Claude model ID to use.
    client:
        Pre-built Anthropic client.  If None, a client is constructed from
        the ``ANTHROPIC_API_KEY`` environment variable.  Inject a stub for
        offline tests.
    """
    import anthropic  # lazy import — SDK not required for other intent modules

    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)

    user_content = json.dumps(
        {
            "nl_intent": nl_intent,
            "pre_ir": pre_ir,
            "post_ir": post_ir,
        },
        indent=2,
    )

    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()
    parsed = json.loads(raw)

    criteria = {
        "correct_node_targeted": bool(parsed["criteria"]["correct_node_targeted"]),
        "correct_parameter_changed": bool(parsed["criteria"]["correct_parameter_changed"]),
        "value_semantically_matches_intent": bool(
            parsed["criteria"]["value_semantically_matches_intent"]
        ),
        "no_orphaned_wiring": bool(parsed["criteria"]["no_orphaned_wiring"]),
    }
    pass_ = all(criteria.values())

    return JudgeVerdict(
        pass_=pass_,
        criteria=criteria,
        rationale=str(parsed.get("rationale", "")),
    )


def judge_vision(
    pre_images: list[bytes | str],
    post_images: list[bytes | str],
    nl_intent: str,
    *,
    model: str = "claude-opus-4-8",
    client: Any = None,
) -> JudgeVerdict:
    """Evaluate a workflow edit against a natural-language intent using rendered images.

    Parameters
    ----------
    pre_images:
        Rendered images before the edit.  Each item is either raw PNG/JPEG bytes
        or a base64-encoded string.
    post_images:
        Rendered images after the edit.
    nl_intent:
        Natural-language description of the intended edit.
    model:
        Claude model ID to use.
    client:
        Pre-built Anthropic client.  If None, a client is constructed from
        the ``ANTHROPIC_API_KEY`` environment variable.  Inject a stub for
        offline tests.
    """
    import anthropic  # lazy import

    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)

    def _to_b64(img: bytes | str) -> str:
        if isinstance(img, (bytes, bytearray)):
            return base64.b64encode(img).decode()
        return img  # already base64 string

    def _image_block(img: bytes | str) -> dict:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": _to_b64(img),
            },
        }

    content: list[Any] = [{"type": "text", "text": f"Natural-language intent: {nl_intent}\n\nPre-edit images:"}]
    for img in pre_images:
        content.append(_image_block(img))
    content.append({"type": "text", "text": "Post-edit images:"})
    for img in post_images:
        content.append(_image_block(img))

    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=_VISION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    raw = response.content[0].text.strip()
    parsed = json.loads(raw)

    criteria = {
        "correct_node_targeted": bool(parsed["criteria"]["correct_node_targeted"]),
        "correct_parameter_changed": bool(parsed["criteria"]["correct_parameter_changed"]),
        "value_semantically_matches_intent": bool(
            parsed["criteria"]["value_semantically_matches_intent"]
        ),
        "no_orphaned_wiring": bool(parsed["criteria"]["no_orphaned_wiring"]),
    }
    pass_ = all(criteria.values())

    return JudgeVerdict(
        pass_=pass_,
        criteria=criteria,
        rationale=str(parsed.get("rationale", "")),
    )


@dataclass
class PanelVerdict:
    text: JudgeVerdict
    vision: JudgeVerdict
    pass_: bool


def panel_verdict(text: JudgeVerdict, vision: JudgeVerdict) -> PanelVerdict:
    """Aggregate text and vision verdicts with AND logic."""
    return PanelVerdict(
        text=text,
        vision=vision,
        pass_=text.pass_ and vision.pass_,
    )
