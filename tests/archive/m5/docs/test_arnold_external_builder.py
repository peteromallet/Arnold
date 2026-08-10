"""Arnold external-builder documentation harness.

This staged harness models an out-of-tree builder that can read only the
authored ``docs/arnold/`` pages plus the scaffold it just requested. The
builder then proves the scaffold through the public check and doctor command
surface.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import site
import subprocess
import sys
import textwrap
from pathlib import Path

from arnold_pipelines.megaplan.runtime import discovery as registry_mod
from arnold_pipelines.megaplan import cli as arnold_cli


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHONPATH_FOR_SUBPROCESS = os.pathsep.join(
    path
    for path in (
        str(REPO_ROOT),
        os.environ.get("PYTHONPATH", ""),
        site.getusersitepackages(),
    )
    if path
)
FORBIDDEN_BUILDER_VOCABULARY = re.compile(
    # M3b: GateRecommendation typed literal removed; check for the name
    # string and decision vocabulary terms still forbidden in builders.
    r"GateRecommendation|STATE_|proceed|iterate|tiebreaker|escalate"
)


def _run_megaplan(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "FIREWORKS_API_KEY": "test-fireworks-key",
            "HOME": str(home),
            "MEGAPLAN_MOCK_WORKERS": "1",
            "OPENAI_API_KEY": "test-openai-key",
            "PYTHONPATH": PYTHONPATH_FOR_SUBPROCESS,
        }
    )
    return subprocess.run(
        [sys.executable, "-m", "arnold.pipelines.megaplan", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def _run_arnold(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "FIREWORKS_API_KEY": "test-fireworks-key",
            "HOME": str(home),
            "MEGAPLAN_MOCK_WORKERS": "1",
            "OPENAI_API_KEY": "test-openai-key",
            "PYTHONPATH": PYTHONPATH_FOR_SUBPROCESS,
        }
    )
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from arnold.pipelines.megaplan.cli.arnold import main; raise SystemExit(main())",
            *args,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def _docs_only_skill_authoring(docs_root: Path, module_name: str) -> str:
    """Author SKILL.md content from the docs-only builder sandbox."""

    assert docs_root.name == "arnold"
    visible_paths = sorted(path.relative_to(docs_root.parent).as_posix() for path in docs_root.rglob("*"))
    assert visible_paths
    assert all(path == "arnold" or path.startswith("arnold/") for path in visible_paths)

    authoring = (docs_root / "authoring-guide.md").read_text(encoding="utf-8")
    skill_integration = (docs_root / "skill-integration.md").read_text(encoding="utf-8")
    tooling = (docs_root / "tooling.md").read_text(encoding="utf-8")

    assert "arnold pipelines new my-module" in authoring or "pipelines new" in authoring
    assert "arnold pipelines check my-module" in authoring
    assert "megaplan pipelines doctor" in tooling
    assert "Every Arnold module needs instructions" in skill_integration

    return textwrap.dedent(
        f"""\
        ---
        name: {module_name}
        description: Use when validating the staged Arnold external-builder harness.
        ---

        # {module_name}

        Use this module for the staged Arnold external-builder harness. It is
        intentionally small: the external builder only needs to prove that the
        documented scaffold can be created, the module skill can be authored,
        and the package validates through the public command surface.

        Validate with:

        ```bash
        megaplan pipelines check {module_name}
        megaplan pipelines doctor
        ```
        """
    )


def _docs_only_select_tournament_module(docs_root: Path, module_name: str) -> str:
    """Build a runnable select-tournament module from docs-only inputs."""

    example = (docs_root / "examples" / "select-tournament.md").read_text(
        encoding="utf-8"
    )
    tooling = (docs_root / "tooling.md").read_text(encoding="utf-8")
    authoring = (docs_root / "authoring-guide.md").read_text(encoding="utf-8")

    assert "arnold my-module run [module-specific args]" in tooling
    assert "project_graph" in authoring or "Pipeline.builder(" in authoring
    assert "ParallelStage" in example
    assert "winner_result" in example
    assert "application/x-select-tournament-winner+json" in example

    identifier = module_name.replace("-", "_")
    return textwrap.dedent(
        f"""\
        from __future__ import annotations

        import json
        from dataclasses import dataclass
        from pathlib import Path
        from typing import Any, Mapping

        from arnold.pipelines.megaplan._pipeline.types import Edge, ParallelStage, Pipeline, Port, PortRef, Stage, StepContext, StepResult


        name = {module_name!r}
        description = "Docs-built tournament module with typed ports and a terminal winner artifact."
        driver: tuple[str, str] = ("native", "project+validate")
        entrypoint = "build_pipeline"
        arnold_api_version = "1.0"
        capabilities = ("review",)
        default_profile = None
        supported_modes: tuple[str, ...] = ()
        recommended_profiles: tuple[str, ...] = ()

        SCORE_PORT = Port("candidate_scores", "application/x-{identifier}-candidate-scores+json")
        BRACKET_PORT = Port("bracket_result", "application/x-{identifier}-bracket+json")
        WINNER_PORT = Port("winner_result", "application/x-{identifier}-winner+json")


        def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            return path


        def _read_json(path: Path) -> Any:
            return json.loads(Path(path).read_text(encoding="utf-8"))


        @dataclass(frozen=True)
        class CandidateScoreStep:
            candidate: str
            seed: int
            score: float
            name: str = "candidate_score"
            kind: str = "produce"
            prompt_key: str | None = "score_candidate"
            slot: str | None = None
            produces: tuple[Port, ...] = (Port("candidate_score", SCORE_PORT.content_type),)
            consumes: tuple[PortRef, ...] = ()

            def run(self, ctx: StepContext) -> StepResult:
                payload = {{"candidate": self.candidate, "seed": self.seed, "score": self.score}}
                path = _write_json(
                    Path(ctx.plan_dir) / "score_candidates" / f"candidate_{{self.seed}}.json",
                    payload,
                )
                return StepResult(outputs={{"candidate_score": path}}, next="done")


        def join_candidate_scores(results: list[StepResult], ctx: StepContext) -> StepResult:
            candidates = []
            for result in results:
                score_path = result.outputs.get("candidate_score")
                if score_path is None:
                    raise LookupError("missing candidate score output")
                candidates.append(_read_json(score_path))
            candidates.sort(key=lambda item: int(item["seed"]))
            path = _write_json(
                Path(ctx.plan_dir) / "score_candidates" / "v1.json",
                {{"candidates": candidates}},
            )
            return StepResult(outputs={{SCORE_PORT.name: path}}, next="bracket")


        @dataclass(frozen=True)
        class BracketStep:
            name: str = "bracket"
            kind: str = "produce"
            prompt_key: str | None = "bracket"
            slot: str | None = None
            produces: tuple[Port, ...] = (BRACKET_PORT,)
            consumes: tuple[PortRef, ...] = (PortRef(SCORE_PORT.name, SCORE_PORT.content_type),)

            def run(self, ctx: StepContext) -> StepResult:
                scores_path = ctx.inputs.get(SCORE_PORT.name)
                if scores_path is None:
                    scores_path = Path(ctx.plan_dir) / "score_candidates" / "v1.json"
                payload = _read_json(scores_path)
                candidates = list(payload["candidates"])
                candidates.sort(key=lambda item: float(item["score"]), reverse=True)
                champion = candidates[0]
                path = _write_json(
                    Path(ctx.plan_dir) / "bracket" / "v1.json",
                    {{"champion": champion, "candidate_count": len(candidates)}},
                )
                return StepResult(outputs={{BRACKET_PORT.name: path}}, next="winner")


        @dataclass(frozen=True)
        class WinnerStep:
            name: str = "winner"
            kind: str = "produce"
            prompt_key: str | None = "winner"
            slot: str | None = None
            produces: tuple[Port, ...] = (WINNER_PORT,)
            consumes: tuple[PortRef, ...] = (PortRef(BRACKET_PORT.name, BRACKET_PORT.content_type),)

            def run(self, ctx: StepContext) -> StepResult:
                bracket_path = ctx.inputs.get(BRACKET_PORT.name)
                if bracket_path is None:
                    bracket_path = Path(ctx.plan_dir) / "bracket" / "v1.json"
                champion = _read_json(bracket_path)["champion"]
                payload = {{
                    "winner": champion["candidate"],
                    "seed": champion["seed"],
                    "score": champion["score"],
                    "source_port": BRACKET_PORT.name,
                }}
                path = _write_json(Path(ctx.plan_dir) / "winner" / "v1.json", payload)
                return StepResult(
                    outputs={{WINNER_PORT.name: path}},
                    next="halt",
                    state_patch={{"select_tournament_winner": payload["winner"]}},
                )


        def build_pipeline() -> Pipeline:
            candidates = ("alpha", "beta", "gamma", "delta")
            steps = tuple(
                CandidateScoreStep(candidate=candidate, seed=index, score=float(index + 1))
                for index, candidate in enumerate(candidates)
            )
            return Pipeline(
                stages={{
                    "score_candidates": ParallelStage(
                        name="score_candidates",
                        steps=steps,
                        join=join_candidate_scores,
                        edges=(Edge(label="bracket", target="bracket"),),
                        max_workers=len(steps),
                        produces=(SCORE_PORT,),
                    ),
                    "bracket": Stage(
                        name="bracket",
                        step=BracketStep(),
                        edges=(Edge(label="winner", target="winner"),),
                        consumes=(PortRef(SCORE_PORT.name, SCORE_PORT.content_type),),
                        produces=(BRACKET_PORT,),
                    ),
                    "winner": Stage(
                        name="winner",
                        step=WinnerStep(),
                        edges=(),
                        consumes=(PortRef(BRACKET_PORT.name, BRACKET_PORT.content_type),),
                        produces=(WINNER_PORT,),
                    ),
                }},
                entry="score_candidates",
                resource_bundles=("score_candidate", "bracket", "winner"),
            )
        """
    )


def test_external_builder_docs_only_sandbox_scaffolds_authors_and_validates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Docs-only builder path creates a module, authors SKILL.md, and validates."""

    module_name = "t19-external-builder"
    home = tmp_path / "home"
    scaffold_root = home / ".megaplan" / "pipelines"
    docs_sandbox = tmp_path / "builder_sandbox" / "docs" / "arnold"
    scaffold_root.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "docs" / "arnold", docs_sandbox)

    monkeypatch.setenv("HOME", str(home))
    # ``pipelines new`` intentionally writes to the in-tree scan root. For the
    # harness stage, point that root at the temp scaffold output; subsequent
    # check/doctor subprocesses rediscover the same files through HOME's user
    # pipeline root.
    monkeypatch.setattr(registry_mod, "_SCAN_ROOTS", [(scaffold_root, "arnold_pipelines.megaplan.pipelines")])

    scaffold_rc = arnold_cli._handle_pipelines(
        os.getcwd(),
        __import__("argparse").Namespace(pipelines_action="new", pipeline_name=module_name, driver=None),
    )
    assert scaffold_rc == 0

    module_path = scaffold_root / f"{module_name.replace('-', '_')}.py"
    skill_path = scaffold_root / module_name / "SKILL.md"
    assert module_path.exists()
    assert skill_path.exists()
    assert 'driver: tuple[str, str] = ("native", "project+validate")' in module_path.read_text(
        encoding="utf-8"
    )

    skill_path.write_text(
        _docs_only_skill_authoring(docs_sandbox, module_name),
        encoding="utf-8",
    )
    authored_skill = skill_path.read_text(encoding="utf-8")
    assert f"name: {module_name}" in authored_skill
    assert "staged Arnold external-builder harness" in authored_skill

    check_result = _run_megaplan(home, "pipelines", "check", module_name)
    assert check_result.returncode == 0, (
        f"check failed:\nstdout:\n{check_result.stdout}\nstderr:\n{check_result.stderr}"
    )
    assert module_name in check_result.stdout

    doctor_result = _run_megaplan(home, "pipelines", "doctor")
    assert doctor_result.returncode == 0, (
        f"doctor failed:\nstdout:\n{doctor_result.stdout}\nstderr:\n{doctor_result.stderr}"
    )
    assert f"discovered\tuser\t{module_path}" in doctor_result.stdout
    assert f"(name={module_name})" in doctor_result.stdout


