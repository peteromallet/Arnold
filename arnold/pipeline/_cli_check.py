"""CLI verb ``arnold pipeline check <fixture-id>``.

Loads a named pipeline fixture from a small in-process registry and runs
:func:`arnold.pipeline.c4_static_checks.run_c4_static_checks` against it.
Exits 0 on a clean report, nonzero on findings (each printed with its
locus). Distinct from ``arnold pipelines check`` (note plural) which
operates over discovered pipeline modules.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import Any, Callable, Sequence

from arnold.pipeline.c4_static_checks import run_c4_static_checks


_FixtureBuilder = Callable[[], Any]


def _wellformed_fixture() -> Any:
    """Empty-but-valid pipeline. Passes every C4 static pass."""

    class _P:
        stages: list = []
        binding_map: dict = {}

    return _P()


def _unknown_producer_fixture() -> Any:
    """Binding map names a producer stage that does not exist."""

    class _P:
        stages: list = []
        binding_map = {("consumer", "x"): ("ghost", "y")}

    return _P()


def _missing_port_fixture() -> Any:
    """Binding map names a port that the consumer stage does not declare."""

    from arnold.pipeline.types import PortRef, Stage

    class _Step:
        name = "consumer"
        kind = "tool"
        produces: tuple = ()
        consumes = (PortRef(port_name="declared", content_type="application/json"),)

    consumer = Stage(name="consumer", step=_Step())  # type: ignore[arg-type]

    class _P:
        stages = [consumer]
        binding_map = {("consumer", "undeclared"): ("producer", "y")}

    return _P()


def _media_edge_fixture() -> Any:
    """Media content-type edge: producer with ``video/mp4`` port, consumer with
    matching ``PortRef``, wired through a typed binding map.

    Kept invocation-free and adapter-free — no ``StepInvocation`` or
    ``StepInvocationAdapter`` wiring.  The fixture proves that C4 passes
    accept media content types in real ``Port`` / ``PortRef`` / binding-map
    objects and that the updated ``_iter_stages`` / ``_get_port_name``
    helpers handle them correctly.
    """

    from arnold.pipeline.types import Port, PortRef, Stage

    class _ProducerStep:  # pragma: no cover — fixture-only
        name = "producer"
        kind = "media-producer"

    class _ConsumerStep:  # pragma: no cover — fixture-only
        name = "consumer"
        kind = "media-consumer"

    producer = Stage(
        name="producer",
        step=_ProducerStep(),  # type: ignore[arg-type]
        produces=(Port(name="video_out", content_type="video/mp4"),),
    )
    consumer = Stage(
        name="consumer",
        step=_ConsumerStep(),  # type: ignore[arg-type]
        consumes=(
            PortRef(port_name="video_in", content_type="video/mp4"),
        ),
    )

    class _P:
        stages = [producer, consumer]
        binding_map = {("consumer", "video_in"): ("producer", "video_out")}

    return _P()


def _media_audio_edge_fixture() -> Any:
    """Media content-type edge with ``audio/wav`` — exercises audio pricing advisory.

    Like ``_media_edge_fixture`` but uses ``audio/wav`` content type.  This
    fixture proves that C4 passes accept audio media content types and that
    the media-pricing advisory pass produces a warning when the corresponding
    pricing unit (``audio_second``) is not present in DEFAULT_MEDIA_PRICING.
    """

    from arnold.pipeline.types import Port, PortRef, Stage

    class _ProducerStep:  # pragma: no cover — fixture-only
        name = "producer"
        kind = "media-producer"

    class _ConsumerStep:  # pragma: no cover — fixture-only
        name = "consumer"
        kind = "media-consumer"

    producer = Stage(
        name="producer",
        step=_ProducerStep(),  # type: ignore[arg-type]
        produces=(Port(name="audio_out", content_type="audio/wav"),),
    )
    consumer = Stage(
        name="consumer",
        step=_ConsumerStep(),  # type: ignore[arg-type]
        consumes=(
            PortRef(port_name="audio_in", content_type="audio/wav"),
        ),
    )

    class _P:
        stages = [producer, consumer]
        binding_map = {("consumer", "audio_in"): ("producer", "audio_out")}

    return _P()


def _multi_media_fixture() -> Any:
    """Pipeline with multiple media content types (video/mp4 + audio/wav).

    Exercises the media-pricing advisory pass across multiple categories.
    """

    from arnold.pipeline.types import Port, PortRef, Stage

    class _ProdStep:  # pragma: no cover — fixture-only
        name = "producer"
        kind = "media-producer"

    class _ConsStep:  # pragma: no cover — fixture-only
        name = "consumer"
        kind = "media-consumer"

    producer = Stage(
        name="producer",
        step=_ProdStep(),  # type: ignore[arg-type]
        produces=(
            Port(name="video_out", content_type="video/mp4"),
            Port(name="audio_out", content_type="audio/wav"),
        ),
    )
    consumer = Stage(
        name="consumer",
        step=_ConsStep(),  # type: ignore[arg-type]
        consumes=(
            PortRef(port_name="video_in", content_type="video/mp4"),
            PortRef(port_name="audio_in", content_type="audio/wav"),
        ),
    )

    class _P:
        stages = [producer, consumer]
        binding_map = {
            ("consumer", "video_in"): ("producer", "video_out"),
            ("consumer", "audio_in"): ("producer", "audio_out"),
        }

    return _P()


def _image_only_fixture() -> Any:
    """Media content-type edge with only ``image/png`` — fully priced unit.

    Unlike ``_media_edge_fixture`` (video) and ``_media_audio_edge_fixture``
    (audio), this fixture uses only ``image/png`` which maps to the ``image``
    pricing unit that *is* present in ``DEFAULT_MEDIA_PRICING``.  The
    media-pricing advisory pass should produce **no warnings** for this
    fixture.
    """

    from arnold.pipeline.types import Port, PortRef, Stage

    class _ProducerStep:  # pragma: no cover — fixture-only
        name = "producer"
        kind = "media-producer"

    class _ConsumerStep:  # pragma: no cover — fixture-only
        name = "consumer"
        kind = "media-consumer"

    producer = Stage(
        name="producer",
        step=_ProducerStep(),  # type: ignore[arg-type]
        produces=(Port(name="image_out", content_type="image/png"),),
    )
    consumer = Stage(
        name="consumer",
        step=_ConsumerStep(),  # type: ignore[arg-type]
        consumes=(
            PortRef(port_name="image_in", content_type="image/png"),
        ),
    )

    class _P:
        stages = [producer, consumer]
        binding_map = {("consumer", "image_in"): ("producer", "image_out")}

    return _P()


FIXTURES: dict[str, _FixtureBuilder] = {
    "wellformed": _wellformed_fixture,
    "media-wellformed": _media_edge_fixture,
    "media-image-only": _image_only_fixture,
    "media-audio-edge": _media_audio_edge_fixture,
    "media-multi": _multi_media_fixture,
    "mismatch-unknown-producer": _unknown_producer_fixture,
    "mismatch-missing-port": _missing_port_fixture,
}


def _fixture_ids() -> list[str]:
    return sorted(FIXTURES.keys())


def run(argv: Sequence[str]) -> int:
    """Dispatch for the ``pipeline`` verb group (singular).

    Subcommands:
      - ``check <fixture-id>``   run C4 static checks against a fixture
      - ``list``                  list available fixture-ids
    """
    parser = argparse.ArgumentParser(prog="arnold pipeline")
    sub = parser.add_subparsers(dest="action", required=True)

    p_check = sub.add_parser("check", help="run C4 static checks against a named fixture")
    p_check.add_argument(
        "fixture_id",
        nargs="?",
        help=f"one of: {', '.join(_fixture_ids())}",
    )
    p_check.add_argument(
        "--module",
        dest="module_factory",
        help="load a real Pipeline from dotted.module:factory",
    )

    sub.add_parser("list", help="list available fixture-ids")

    ns = parser.parse_args(list(argv))

    if ns.action == "list":
        for fid in _fixture_ids():
            print(fid)
        return 0

    if ns.action == "check":
        if ns.module_factory:
            if ns.fixture_id:
                print(
                    "arnold pipeline check: pass either a fixture-id or --module, not both",
                    file=sys.stderr,
                )
                return 2
            label = ns.module_factory
            try:
                pipeline = _load_pipeline_from_module(ns.module_factory)
            except Exception as exc:
                print(
                    f"arnold pipeline check: failed to load module pipeline "
                    f"{ns.module_factory!r}: {exc}",
                    file=sys.stderr,
                )
                return 2
        else:
            fid = ns.fixture_id
            if fid is None:
                print(
                    "arnold pipeline check: fixture-id required unless --module is used",
                    file=sys.stderr,
                )
                return 2
            builder = FIXTURES.get(fid)
            if builder is None:
                print(
                    f"arnold pipeline check: unknown fixture-id {fid!r}; "
                    f"known: {', '.join(_fixture_ids())}",
                    file=sys.stderr,
                )
                return 2
            label = fid
            pipeline = builder()
        report = run_c4_static_checks(pipeline)

        # ── render advisory warnings (stdout, never affect exit code) ──
        if report.warnings:
            print(
                f"WARNING: pipeline {label!r} produced"
                f" {len(report.warnings)} advisory warning(s):",
            )
            for w in report.warnings:
                print(
                    f"  [{w.pass_name}/{w.code}] locus={w.locus} -- {w.detail}",
                )

        if report.ok:
            print(f"OK: pipeline {label!r} passed C4 static checks (0 findings)")
            return 0
        print(
            f"FAIL: pipeline {label!r} produced {len(report.findings)} finding(s):",
            file=sys.stderr,
        )
        for f in report.findings:
            print(
                f"  [{f.pass_name}/{f.code}] locus={f.locus} -- {f.detail}",
                file=sys.stderr,
            )
        return 1

    return 2


def _load_pipeline_from_module(spec: str) -> Any:
    if ":" not in spec:
        raise ValueError("expected dotted.module:factory")
    module_name, factory_name = spec.split(":", 1)
    if not module_name or not factory_name:
        raise ValueError("expected dotted.module:factory")
    module = importlib.import_module(module_name)
    factory = module
    for attr in factory_name.split("."):
        factory = getattr(factory, attr)
    if not callable(factory):
        raise TypeError(f"{spec!r} did not resolve to a callable factory")
    pipeline = factory()
    if not hasattr(pipeline, "stages") or not hasattr(pipeline, "entry"):
        raise TypeError("factory did not return a Pipeline-like object")
    return pipeline


__all__ = ["FIXTURES", "run"]
