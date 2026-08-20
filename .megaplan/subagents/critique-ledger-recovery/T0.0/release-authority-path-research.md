# T0.0 minimal containment release: current authority-path research

Date: 2026-08-02  
Anchor: `6787d6363e8fc0603092913ae877db14f3b9fff8`  
Inspected descendant: `e019cf4519f2e54aea7164390e4e5c11e5ad5517`

## Decisive verdict

There is no currently accepted M11 `GEN-DEPLOY` / Release Authority path that
can install RA-CONTAIN on the Hetzner agentbox and pin its runtime identity.
Do not deploy, copy, SSH, use `cloud chain`, tmux, markers, watchdogs, or a
legacy launcher as an authority substitute.

The code situation and the authority situation are different:

| Situation | Finding |
|---|---|
| Generic Run Authority contracts | Exist at the anchor; immutable, persistence-neutral records and a pure reducer/current-source checker. |
| Minimal RA-CONTAIN writer/CLI | Exists only in the four-commit descendant ending at `e019cf4519`; it is local owner-journal code, not a deployment surface. |
| RA-CONTAIN acceptance | **Not accepted**: independent pass-4 review is `FAIL` with six release blockers. |
| Runtime provenance/attestation/canary | Exist and have local tests, but they attest a runtime/canary; they do not issue a Release Authority generation or bind RA-CONTAIN. |
| `GEN-DEPLOY` contract/writer/receipt | **Absent**. Repository-wide search found no `GEN-DEPLOY`, generation-deployment owner writer, or accepted receipt schema/path. |
| Accepted cloud installation authority | **Absent**. T0.0 remains blocked. |

The existing incident artifact therefore remains truthful: the runtime member
of the poisoned tuple is explicitly “not present” and must not be inferred
([containment-decision.json](/Users/peteromalley/Documents/Arnold/evidence/critique-ledger-recovery/T0.0/containment-decision.json:1)).

## 1. What exists in the clean lineage

### Generic Run Authority substrate at `6787d6363e`

These are contracts and readers, not writers or deployment authority:

- Canonical JSON/digest and immutable contract serialization are in
  `arnold_pipelines/run_authority/contracts.py:82-149`.
- `CoordinatorFence` is defined at `contracts.py:197-209`.
- `CapabilityGrant` carries run/revision, coordinator attempt, fence token,
  subject IDs, capabilities, and evidence IDs at `contracts.py:211-230`.
- `SubjectAttempt` carries grant/fence binding at `contracts.py:233-254`.
- `Decision` is an immutable supplied record with outcomes limited to
  `accepted`, `rejected`, `quarantined`, and `superseded` at
  `contracts.py:304-338`; it does not append or authenticate a decision.
- `RunAuthorityView` is a projection over supplied records at
  `arnold_pipelines/run_authority/reducer.py:68-102`; `reduce_run_authority()`
  is the pure projection entry point at `reducer.py:294-432`.
- `evaluate_current_source()` is a read-only SATISFIED/DENIED checker. Its
  request has run/revision, coordinator attempt, grant, fence token, subject
  attempt, and decision IDs at `current_source.py:43-78`; all six matching
  conditions and quarantine denial are enforced at `current_source.py:161-225`.

The anchor contains no `ContainmentStore`, no containment CLI, and no writer.
The anchor’s acceptance evidence is the old 18-test contract/reducer set:
`tests/arnold_pipelines/run_authority/test_contracts.py`,
`tests/arnold_pipelines/run_authority/test_reducer.py`, and
`tests/run_authority/test_dependency_closure.py`.

### RA-CONTAIN descendant, `6a4be1aa2b -> 0b757880ea -> eaeca1e7d9 -> e019cf4519`

The descendant adds exactly three tracked files:

- `arnold_pipelines/run_authority/containment.py`
- `arnold_pipelines/run_authority/__init__.py`
- `tests/arnold_pipelines/run_authority/test_containment.py`

The implementation is real but local-only:

- Exact seven-field tuple validation is at `containment.py:12-37`:
  `selection_session`, `spec`, `workspace`, `plan`, `branch`, `profile`,
  `runtime`; all must be non-empty scalar strings.
- Fixed policy denies `resume`, `repair`, `execute`, `publish`, `notify`, and
  `deployment`, while `observe` is the preserved read class at
  `containment.py:12-16,135-149`.
