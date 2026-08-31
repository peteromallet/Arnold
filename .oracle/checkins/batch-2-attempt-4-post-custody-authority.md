# Batch-2 attempt-4 post-custody authority review check-in

## Review boundary

Fresh independent read-only GPT-5.6 Luna/high source review of the reconciled tree. No model, reviewer, delegation harness, launcher, Batch 3 action, commit, stage, push, merge, source/test edit, frozen-file edit, status/history/custody edit, or index mutation was performed. The prior attempt-4 review artifacts and commit `819ce9da03694fb25d2c0b6613030e9aa8f1722e` evolution are excluded.

The review considered the four frozen roots: `R3-NATIVE-001`, `R3-TERM-002`, `R3-LIFE-003`, and `R3-AUTH-004`, with authority, checker completeness, physical-door integration, KISS/YAGNI, and North Star alignment as the lens. Evidence captures are confined to `.oracle/evidence/batch-2-attempt-4-post-custody-authority/`.

## Custody observations

- Branch: `reconcile/nbf-attempt4-2297`.
- HEAD: `2297fb330cdb375b4e5bd048f0d5c37d0e06db30`.
- Source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
- Candidate implementation binding: `5da26ec5be4d13559948fe4256a114ad7626482b`.
- Candidate full source/test diff: 153829 bytes, SHA-256 `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163`.
- Candidate production diff: 109379 bytes, SHA-256 `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32`.
- Pre-review index was empty: `git diff --cached --quiet` exited `0`, and cached name-status was empty.
- The source/test tree was already dirty with the reconciled candidate patch; no source/test path was changed by this review.
- `.oracle/plan.md` is absent from the reconciled tree, so its required `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` file-byte binding could not be rehashed from the target tree. The historical object was inspected only to establish absence; it is not substituted as current-tree evidence.
- The canonical North Star file rehashed to `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`; the supplied canonical block is byte-identical through its final newline.

## Findings

### R3-NATIVE-001 — native proof remains classifier/metadata authority, not construction authority

**Blocking evidence.** `workers/_impl.py:7349-7400` selects `run_codex_step`/`run_claude_step`, checks only broad name predicates (`_is_codex_model_name` and `startswith("claude-")`), then builds a registry/proof dictionary with `constructable: True`. No selected backend/runtime/model construction occurs. `cloud/worker_dispatch.py:699-718` accepts that callback as the authoritative seam and `:601-622` only recomputes digests over the callback's returned content.

The fresh targeted probe `probe-native-unknown.stdout` shows both `gpt-5.999-unknown` and `claude-not-a-catalog-model` returned `kind=native_backend`, `constructable=true`, and a self-consistent identity. This violates the required exact catalog/model membership and actual-construction proof, despite the digest recomputation being internally consistent. The default native path therefore still admits unknown model ids and a forged/self-described positive capability record before the real worker construction seam.

### R3-TERM-002 — terminal transport loses route/provider identity and accepts conflicting replay payloads

1. `DispatchOutcome._FIELDS` contains no `provider` or `route_liveness_identity`; the fresh `probe-outcome-fields.stdout` reports both absent. `WorkerAdmissionReceipt` has those identities, but `_normalize_outcome` and the phase transport serialize only the `DispatchOutcome`, so the terminal/phase consumer does not receive the complete route/provider context required by the frozen contract.
2. `incident/ledger.py:803-817` treats a second terminal with the same reservation, kind, receipt, fingerprint, logical id, and worker as idempotent without comparing the operation payload. The fresh `probe-terminal-conflicting-payload.stdout` changes `success_payload` from `{"value":1}` to `{"value":2}` and reports `conflicting_payload_rejected=false` and the same event returned. A conflicting committed terminal payload is therefore silently accepted as a replay.
3. `cloud/babysitter/launch.py:545-608` has no WBC adapter parameter or construction/refusal branch. Its admission closure directly evaluates `ManagedCommandResult(run_managed_command(spec))`. Under the frozen `wbc_dispatch=None` rule, the managed physical door neither constructs the canonical WBC adapter nor refuses before controlled entry/reservation; it reaches the managed launch operation without the WBC closure used by native and OMP doors.

### R3-LIFE-003 — persisted transition matrix still permits accepted-first history

`incident/ledger.py:40-96` explicitly retains a compatibility exception for `states[0] == "accepted"`; the loop initializes `highest` to accepted and permits the marker. This is contrary to the frozen global matrix, which requires `not_started → entered → accepted → closed` and rejects accepted-before-entered. The fresh `probe-lifecycle-accepted-first.stdout` created a real reservation and appended an accepted marker first; it returned `accepted_first=true`.

The same conditional also allows a closed-first marker when a terminal is already present (`:66-67` checks closed-first only when no terminal exists), so the persisted matrix is not globally strict even when the terminal record is present. Reopen's strongest-marker restoration at `controlled_final_launch.py:42-65` is protected against many stale sequences by projection, but the accepted-first exception remains an authority hole rather than a harmless replay case.

### R3-AUTH-004 — checker coverage is not complete for configured-door context

1. `_AuthorityVisitor.visit_Call` in `scripts/check_worker_admission_authority.py:184-199` gates process/client/RPC/WBC diagnostics behind a function-name regex unless `strict_all_calls` is enabled. `check_files()` enables `strict_all_calls` only for paths that are not the configured `DOORS` tuple (`:318-333`). Thus a helper symbol inside a configured door can hide a raw process construction. The fresh `probe-checker-enclosing-scope.stdout` exercises the configured-mode visitor with `def helper(): subprocess.Popen(...)` and reports no diagnostic.
2. `_is_absent_wbc_test` at `:292-309` handles `is None`, equality/identity-to-None, and false comparisons, but does not recognize either `wbc_dispatch is False` or `False is wbc_dispatch`. The fresh `probe-checker-negative-gaps.stdout` reports only `raw_final_launch_access` for both forms, not `absent_wbc_legacy_delegation`. The frozen negative-form coverage therefore remains incomplete even though the repository's current configured-door scan returns an empty diagnostic list.

The checker is directionally bounded and alias-aware, but the strict fixture mode masks the configured-door enclosing-symbol gap, and the falsey WBC control-flow rule is narrower than the frozen adversarial category.

## Root-level assessment

The candidate has a single ledger/dispatch center and preserves the valid RTB, CHILD, OMP, and SCHED seams, which aligns with the North Star's one-door principle. The remaining defects are authority defects, not cosmetic gaps: a caller-visible construction proof is not a real construction proof; typed terminal records omit route/provider identity and accept unequal replay payloads; persisted history allows an illegal first state; managed launch bypasses the WBC contract; and checker fixtures do not exercise configured-door scope or both reversed falsey forms. These leave the required four-root contract unproven and preserve the North Star anti-patterns of assumed model health, ambiguous terminal evidence, and incomplete contextual enforcement.

No batch verdict is issued by this check-in.
