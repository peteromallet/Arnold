# M6 — Productionize: CLI ergonomics, docs, invariant test floor  [directed tier]

## Outcome
Make the round-trip a first-class, documented, well-guarded part of VibeComfy: a clean CLI surface, a
coherent bidirectional story in the docs framed for the **editor-first** user, and a durable offline
test floor that guards identity (M2), emitter + oracle (M3), layout (M4), and preserve (M5). After M6
the feature is shippable, discoverable, and protected from regression.

## Scope
- **CLI ergonomics & report.** Finalize `port export --to ui` and modifiers: `--fresh` (force M4 clean
  layout), `--from <prev.json>` (explicit layout source; else the M2 store / breadcrumb auto-discovery),
  `--out`, `--strict` (hard-fail schema-less), `--main-positions` (emit the fuller native litegraph
  metadata — `extra.ds` viewport, `state` counters, node `order`/`title`, full `groups[]` geometry — for a
  file that reopens exactly as left; lean default keeps shared templates diff-small and free of
  machine-specific canvas state; defined in M3). Stable text + `--json` (existing `port` contract). A LOUD
  recovery report in default text: stripped helper nodes, schema-less widget-order guesses, and on
  preserve re-emit a change summary (preserved / new-auto-placed / removed, named).
- **Docs (the bidirectional story), framed for editor-first users.** Update:
  - `CLAUDE.md` — add the reverse direction to the porting/decision tables (Python/IR -> UI JSON via
    `port export --to ui`). Frame correctly: **the editor owns layout, Python owns structure; the
    round-trip preserves positions + furniture when present and lays out cleanly when not.** Drop the
    old "disposable, best-effort developer view" framing — it is wrong for this user. State: preserve is
    default, `--fresh` overrides, uid-matched fidelity is exact, the legacy hash bridge is best-effort,
    the offline gate is wiring + object_info while editor-faithfulness is the comfy/RunPod gate.
  - `docs/template_porting_workbench.md` — an "emit a UI view / round-trip" section: `--to ui`,
    preserve-by-default + `--fresh`, the uid + layout-store identity scheme, furniture coverage
    (groups/notes/reroutes/bypass/subgraphs), and the gate guarantees with caveats.
  - `docs/authoring.md` — when to emit a view, and the no-metadata fresh-layout behavior for authored templates.
- **Test floor.** Ensure the default offline `pytest` enforces: uid read-back + lossless-ingest (M2),
  object_info Layer-2 gate + independent read-back + fuzz (M3), no-overlap + determinism (M4),
  position-fidelity + duplicate + legacy-bridge (M5). Mark comfy/RunPod gates (Layer 3/4) appropriately.
- **Discoverability:** `port export --help` surfaces `--to ui`, `--fresh`, `--from`, `--strict`,
  `--main-positions`; align with the `port convert` mental model so the inverse is obvious.
- **[Phase-C] `port convert --keep-virtual-wires`.** This flag governs the PYTHON representation, not the
  round-trip. Default: clean Python — Get/SetNode/Reroute resolved to direct connections (best for the
  Python-first engineer + AI agent; virtual wires still round-trip via M2/M3 furniture regardless).
  `--keep-virtual-wires`: surface Get/SetNode/Reroute as explicit nodes in the generated `.py` so a
  round-tripper can edit routing in Python too (faithful but more verbose). Document the trade-off.
- **[Phase-C] AI-agent journey (the worst-served persona) is first-class.** Add to docs + the test floor:
  an agent that programmatically adds/deletes/rewires nodes and emits gets a sensible graph with no
  position theft (monotonic uid minting, M2). `uid=` is auto-minted, never required of the agent. The
  agent edit-safety test (M5) runs in the default suite.
- **[Phase-C] Legible preserve.** Every emit prints the change summary so preserve is never invisible:
  first run says "no prior layout found — fresh layout applied"; re-emit says "preserved N / new-placed M
  / removed K (named)". A `--dry-run` prints the report + position deltas WITHOUT writing (cheap trust /
  preview); "undo" = re-run, since output under `out/` is non-clobbering — document this.