- Append-only owner journal, lock, replay, content hash, record hash chain,
  and fsync are at `containment.py:51-112`.
- `issue()` and `terminate()` use `(cursor, owner_revision)` CAS at
  `containment.py:113-134`; canonical CAS validation is at `151-155`.
- The real JSON CLI is `python -m arnold_pipelines.run_authority.containment`
  with `status`, `issue`, `check`, and `terminate` at `containment.py:159-175`.
- Package exports intentionally expose the store/policy types but no receipt-
  only verifier at `arnold_pipelines/run_authority/__init__.py:30-45`.

The local implementation has useful tests, but passing tests do not make it an
accepted deployment. The focused lineage checks run read-only with temporary
pytest paths as follows:

```text
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/run_authority tests/run_authority
75 passed

PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_m1_containment_acceptance.py
10 passed

PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/cloud/test_final_runtime_promotion_runbook.py \
  tests/cloud/test_runtime_provenance.py
15 passed
```

`test_m1_containment_acceptance.py` is a provisional M1 adapter/repair/auditor
acceptance file (`tests/cloud/test_m1_containment_acceptance.py:1-20`); it is
not a GEN-DEPLOY acceptance test. The runtime tests validate provenance and
attestation behavior, not Release Authority ownership.

Most importantly, the independent review of exact commit `e019cf4519` is
explicitly **FAIL**:
[ra-contain-final-review-pass4.md](/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass4.md:1-6).
The defects are documented at lines 9-72:

1. Truncating a valid journal prefix after termination resurrects active
   authority; the hash chain has no durable tail/anchor.
2. An explicit duplicate `decision_id` with changed issuer/reason/CAS is
   incorrectly returned as idempotent.
3. Semantically malformed but rehashed receipts, TTLs, revisions, and
   terminate records are accepted by replay/check.
4. Malformed current receipts can escape the real CLI as `KeyError` or
   `AttributeError` traceback.
5. A post-append fsync failure can be retried into clean success despite
   durability ambiguity.
6. `issuer` is recorded but not owner-authenticated/enforced.

The same review confirms that no shell, marker, queue, cloud, or deployment
operation was introduced by the descendant (`ra-contain-final-review-pass4.md:74-106`).

## 2. Deployment/runtime surfaces and why none grants authority

The cloud CLI does have `build` and `deploy` branches at
`arnold_pipelines/megaplan/cloud/cli.py:594-620`. Its deploy report explicitly
describes a thin runner-service update, not a Run Authority generation, at
`cli.py:2855-2881`. It has no owner grant/fence input, no RA-CONTAIN tuple
binding, no immutable `GEN-*` generation, and no accepted Release Authority
receipt.

The M11 runtime machinery is real but separate:

- `runtime_provenance.py:18-27` defines the provenance receipt schema and
  identity keys; its git-clean/source/import/PTH checks are implemented at
  `runtime_provenance.py:48-69` and receipt emission at `runtime_provenance.py:650-735`.
- `runtime_attestation.py` binds launch selectors, source revision, wrappers,
  supervisor, marker, and chain binding; it is not a Run Authority writer.
- `m11_workflow_canary.py` / `m11_workflow_canary_runner.py` / verifier provide
  admitted deployed-workflow evidence. The documented owner-side canary
  commands are `admit`, `run`, and `verify` in
  `docs/megaplan/final-cloud-runtime-promotion-runbook-2026-07-31.md:778-844`.
  They derive identity from a runtime receipt, but do not issue RA-CONTAIN.

The runbook’s candidate-only phase does show how an immutable runtime could be
constructed and proven locally/in an isolated environment: source checkout,
independent `venv --copies`, frozen install, `runtime_provenance`, then
`cloud build` without `cloud deploy` at
`docs/megaplan/final-cloud-runtime-promotion-runbook-2026-07-31.md:178-249`.
That document is an operational recipe, not an accepted GEN-DEPLOY contract;
its paths and receipt variables are operator inputs, and it has no RA-CONTAIN
owner/grant binding. It cannot lawfully install this release under the stated
authority rules.

## 3. Owner inputs, tuple, and receipts

### Inputs currently accepted by code

The generic reader understands run/revision, coordinator attempt, grant,
fence, subject attempt, decision, and quarantine identities. The RA-CONTAIN
writer instead accepts only:

