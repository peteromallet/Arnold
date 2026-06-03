"""Neutral prompt-resource primitives for the Arnold pipeline boundary.

This module provides a lightweight bundle abstraction
(:class:`PipelineResourceBundle`) and a :func:`resolve_prompt` function
that dispatches on :data:`PromptSource` values — inline strings, ``.md``
file references, or callables.  The global :class:`PromptRegistry` and
:func:`register_prompt` remain in ``megaplan/_pipeline/prompts.py`` as an
M3a bridge; they are NOT duplicated here.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, TypeAlias

from arnold.pipeline.types import StepContext

#: A prompt source that can be resolved to text at dispatch time.
#:
#: * ``str`` ending with ``.md`` — path to a markdown file relative to the
#:   bundle's prompt directory.
#: * ``str`` otherwise — inline prompt text used verbatim.
#: * ``Callable`` — invoked with *ctx* and *params* to produce text.
PromptSource: TypeAlias = str | Callable[[StepContext, Mapping[str, Any]], str]


@dataclass
class PipelineResourceBundle:
    """A lightweight container of base-dir, prompt-dir, and opaque resources.

    Steps that want to resolve prompts or locate resource files should
    accept (or construct) a bundle rather than hard-coding paths.  The
    bundle is deliberately agnostic about how resources are stored —
    callers supply a ``resources`` :class:`~typing.Mapping` of their
    choosing.

    ``prompt_dir`` may be relative (resolved against ``base_dir``) or
    absolute.  ``resources`` is an opaque mapping of label → value
    (e.g. model handles, API client stubs, …).
    """

    base_dir: Path
    prompt_dir: Path
    resources: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_module(
        cls,
        module_file: str,
        *,
        prompt_dir: str = "prompts",
        resources: Mapping[str, Any] | None = None,
    ) -> "PipelineResourceBundle":
        """Create a bundle rooted at *module_file*'s parent directory.

        ``prompt_dir`` is a relative path resolved against the module's
        parent.  Useful for pipeline packages that ship prompts alongside
        their ``build_pipeline()`` module::

            bundle = PipelineResourceBundle.from_module(__file__)
        """
        base = Path(module_file).resolve().parent
        return cls(
            base_dir=base,
            prompt_dir=base / prompt_dir,
            resources=dict(resources or {}),
        )

    def resolve_prompt_path(self, source: str) -> Path:
        """Resolve a ``.md`` source string to a concrete path under *prompt_dir*.

        Returns ``prompt_dir / source``.  Callers should check existence
        before reading.
        """
        return self.prompt_dir / source


def resolve_prompt(
    source: PromptSource,
    ctx: StepContext,
    params: Mapping[str, Any] | None = None,
) -> str:
    """Resolve *source* to a prompt string.

    Dispatch rules (first match wins):

    1. *source* is a :class:`Callable` → invoke ``source(ctx, params or {})``.
    2. *source* is a ``str`` ending with ``.md`` → treat as a file path
       relative to *ctx.inputs* (or absolute) and read its text content.
    3. *source* is any other ``str`` → return it verbatim as inline text.

    Parameters
    ----------
    source:
        The prompt source to resolve.
    ctx:
        The step context at dispatch time.
    params:
        Optional extra parameters forwarded to callable sources.
    """
    if callable(source):
        return source(ctx, params or {})

    if isinstance(source, str):
        # .md files: read from filesystem.  Try relative to inputs first,
        # then absolute.
        if source.endswith(".md"):
            # Check ctx.inputs for a path-valued key matching the stem.
            stem = source.removesuffix(".md")
            if stem in ctx.inputs:
                candidate = ctx.inputs[stem]
                if isinstance(candidate, (str, Path)):
                    path = Path(candidate)
                    if path.is_file():
                        return path.read_text(encoding="utf-8")
            # Fall back to absolute path.
            path = Path(source)
            if path.is_file():
                return path.read_text(encoding="utf-8")
            # Not found — return the path reference as a message.
            return f"[prompt file not found: {source}]"

        # Bare string — inline prompt.
        return source

    # Fallback (shouldn't happen with the type alias but be defensive).
    return str(source)