def test_external_builder_runs_docs_built_select_tournament_and_greps_builder_module(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Docs-only builder path runs select-tournament and rejects planning leaks."""

    module_name = "t20-select-tournament"
    home = tmp_path / "home"
    scaffold_root = home / ".megaplan" / "pipelines"
    docs_sandbox = tmp_path / "builder_sandbox" / "docs" / "arnold"
    scaffold_root.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "docs" / "arnold", docs_sandbox)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(registry_mod, "_SCAN_ROOTS", [(scaffold_root, "arnold_pipelines.megaplan.pipelines")])

    scaffold_rc = arnold_cli._handle_pipelines(
        os.getcwd(),
        __import__("argparse").Namespace(pipelines_action="new", pipeline_name=module_name, driver=None),
    )
    assert scaffold_rc == 0

    module_path = scaffold_root / f"{module_name.replace('-', '_')}.py"
    skill_path = scaffold_root / module_name / "SKILL.md"
    module_path.write_text(
        _docs_only_select_tournament_module(docs_sandbox, module_name),
        encoding="utf-8",
    )
    skill_path.write_text(
        _docs_only_skill_authoring(docs_sandbox, module_name),
        encoding="utf-8",
    )

    builder_source = module_path.read_text(encoding="utf-8")
    forbidden_match = FORBIDDEN_BUILDER_VOCABULARY.search(builder_source)
    assert forbidden_match is None, (
        f"forbidden planning vocabulary {forbidden_match.group(0)!r} "
        f"found in {module_path}"
    )

    check_result = _run_arnold(home, "pipelines", "check", module_name)
    assert check_result.returncode == 0, (
        f"check failed:\nstdout:\n{check_result.stdout}\nstderr:\n{check_result.stderr}"
    )

    plan_dir = tmp_path / "select_tournament_run"
    run_result = _run_arnold(home, module_name, "run", "--plan-dir", str(plan_dir))
    assert run_result.returncode == 0, (
        f"run failed:\nstdout:\n{run_result.stdout}\nstderr:\n{run_result.stderr}"
    )
    payload = json.loads(run_result.stdout)
    assert payload["pipeline"] == module_name
    assert payload["final_stage"] == "winner"
    assert payload["state"]["select_tournament_winner"] == "delta"

    winner_artifact = plan_dir / "winner" / "v1.json"
    assert winner_artifact.exists()
    winner_payload = json.loads(winner_artifact.read_text(encoding="utf-8"))
    assert winner_payload == {
        "score": 4.0,
        "seed": 3,
        "source_port": "bracket_result",
        "winner": "delta",
    }