```text
exact_tuple, expected_cursor, expected_revision,
issuer, reason, optional ttl_seconds, optional decision_id
```

There is currently no accepted composition between a `CapabilityGrant`/
`CoordinatorFence` and `ContainmentStore.issue()`. `issuer` is an audit string,
not an enforced owner credential; the independent review calls this out at
`ra-contain-final-review-pass4.md:70-72`.

### Receipt currently produced by the local journal

If the code were accepted and invoked, the immutable content includes:

```text
decision_id, exact_tuple, denied_effects, preserved_read_class,
expected_cursor, expected_revision, cursor, revision, ttl_seconds,
termination_policy, issuer, reason, created_at, state, audit_path,
content_hash
```

The runtime member is only the caller-supplied string in `exact_tuple`; no
runtime identity is derived from a deployed interpreter. The journal path is
mandatory (`--journal`) and is echoed as `audit_path`; there is no canonical
cloud journal path or accepted receipt location. The T0.0 evidence currently
has `authority_receipt: null` and `decision_recorded: false` in
[completion-manifest.json](/Users/peteromalley/Documents/Arnold/evidence/critique-ledger-recovery/T0.0/completion-manifest.json:1).

### Required future immutable GEN-DEPLOY tuple

An accepted implementation must add a real owner-controlled generation record,
not infer one from these docs. At minimum it must bind:

```text
generation_id (GEN-*), source commit + tree hash, clean candidate root,
RUNTIME_PYTHON path + executable hash, runtime source/import root,
venv/PTH/wrapper/supervisor identity, runtime-provenance receipt digest,
deployment target + deployment id, owner identity, grant id,
coordinator attempt + fence token, owner CAS/revision, and receipt paths.
```

The runtime value in the poisoned tuple can only be filled from that accepted
receipt. The existing incident coordinates are recorded at
[containment-decision.json:9-15](/Users/peteromalley/Documents/Arnold/evidence/critique-ledger-recovery/T0.0/containment-decision.json:9),
including session `critique-ledger-accountability-v2-20260728`, plan
`cl2-wbc-backed-ledger-20260731-1411`, and profile `partnered-5-glm`.

## 4. Local-only candidate creation and validation

These commands are suitable for a local proof only. They do not install or
mutate cloud state and must not be represented as deployment acceptance:

```bash
cd /Users/peteromalley/Documents/Arnold
git merge-base --is-ancestor \
  6787d6363e8fc0603092913ae877db14f3b9fff8 \
  e019cf4519f2e54aea7164390e4e5c11e5ad5517
git diff --check \
  6787d6363e8fc0603092913ae877db14f3b9fff8 \
  e019cf4519f2e54aea7164390e4e5c11e5ad5517
git worktree add --detach /tmp/arnold-ra-contain-candidate \
  e019cf4519f2e54aea7164390e4e5c11e5ad5517
cd /tmp/arnold-ra-contain-candidate
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/run_authority tests/run_authority
```

For a local independent runtime identity check, use a separate venv and the
candidate interpreter; do not use `cloud deploy`:

```bash
python3 -m venv --copies /tmp/arnold-ra-contain-candidate-venv
/tmp/arnold-ra-contain-candidate-venv/bin/python -m pip install --no-deps -e .
PYTHONSAFEPATH=1 PYTHONPATH="$PWD" \
  /tmp/arnold-ra-contain-candidate-venv/bin/python -P \
  -m arnold_pipelines.megaplan.cloud.runtime_provenance \
  --expected-root "$PWD" \
  --expected-revision e019cf4519f2e54aea7164390e4e5c11e5ad5517
```

This proves only the candidate’s source/import/runtime provenance. It does not
produce an accepted generation, owner grant, cloud selector transaction, or
RA-CONTAIN receipt.

## 5. Narrowest remaining implementation/owner decision

There are two sequential blockers; neither permits an authority shortcut.

### A. Repair and accept RA-CONTAIN

Modify only:

- `arnold_pipelines/run_authority/containment.py`
- `tests/arnold_pipelines/run_authority/test_containment.py`
- package exports in `arnold_pipelines/run_authority/__init__.py` only if the
  accepted API changes.

Add regressions with exact names or equivalent coverage:

