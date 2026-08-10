# M6: Second Non-Megaplan Proof Pipeline

## Outcome

The generic substrate is proven against a second non-Megaplan pipeline so it is not overfit to `evidence_pack` or Megaplan.

## Scope

In scope:

- Promote or build a second pipeline package under `arnold/pipelines/` with zero imports from `arnold.pipelines.megaplan`.
- Prefer a tournament or multi-judge reducer shape based on existing demos if it fits.
- Use typed ports, fan-out/fan-in, contract results, artifact replay, and the canonical runner/executor API.
- Add deterministic end-to-end tests.
- Add negative tests: deliberate port mismatch fails loudly, missing artifact fails with a typed diagnostic, and invalid contract result is rejected.
- Document the pipeline package as a proof of external authoring.

Out of scope:

- Making the new proof pipeline a Megaplan planning feature.
- Moving Megaplan-specific judge/gate vocabulary into the new pipeline.

## Locked Decisions

- The pipeline must not import Megaplan.
- The pipeline must use the same generic executor/runner surface as Megaplan and `evidence_pack`.

## Done Criteria

- Zero Megaplan imports in the new pipeline package.
- Deterministic run passes.
- Negative contract tests fail loudly and specifically.
- The same generic primitives support `evidence_pack`, the new proof pipeline, and the Megaplan runner path.

---

## Revision — SPI-forging charter (2026-06-09)

The point of the second pipeline is not just to exist with zero megaplan imports — it
is to **forge the public extension surface (SPI) by demand-pull**. "Externally usable
by different kinds of pipelines" is false if building this one required reaching into
Arnold internals, forking, or copy-pasting. So this milestone runs under a hard rule:

**RULE: build the second pipeline using ONLY public `arnold.*` API. Every time you would
have to subclass a deep internal, monkeypatch, copy a megaplan module as a template, or
hand-roll infrastructure that should be standard — STOP and promote that to a real public
extension point instead.** Each promotion is part of this milestone's diff.

Known gaps the audit predicts you will hit (promote them as you do):
- **No standard discovery/registration** — ship a `StandardDiscoveryHook`
  (scan_roots + manifest + trust policy) in `arnold/pipeline/discovery/` instead of
  re-hand-rolling the walk; megaplan's discovery becomes a config of it.
- **`ExecutorHooks` is frozen** (`arnold/pipeline/hooks.py:8-9`) — unfreeze via a named
  `extra_callbacks` escape hatch so a tournament reducer can add `on_round_*` without
  forking `run_pipeline`.
- **No `ContractResult` convenience constructors** — add `ContractResult.completed/
  failed/suspended` classmethods so every pipeline stops re-writing the 26-line factory.
- **No generic artifact I/O** — add `write_artifact(ctx,name,payload)`/`read_artifact`
  to `arnold/pipeline/artifacts.py` (evidence_pack already had to roll its own).
- **`OperationKind` is a closed `StrEnum`** (`arnold/runtime/operations.py:47,95`) — open
  the registry vocabulary to `str` (keep the canonical kinds as constants) so this
  pipeline can declare its own control-plane operations without editing `arnold/runtime/`.
- **Profiles are agent-spec-centric** (`arnold/pipeline/profiles.py`) — if this pipeline's
  "profile" isn't `{agent,model,effort}`, split stage-config into an opaque map + a
  pluggable validator rather than stuffing nonsense into agent-spec fields.

A `should_suspend`/resume path and a generic `HumanGateStep` are forged in m8; this
milestone exercises them (e.g. a human "pick the winner" gate in the reducer) to prove
they work end-to-end. **Done means: this pipeline imports zero megaplan, runs + replays
deterministically, AND every extension point it needed is now public Arnold API — not a
fork.** Write a real end-to-end test (the existing evidence_pack canary has none; do not
repeat that).
