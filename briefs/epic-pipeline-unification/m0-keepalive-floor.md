# M0 — Keep-alive floor: pinned engine + report-only schema + dual-run rig + oracle skeleton

**Milestone label:** `m0-keepalive-floor` · **Tier:** T0 (keep-alive floor) · **Profile:** apex/thorough
(this is the scaffold the entire epic self-hosts on — a wrong floor poisons every milestone).
**Authoritative sources:** `validation/sequencing/PROGRAM.md` §"M0", §"Strangler discipline", §"Open
sequencing risks"; `pipeline-unification-EPIC.md` §"Sequenced build program — FINAL" (M0 bullet),
§"Cross-cutting/guardrails"; `validation/premortem/p3-self-reference.md` (the four recommendations);
MEMORY `project_dogfood_engine_shadow_and_openrouter`; `validation/human-blockers/REGISTER.md`.

---

## Outcome

The epic can self-host **safely**. After M0, a single t0 "go" arms a `megaplan chain` that drives the
11-organ build where the code *executing* the build is a **pinned, frozen external engine in its own
venv** — never the working tree it is mutating — so no merged milestone ever changes the driver
mid-flight (the p3 H1/H2/H3 deadlock class is structurally impossible). M0 lands **no organ and no
reshaper**; it is pure risk-removal. It delivers three things, all default-OFF / report-only so they
cannot perturb the live driver:

1. **A pinned-engine harness** — a frozen megaplan installed from a tag into a dedicated venv, driving
   this epic against the worktree as *target repo*, with `--no-git-refresh` so the engine source on
   disk is never `git pull`-stomped under the running process.
2. **A schema-version validator in report-only / accept-missing-as-v0 mode** — so when M1 stamps
   `schema_version`, an old writer can never deadlock a new reader (p3 H1). M0 ships the validator
   *plumbing*; M1 ships the *stamp*. The fail-closed flip is deferred to after the epic.
3. **The standing dual-run rig + oracle harnesses** — (a) the OLD frozen engine drives a throwaway
   1-milestone plan end-to-end (OLD-alive); (b) a planning-shaped throwaway plan runs on whatever NEW
   pieces exist (NEW-alive); (c) a **behavioral-replay oracle harness** that compares NEW-path traces
   against recorded REAL-run traces (incl. recovery/escalate/blocked, not just happy path); (d) a
   **substrate-swap oracle skeleton** (resume-across-version / crash-isolation harness, no real swap to
   gate yet — M3 is its first consumer).

---

## Scope (work items tied to current file:line)

**W1 — Pinned-engine launcher + verification probe.** Add a launcher (script + thin test) that
(i) builds/installs a frozen megaplan from a pinned tag/sha into its own venv, (ii) invokes
`megaplan chain` from THAT interpreter against the epic worktree as target, and (iii) asserts at phase
boundary that `megaplan.__file__` resolved inside a phase subprocess points at the **pinned** copy, not
the editable target tree. The subprocess seam already exists — `auto._run_megaplan` shells
`[sys.executable, "-m", "megaplan", *args]` (`megaplan/auto.py:266,287`); the probe verifies
`sys.executable`/`PATH` resolve to the pinned venv (defeats p3 H3 / MEMORY dogfood-shadow). The
`--no-git-refresh` plumbing is **already present** (`chain/__init__.py:1242,1382,1386,1713,1746,1915,1922`;
honored by `git_ops._refresh_base_branch` at `chain/git_ops.py:23,41-43`) — W1 wires it ON for the epic
and adds the missing *verification* that it is on, not the flag itself.