```text
test_truncation_after_termination_refuses
test_divergent_explicit_id_is_duplicate_conflict
test_replayed_receipt_schema_and_finite_ttl_are_strict
test_cli_malformed_current_receipt_is_typed_refusal
test_post_append_durability_ambiguity_never_retries_to_success
test_owner_identity_is_authenticated_or_explicitly enforced at the boundary
```

Do not mark the code accepted while the pass-4 reproducers remain possible.

### B. Add the missing GEN-DEPLOY owner surface

No exact implementation file exists today. The smallest coherent addition is a
new, explicitly owner-owned module and tests, for example:

```text
arnold_pipelines/run_authority/generation_deploy.py
tests/arnold_pipelines/run_authority/test_generation_deploy.py
tests/cloud/test_run_authority_generation_deploy_acceptance.py
```

The owner must approve the final names and contract. The module must:

1. accept an owner-authenticated grant/fence/CAS and exact candidate source;
2. construct and validate a clean content-addressed candidate locally;
3. execute all identity probes through the candidate `RUNTIME_PYTHON -P`;
4. derive, never caller-supply, `GEN-*`, runtime identity, receipt digest, and
   deployment target/id;
5. write an append-only generation receipt before any cloud selector change;
6. make cloud installation an explicit owner-authorized transition that checks
   the same grant/fence/CAS and exact receipt digest; and
7. have an independent verifier reject missing, stale, dirty, mismatched,
   superseded, or unaccepted generations.

The acceptance suite must include source-tree cleanliness, exact interpreter
and PTH/import root, receipt-to-generation binding, owner/grant/fence/CAS
rejection, duplicate/stale generation rejection, no-cloud local candidate
mode, and an installed `RUNTIME_PYTHON -P` attestation. Until that exists and
is accepted, there is no lawful install command.

The only owner decision needed before implementation can proceed is selection
of the exact clean source commit (the proposed RA-CONTAIN lineage is currently
`e019cf4519`, but it is not acceptable until the review blockers are fixed),
the deployment target/id, the owner credential/grant/fence, the canonical
journal/receipt roots, and the policy to use for runtime expiry/termination.

## 6. Owner invocation after an actually accepted installation

The following is the exact shape of the invocation against the installed
runtime. `RUNTIME_PYTHON`, `CONTAINMENT_JOURNAL`, and the runtime field must be
provided by the accepted GEN-DEPLOY receipt; no path is guessed here.

```bash
export RUNTIME_PYTHON=/path/from/accepted/GEN-DEPLOY/venv/bin/python
export CONTAINMENT_JOURNAL=/path/from/accepted/GEN-DEPLOY/ra-containment.ndjson
export OWNER_ID='named-run-authority-owner'
export TUPLE='{"selection_session":"critique-ledger-accountability-v2-20260728","spec":".megaplan/initiatives/critique-ledger/chain.yaml","workspace":"/workspace/critique-ledger-accountability-v2-20260728/Arnold","plan":"cl2-wbc-backed-ledger-20260731-1411","branch":"megaplan/critique-ledger-accountability-v2-20260728","profile":"partnered-5-glm","runtime":"<runtime from accepted GEN-DEPLOY receipt>"}'

# Read current owner journal state; a missing journal is genesis.
"$RUNTIME_PYTHON" -P -m arnold_pipelines.run_authority.containment \
  --journal "$CONTAINMENT_JOURNAL" status

STATE="$($RUNTIME_PYTHON -P -m arnold_pipelines.run_authority.containment \
  --journal "$CONTAINMENT_JOURNAL" status)"
CURSOR="$(jq -r .cursor <<<"$STATE")"
REVISION="$(jq -r .journal_digest <<<"$STATE")"

# Owner issues the exact tuple-bound containment decision.
"$RUNTIME_PYTHON" -P -m arnold_pipelines.run_authority.containment \
  --journal "$CONTAINMENT_JOURNAL" issue \
  --tuple "$TUPLE" --expected-cursor "$CURSOR" \
  --expected-revision "$REVISION" --issuer "$OWNER_ID" \
  --reason 'poisoned tuple containment' \
  --decision-id 'ra-contain-cl2-wbc-backed-ledger-20260731-1411'

# Owner/status and effect checks.
"$RUNTIME_PYTHON" -P -m arnold_pipelines.run_authority.containment \
  --journal "$CONTAINMENT_JOURNAL" status
"$RUNTIME_PYTHON" -P -m arnold_pipelines.run_authority.containment \
  --journal "$CONTAINMENT_JOURNAL" check --tuple "$TUPLE" --effect deployment
"$RUNTIME_PYTHON" -P -m arnold_pipelines.run_authority.containment \
  --journal "$CONTAINMENT_JOURNAL" check --tuple "$TUPLE" --effect observe
```

