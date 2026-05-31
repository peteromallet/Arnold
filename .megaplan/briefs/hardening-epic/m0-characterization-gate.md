# M0 — Characterization gate

**Rubric:** `directed//high`, robustness `full`
**Position in epic:** milestone 0 of 12. No dependencies. **The safety net every later milestone leans on** — the epic does broad semantic edits (M1, M3*, M4) followed by massive file moves (M5a/b) with no proof behavior held unless this exists first.

## Outcome
A fast, deterministic characterization suite that pins the *current observable behavior* of the surfaces the epic will churn, so every subsequent milestone can prove "no unintended behavior change" by keeping these green. This is not new feature testing — it captures behavior as-is (including current warts), to be updated deliberately only when a milestone intends to change behavior.

## Scope (IN)
- **Import smoke test.** A test that imports every currently-public symbol from the modules the epic will split — `megaplan.cli`, `megaplan.chain`, `megaplan.workers`, `megaplan.orchestration.evaluation`, `megaplan.store` (and re-exported names) — and asserts they resolve. This is the tripwire for M5a/M5b import-path regressions.
- **Remote-exec import guard.** A test that actually imports the symbols `cloud/supervise.py:54` constructs in its remote one-liner (`_capture_sync_state`, `ChainState`, …) *from `megaplan.chain`* — i.e. `from megaplan.chain import _capture_sync_state`. The existing test only checks the command *string* contains the name; that won't catch a move. (Flagged by the M5 reviewer as the single biggest M5 risk.)
- **CLI parser snapshot.** A test that serializes the full `build_parser()` surface (every subcommand, every flag, defaults, choices) to a stable snapshot, so M5b (cli split) and M6a (flag fixes) can prove they didn't silently drop or rename a flag.
- **Extend the existing store contract test.** `tests/contract/store_contract.py` (454 loc) already exists — extend it so it runs against `DBStore`, `FileStore`, and `MultiStore` and asserts the parity properties M2 will rely on (same method surface, same error class for the same condition). Do NOT rewrite it; build on it.
- **1–2 end-to-end golden runs.** A minimal `bare`/`light` plan run (mock workers, deterministic) that exercises plan→finalize→execute and a resume, capturing the resulting `state.json` shape + key artifacts as a golden. This is the backstop for M2 (state.json routing) and M3* (error-path changes).

## Locked decisions
- **Characterization, not specification** — pin what the code *does today*, including current quirks. When a later milestone deliberately changes behavior, it updates the golden in the same PR with a comment explaining why.
- Build on existing harnesses (`tests/contract/store_contract.py`, `tests/conftest.py` factories) — do not fork parallel scaffolding.
- Tests must be fast and deterministic (mock workers/models; no network, no real LLM calls).

## Open questions (for plan to resolve)
- Which symbols count as "public" for the import smoke test — everything in each module's `__all__`, or everything tests currently import? (Survey `tests/` imports to build the list.)
- What's the smallest deterministic plan fixture that meaningfully exercises resume? (Likely reuse `tests/test_pipeline_resume.py` machinery.)

## Constraints
- Zero flakiness — these gate every milestone; a flaky baseline poisons the whole chain.
- Snapshots must be readable/diffable (JSON/text), not opaque pickles, so a reviewer can see what changed.

## Done criteria
- `pytest` target(s) that run the import smoke, remote-exec import guard, CLI parser snapshot, extended store contract, and golden e2e — all green on current `main`.
- A one-paragraph `docs/` note telling each subsequent milestone: "keep these green; update a golden only when you intend the behavior change, and say why in the PR."
- The remote-exec guard fails loudly if `_capture_sync_state` is not importable from `megaplan.chain`.

## Touchpoints
`tests/contract/store_contract.py` (extend), `tests/` (new characterization tests), `tests/conftest.py` (reuse factories), reads across `megaplan/cli.py`, `chain.py`, `workers/`, `orchestration/evaluation.py`, `store/`, `cloud/supervise.py`.

## Anti-scope
- Do NOT fix any bug or change any behavior — if a test pins a current wart, that's correct; the warts get fixed in their owning milestone.
- Do NOT add coverage for surfaces the epic won't touch.
- Do NOT refactor the existing contract test — extend it.