## Locked decisions (do not relitigate)
- Reverse emit is `port export --to ui` (mirror of `port convert`); re-emit preserves by default,
  `--fresh` forces clean layout.
- Docs frame the editor as layout owner and Python as structure owner; the round-trip is a real
  working feature, not a disposable view; gates described honestly (wiring/object_info offline,
  editor-faithfulness on comfy/RunPod).

## Open questions (resolve during planning)
- Recovery report shape: inline in `--json` plus the loud default-text summary.
- Default emitted-file + store naming under `out/` — deterministic, non-clobbering, discoverable by preserve.

## Constraints
- No behavior change to M2-M5 internals; this milestone wires, documents, guards. Offline/deterministic
  default suite; existing `port`/`workflows` text outputs stable; scoped — no unrelated refactors/churn.

## Done criteria
- `port export --to ui`, `--fresh`, `--from`, `--strict`, `--main-positions`, `--dry-run` and
  `port convert --keep-virtual-wires` documented in `--help`, `CLAUDE.md`, and
  `docs/template_porting_workbench.md`; the bidirectional story is coherent end to end.
- Full offline `pytest` green incl. identity + object_info + layout + preserve + **agent-edit-safety +
  virtual-wire round-trip** suites.
- The conflict-merge three-state behavior (in-sync / Python-ahead / editor-ahead-REFUSE) is documented
  and exercised; an editor-added node is never silently dropped.
- A new contributor can read the docs and: emit a clean UI view of any ready template (no metadata),
  AND round-trip an editor workflow (incl. groups/notes/reroutes/get-set) preserving their arrangement by
  default — without reading the source.

## Touchpoints
- `vibecomfy/commands/port.py`, `CLAUDE.md`, `docs/template_porting_workbench.md`, `docs/authoring.md`,
  `tests/` (verify M2-M5 suites run under default `pytest`).

## [Phase-C] Conflict-merge semantics (CLOSED, not deferred) — document the canonical loop
Single-source-per-plane: **Python owns STRUCTURE, the editor owns LAYOUT**, joined on the extrinsic uid;
the planes provably don't overlap (K3) so simultaneous edits are not a conflict. The canonical loop:
`editor .json --port convert--> Python(.py + uid=) --edit structure--> port export --to ui --> editor`.
The editor is **layout-only by contract** — structural editor changes become real only via `port convert`.
Divergence rules: (a) node edited/rewired/retuned in Python keeps its editor position (extrinsic uid);
(b) node deleted in Python -> gone, its stored layout dropped and NAMED in the report; (c) **a node ADDED
in the editor that Python lacks -> `port export` REFUSES to overwrite** (git-style "editor is ahead"
detection) and tells the user to `port convert <prior.json>` to import it or `--force-drop` to discard it
explicitly. Never silent loss. Document the three states (in-sync / Python-ahead / editor-ahead).

## Covered vs deferred journeys (Phase-B honesty — state this explicitly in docs)
"Make it work" must be honest about which editor-first journeys v1 covers vs defers, so a green epic
isn't mistaken for total coverage:
- **Covered v1:** `.json` -> Python -> `.json` with positions/furniture preserved; widget/wiring edits in
  Python keep positions (extrinsic uid); new nodes auto-placed sensibly; JSON-only collaboration (self-
  describing `.json`); fresh layout for no-metadata authored code.
- **Deferred / explicitly out of scope v1 (name them in docs, don't let them look covered):**
  (a) **PNG-embedded workflows** — the dominant ComfyUI sharing format; v1 reads/writes `.json` only, not
  PNG workflow metadata. (b) **Simultaneous conflicting edits** — a node deleted in Python yet moved in
  the editor, or widgets changed on both sides between emits: the rule is "editor owns layout, Python owns
  structure," but the precise conflict-merge for these cases is deferred and must be documented as such.
  (c) **Workflows hand-edited outside ComfyUI** that stripped the uid -> M5 legacy-hash best-effort only.

## Anti-scope
- No new layout/preserve features or aesthetic changes (M4/M5). No API-export or forward `port convert`
  changes. No RunPod/GPU work beyond marking the env-gated Layer 3/4 gates. PNG-embedded workflow support
  is explicitly out of scope for this epic (named as deferred, not silently missing).