`deployment` must return `DENIED`; `observe` must return `ALLOWED` while the
receipt is active. For termination/revoke, first re-read status and use its
current CAS:

```bash
STATE="$($RUNTIME_PYTHON -P -m arnold_pipelines.run_authority.containment \
  --journal "$CONTAINMENT_JOURNAL" status)"
"$RUNTIME_PYTHON" -P -m arnold_pipelines.run_authority.containment \
  --journal "$CONTAINMENT_JOURNAL" terminate \
  --decision-id "$(jq -r .receipt.decision_id <<<"$STATE")" \
  --expected-cursor "$(jq -r .cursor <<<"$STATE")" \
  --expected-revision "$(jq -r .journal_digest <<<"$STATE")" \
  --issuer "$OWNER_ID" --reason 'owner revoke'
```

An independent verifier must run the same installed interpreter with `-P`,
first validate the exact source/runtime tuple against the accepted GEN-DEPLOY
receipt using `runtime_provenance`, then read the journal through `status` and
replay/check every denied effect. It must compare `decision_id`, exact tuple,
receipt content hash, journal digest/record chain, owner/grant/fence/CAS, and
the runtime identity digest; it must not accept a caller-supplied receipt,
marker, process status, or canary label. The current repo has no dedicated
containment verifier module, so this verifier is another required acceptance
surface, not an existing command to pretend is authoritative.

## 7. Loose/stale refs and worktrees

Relevant-looking refs were inspected as non-authoritative unless they are in
the accepted lineage and have accepted receipts:

- `fix/critique-recovery-ra-contain-20260802` at `e019cf4519` is a loose
  descendant of the anchor in `/private/tmp/arnold-critique-recovery-ra-contain-20260802`.
  It has the local RA-CONTAIN code, but its independent release review is
  `FAIL`; it is not merged/pushed and has no cloud receipt.
- `fix/post-m11-packaging-release-20260731` at `81a44fd930` and
  `docs/final-cloud-cutover-runbook-20260731` at `287967a8a2` are ancestors of
  the anchor. They provide packaging/runbook material only; neither adds a
  GEN-DEPLOY owner writer.
- `fix/post-m11-authority-closure-20260731` (`9dc3b6e270`),
  `fix/post-m11-publication-runtime-custody-20260731` (`63908a2aae`), and
  `fix/release-evidence-schema-hardening-20260731` (`02bed890f7`) are docs/
  evidence residuals or acceptance hardening, not a deployment authority.
- `fix/honest-deployed-workflow-canary-20260731` (`77043c0e35`),
  `fix/m11-workflow-canary-honest-pending` (`788a12e87c`), and
  `fix/post-m11-dual-runtime-cas-guards` (`715e9dba85`) are divergent loose
  branches/worktrees; they are neither descendants of the anchor nor accepted
  release tips. Canary/runtime-CAS code cannot grant Release Authority.
- The local `main` worktree at `36a1098871` is not the anchor lineage and does
  not contain the RA-CONTAIN descendant. It cannot authorize this incident.
- `.megaplan` cloud-chain logs, `docs/cloud.md`, the `megaplan-cloud` skill,
  cloud wrappers, tmux sessions, markers, and watchdog evidence are historical
  transport/process material. They are explicitly zero-authority for this
  M11 decision and cannot be promoted by naming or by a passing local test.

## Critical-path handoff

1. Do not mutate Hetzner and do not issue a containment decision from the
   anchor or from any cloud CLI.
2. Repair the six e019 RA-CONTAIN defects and add the listed regressions.
3. Add and accept the owner-controlled GEN-DEPLOY module/receipt/verifier;
   bind the runtime field only from its strict `RUNTIME_PYTHON -P` receipt.
4. Obtain the named owner’s grant/fence/CAS and canonical journal/receipt
   roots, then accept one immutable generation.
5. Only then run the owner invocations in §6 through the installed runtime and
   record the accepted receipts. Until steps 2-4 complete, the truthful state
   is **blocked**, not “candidate deployed.”