**W2 — Report-only schema validator (accept-missing-as-v0).** Add a validator entered by
`load_plan_from_dir` (`megaplan/_core/state.py:93`) and the chain-state path
(`ChainState.from_dict` `chain/__init__.py:477`, `load_chain_state` `:550`): read an optional
`schema_version`; **missing → treat as v0 and pass; unknown/newer → log a structured report event and
pass** (never raise). Gate the fail-closed behavior behind a default-OFF flag
`MEGAPLAN_SCHEMA_FAIL_CLOSED` (unset for the whole epic). No stamp is written in M0 (that is M1's seed) —
M0 only proves the *reader* tolerates both stamped and unstamped state. This is the direct mitigation of
p3 H1 ("the old writer perpetually removes the field the new reader demands").

**W3 — Dual-run rig (OLD-alive + NEW-alive harness).** A standing test/harness that on demand:
(a) boots the frozen OLD engine and drives a throwaway 1-milestone plan to a terminal state
(OLD-alive); (b) drives a planning-shaped throwaway plan on the current tree behind a default-OFF flag
(NEW-alive — in M0 the NEW path == the OLD path, so this asserts the rig works, baselining for M1+).
Both run on **throwaway** plans in a temp dir, never on the epic-driving chain. Reuse the existing
`tests/test_chain.py` / `tests/test_chain_in_worktree.py` fixtures as the plan-shape source.

**W4 — Behavioral-replay oracle harness + recorded-trace corpus seed.** Record a small REAL-run trace
corpus from today's subprocess engine — **including recovery / escalate / blocked-retry traces**, the
class MEMORY shows recurring (execute-stall, shannon-stream-stall, chain-blocked-retry,
tiebreaker-downgrade) — and a harness `replay_oracle(recorded, candidate) -> {match | divergence@field}`
that diffs a candidate trace against the corpus. In M0 the candidate == the recording, so it must report
MATCH (proves the harness is sound); M1's shadow-WAL fold-equivalence becomes its first real consumer,
making the shadow load-bearing from M2.5 on. The corpus is committed as a fixture so every later PR
replays against it.

**W5 — Substrate-swap oracle skeleton.** A harness shell `substrate_swap_oracle(...)` with the
resume-across-version and crash-isolation *shapes* stubbed (record a run on engine@A, attempt
resume/replay on engine@B; assert the recorded blocked-retry-then-resume trace survives the version
boundary). M0 ships the **skeleton + a self-test that the skeleton runs green on engine@A==engine@B**;
M3 fills in the real cross-version swap it gates. Explicitly labelled: this is the SOLE retirement
authority at a swap seam — **never** the happy-path parity gate.

**W6 — Strangler-gate wiring.** A single machine-gate entrypoint that runs W3+W4(+W5 self-test) and
emits a green/red verdict consumable by the chain's per-milestone gate, so from M1 on every milestone
boundary auto-runs "OLD-alive AND NEW-alive AND replay-MATCH"; red auto-halts/auto-reverts or enters the
bounded escalation ladder (REGISTER §3 chain.yaml ladder), never parks on a person.

---

## Locked decisions

- **Pinned external engine in its own venv, not the editable tree.** The deliverable IS the driver; this
  is the one case where dogfooding the live tree is actively unsafe (p3 verdict). Frozen engine + target
  worktree + `--no-git-refresh`.
- **Schema validator ships report-only / accept-missing-as-v0; fail-closed deferred behind a default-OFF
  flag flipped only after the epic completes.** (p3 rec #2; REGISTER M1 "`schema_version` JSON-path,
  report-only till last".)
- **No organ, no reshaper, no behavior change.** M0 is `W0` from the strangler lens folded in as a real
  milestone — scaffold only.
- **The behavioral-replay + substrate-swap oracle is the SOLE retirement authority**; the happy-path
  parity gate is honestly labelled "control-flow/artifact parity on the happy path, NOT drift-provably-
  zero" and is never the swap gate (PROGRAM §"Strangler discipline", risk #6).
- **Replay corpus MUST include recovery/escalate/blocked-retry traces** (load-bearing per PROGRAM risk
  #2), not just happy-path.
- **The subprocess seam stays alive** (it survives through M3, retired only at M6); M0 does not touch it
  beyond verifying it resolves the pinned engine.

## Open questions (each RESOLVED to its default)

- **Pin by git-sha or PyPI tag?** → **git-sha of the current `main` HEAD at t0**, installed into a venv
  (`pip install 'megaplan-harness @ git+file://...@<sha>'` or a copied checkout). Most reversible, no
  release ceremony. (Default; `must_ask_peter=false`.)
- **Where does the validator read `schema_version` from?** → **a JSON-path field on the state dict**
  (state.json / chain_state.json); a DB column is deferred (REGISTER M1). Accept-missing-as-v0.
- **What is the throwaway plan's shape?** → **the smallest planning-shaped plan** the existing chain
  tests already exercise (`tests/test_chain.py` fixtures); 1 milestone, default robustness.
- **How big is the recorded-trace corpus?** → **minimal-but-representative**: one happy-path + one each
  of recover / escalate / blocked-retry, drawn from real runs; expand only if a later milestone's fold
  needs a branch the corpus lacks.
- **Does M0 stamp `schema_version`?** → **No.** Stamp is M1's seed; M0 only proves the reader tolerates
  stamped+unstamped. (Avoids a stamp-without-validator window.)
- **What happens on a red strangler gate during the epic?** → **the REGISTER ladder**: retry fresh ×2 →
  bump profile/robustness one tier, re-run once → `stop_chain` + auto-filed megaplan-ticket. Never a
  human wait.

## Constraints

- **Never `git pull` merged milestone code into the running engine's source.** `--no-git-refresh` ON for
  the whole epic; milestone merges land at the review-merge seam and the pinned engine is re-launched
  deliberately, never stomped under the live process (p3 H4).
- **Report-only validator must never raise** for the duration of the epic; the fail-closed flag stays
  unset.
- **No flag M0 adds may be default-ON.** Dual-run/oracle harnesses run on throwaway plans only; they must
  not touch or perturb the epic-driving chain's state.
- **Back-compat:** the validator accepts every state file the current tree writes today (no
  `schema_version` present) — verified against the existing fixture corpus and a clean live run.
- **Bare-model-name safety (MEMORY):** the pinned-engine harness must inherit the
  no-silent-OpenRouter-routing fix; a bare `deepseek-*` resolves to direct `api.deepseek.com`, never
  OpenRouter unless `openrouter:`-prefixed.

## Done criteria (testable, incl. the oracle gate)

1. **Pinned-engine probe (W1):** a phase subprocess launched by the harness asserts
   `megaplan.__file__` resolves under the **pinned venv**, not the editable target tree; the assertion
   fails loud if it points at the worktree. (Defeats p3 H3 / dogfood-shadow.)
2. **`--no-git-refresh` verified ON (W1):** an integration check confirms the epic chain runs with
   `no_git_refresh=True` and that `_refresh_base_branch` is skipped (no `git pull` against the engine
   source).
3. **Report-only validator (W2):** unit tests prove (a) state WITHOUT `schema_version` loads as v0 and
   passes; (b) state WITH an unknown/newer `schema_version` logs a structured report event and STILL
   loads; (c) NOTHING raises while `MEGAPLAN_SCHEMA_FAIL_CLOSED` is unset; (d) the flag set to true makes
   (b) raise (proving the deferred fail-closed path exists but is off).
4. **OLD-alive (W3):** the frozen engine drives a throwaway 1-milestone plan to a terminal state in CI.
5. **NEW-alive (W3):** a planning-shaped throwaway plan completes behind the default-OFF flag (in M0 the
   NEW path == OLD path; the assertion is "the rig works").
6. **Behavioral-replay oracle harness (W4) — THE MILESTONE ORACLE GATE:** replaying the recorded corpus
   (happy + recover + escalate + blocked-retry) against itself reports **MATCH** on every trace; an
   injected single-field divergence reports `divergence@<field>` (proves the harness can fail). This is
   the green/red signal every later milestone's retirement is authorized against.
7. **Substrate-swap oracle skeleton (W5):** the skeleton runs green for engine@A==engine@B, including a
   recorded blocked-retry-then-resume trace surviving the (degenerate) version boundary; it is wired as a
   distinct required gate (NOT the parity gate) ready for M3 to fill in.
8. **Strangler gate (W6):** one entrypoint runs W3+W4+W5-self-test and emits a single machine verdict;
   on red it auto-halts/auto-reverts or enters the bounded ladder, with zero human-wait.
9. **t0 arm path:** after one recorded t0 go, the chain auto-arms on the M1/W8 lint — M0 does not
   introduce any new human gate (REGISTER §1).

## Touchpoints

- `megaplan/auto.py:238,266,287` (`_run_megaplan` subprocess seam — verify it resolves the pinned engine;
  do NOT modify the seam).
- `megaplan/chain/__init__.py:1242,1382,1386,1713,1746,1915,1922` (`no_git_refresh` plumbing — wire ON +
  verify) and `:477,550,567` (`ChainState.from_dict` / `load_chain_state` / `save_chain_state` — add the
  report-only read path).
- `megaplan/chain/git_ops.py:23,41-43,55,71` (`_refresh_base_branch` — confirm it is skipped under
  `--no-git-refresh`; the abort-on-dirty path stays as-is).
- `megaplan/_core/state.py:93` (`load_plan_from_dir` — add the report-only validator hook ahead of the
  existing legacy-migration sniff at `:96-100`).
- `tests/test_chain.py`, `tests/test_chain_in_worktree.py`, `tests/test_auto.py` (fixtures for the
  throwaway plan shape + the recorded-trace corpus home).
- New: a `tools/`-level pinned-engine launcher + an oracle/dual-run harness module + a committed
  recorded-trace corpus fixture.
- `briefs/epic-pipeline-unification/chain.yaml` (the epic runs OLD engine, flag-OFF, `--no-git-refresh`).

## Anti-scope

- **No `schema_version` STAMP** (M1's seed) — M0 only ships the tolerant *reader*.
- **No organ / reshaper** — no Port, no WAL/shadow log, no Activation, no Governor, no Ledger. The
  shadow-WAL seed is M1.
- **No fail-closed schema enforcement** during the epic (deferred behind the default-OFF flag, flipped
  only after the epic completes).
- **No removal/refactor of the subprocess seam** (`_run_megaplan`) — it must survive through M3, retired
  only at M6.
- **No real cross-version substrate swap** — only the skeleton + a degenerate self-test; M3 is the first
  real consumer.
- **No change to the happy-path parity gate's semantics** beyond honestly labelling it and adding the
  oracle as the supplementary, authoritative swap gate.
- **No in-process dispatch path** (`MEGAPLAN_UNIFIED_DISPATCH`) — that is M3, default-OFF.
