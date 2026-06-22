"""Steps for the ``select-tournament`` pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

# M3a: structural port/result shapes route through the Megaplan bridge here
# because this package is executed by the Megaplan pipeline executor.
from arnold.pipeline.types import PipelineVerdict, Port, PortRef
from arnold_pipelines.megaplan.step_types import StepContext, StepResult
from arnold.pipeline import ReduceResult, SelectionResult


SCORE_CONTENT_TYPE = "application/x-select-tournament-candidate-scores+json"
BRACKET_CONTENT_TYPE = "application/x-select-tournament-bracket+json"
WINNER_CONTENT_TYPE = "application/x-select-tournament-winner+json"

CANDIDATE_SCORES_PORT = Port("candidate_scores", SCORE_CONTENT_TYPE)
BRACKET_RESULT_PORT = Port("bracket_result", BRACKET_CONTENT_TYPE)
WINNER_PORT = Port("winner_result", WINNER_CONTENT_TYPE)


def _root_dir(ctx: StepContext) -> Path:
    """Return the pipeline root directory from either Arnold or Megaplan context.

    Arnold StepContext has ``artifact_root``; Megaplan has ``plan_dir``.
    This bridge helper keeps the select-tournament pipeline compatible with both runtimes.
    """
    root = getattr(ctx, 'artifact_root', None)
    if root is not None:
        return Path(root)
    return getattr(ctx, 'plan_dir')  # type: ignore[no-any-return]


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class CandidateScoreStep:
    """Score one candidate inside the fanout stage."""

    candidate: str
    seed: int
    score: float

    name: str = "candidate_score"
    kind: str = "produce"
    prompt_key: str | None = "score_candidate"
    slot: str | None = None
    consumes: tuple[PortRef, ...] = ()
    produces: tuple[Port, ...] = (Port("candidate_score", SCORE_CONTENT_TYPE),)

    def run(self, ctx: StepContext) -> StepResult:
        payload = {
            "candidate": self.candidate,
            "seed": self.seed,
            "score": self.score,
        }
        path = _write_json(
            _root_dir(ctx) / "score_candidates" / f"candidate_{self.seed}.json",
            payload,
        )
        return StepResult(outputs={"candidate_score": path}, next="done")


def join_candidate_scores(results: list[StepResult], ctx: StepContext) -> StepResult:
    """Join fanout score artifacts into the declared ``candidate_scores`` Port."""

    candidates: list[dict[str, Any]] = []
    for result in results:
        score_path = result.outputs.get("candidate_score")
        if score_path is None:
            raise LookupError("candidate_score fanout result did not declare an output")
        loaded = _read_json(score_path)
        if not isinstance(loaded, dict):
            raise ValueError(f"candidate score artifact must be an object: {score_path}")
        candidates.append(loaded)
    candidates.sort(key=lambda item: int(item["seed"]))

    reduce_result = ReduceResult(
        value=candidates,
        scores=tuple(float(item["score"]) for item in candidates),
        tally={"candidates": len(candidates)},
        provenance=tuple(str(result.outputs["candidate_score"]) for result in results),
        label="candidate_scores",
    )
    path = _write_json(
        _root_dir(ctx) / "score_candidates" / "v1.json",
        {
            "candidates": candidates,
            "scores": list(reduce_result.scores),
            "provenance": list(reduce_result.provenance),
        },
    )
    return StepResult(
        outputs={CANDIDATE_SCORES_PORT.name: path},
        verdict=PipelineVerdict(
            score=max(reduce_result.scores) if reduce_result.scores else 0.0,
            payload={"reduce_result": reduce_result},
        ),
        next="pairwise_bracket",
    )


@dataclass(frozen=True)
class PairwiseBracketStep:
    """Reduce candidate scores through a deterministic pairwise bracket."""

    name: str = "pairwise_bracket"
    kind: str = "produce"
    prompt_key: str | None = "pairwise_bracket"
    slot: str | None = None
    consumes: tuple[PortRef, ...] = (
        PortRef(CANDIDATE_SCORES_PORT.name, CANDIDATE_SCORES_PORT.content_type),
    )
    produces: tuple[Port, ...] = (BRACKET_RESULT_PORT,)

    def run(self, ctx: StepContext) -> StepResult:
        scores_path = ctx.inputs.get(CANDIDATE_SCORES_PORT.name)
        if scores_path is None:
            raise LookupError(f"missing Port input {CANDIDATE_SCORES_PORT.name!r}")

        payload = _read_json(scores_path)
        candidates = list(payload.get("candidates", [])) if isinstance(payload, dict) else []
        if not candidates:
            raise ValueError("candidate_scores Port carried no candidates")

        active = list(candidates)
        rounds: list[list[dict[str, Any]]] = []
        while len(active) > 1:
            next_active: list[dict[str, Any]] = []
            round_matches: list[dict[str, Any]] = []
            for index in range(0, len(active), 2):
                left = active[index]
                if index + 1 >= len(active):
                    next_active.append(left)
                    round_matches.append({"left": left, "right": None, "winner": left})
                    continue
                right = active[index + 1]
                winner = left if float(left["score"]) >= float(right["score"]) else right
                next_active.append(winner)
                round_matches.append({"left": left, "right": right, "winner": winner})
            rounds.append(round_matches)
            active = next_active

        winner = active[0]
        selection = SelectionResult(
            winner=int(winner["seed"]),
            subset=(int(winner["seed"]),),
            losers=tuple(
                int(candidate["seed"])
                for candidate in candidates
                if int(candidate["seed"]) != int(winner["seed"])
            ),
            scores=tuple(float(candidate["score"]) for candidate in candidates),
            cleared=True,
        )
        path = _write_json(
            _root_dir(ctx) / "pairwise_bracket" / "v1.json",
            {
                "rounds": rounds,
                "winner": winner,
                "selection": {
                    "winner": selection.winner,
                    "subset": list(selection.subset),
                    "losers": list(selection.losers),
                    "scores": list(selection.scores),
                    "cleared": selection.cleared,
                },
            },
        )
        return StepResult(
            outputs={BRACKET_RESULT_PORT.name: path},
            verdict=PipelineVerdict(
                score=float(winner["score"]),
                payload={"selection_result": selection},
            ),
            next="winner",
        )


@dataclass(frozen=True)
class WinnerStep:
    """Emit the final winner artifact from the bracket Port."""

    name: str = "winner"
    kind: str = "produce"
    prompt_key: str | None = "winner"
    slot: str | None = None
    consumes: tuple[PortRef, ...] = (
        PortRef(BRACKET_RESULT_PORT.name, BRACKET_RESULT_PORT.content_type),
    )
    produces: tuple[Port, ...] = (WINNER_PORT,)

    def run(self, ctx: StepContext) -> StepResult:
        bracket_path = ctx.inputs.get(BRACKET_RESULT_PORT.name)
        if bracket_path is None:
            raise LookupError(f"missing Port input {BRACKET_RESULT_PORT.name!r}")

        bracket = _read_json(bracket_path)
        winner = bracket["winner"]
        payload = {
            "winner": winner["candidate"],
            "seed": winner["seed"],
            "score": winner["score"],
            "source_port": BRACKET_RESULT_PORT.name,
        }
        path = _write_json(_root_dir(ctx) / "winner" / "v1.json", payload)
        return StepResult(
            outputs={WINNER_PORT.name: path},
            next="halt",
            state_patch={"select_tournament_winner": payload["winner"]},
        )


__all__ = [
    "BRACKET_CONTENT_TYPE",
    "BRACKET_RESULT_PORT",
    "CANDIDATE_SCORES_PORT",
    "CandidateScoreStep",
    "PairwiseBracketStep",
    "SCORE_CONTENT_TYPE",
    "WINNER_CONTENT_TYPE",
    "WINNER_PORT",
    "WinnerStep",
    "join_candidate_scores",
]
