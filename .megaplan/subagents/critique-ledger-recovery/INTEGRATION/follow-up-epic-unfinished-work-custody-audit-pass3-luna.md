# Follow-up epic unfinished-work custody audit — pass 3

Date: 2026-08-02

Mode: read-only audit of the current uncommitted epic patch; this report is the
only write. No source, Git ref, cloud, provider, owner, process, or existing
evidence was mutated.

## Verdict

**FAIL / REVISE.** The patch fixes the T1.1 count, hashes current untracked
contents, gives the proof map real file-shaped entries under exact milestone
labels, and splits T3.6 proof paths. It is not yet an honest stable handoff.

## Exact blockers

### 1. `chain_completed` is the wrong semantic gate for the finite canary

The accepted shortest route is one supervised finite slice:

`init -> plan -> critique -> gate -> finalize -> target CAS -> fence/stop`

T1.9 explicitly makes `run_chain`, `run_epic_chain`, supervisor chain launch,
and execute/review handlers unavailable. Generic `chain_completed` instead
requires a chain state advanced past every milestone with `done` completion
records. Requiring a real normal canary chain would therefore require either
forbidden chain-driver expansion or fabricated completion state. A
content-addressed manifest does not cure a false completion predicate.

Replace the first launch precondition with a generalized typed
`validated_manifest`/`completion_receipt` precondition, plus `git_tracked` for
the whole canary initiative. It should consume, for example:

- a closed-schema `finite-canary-completion.json` binding the exact phase list,
  target transition, one upload/start/stop, `STOPPED_FENCED -> SUCCEEDED_CLOSED`,
  zero recovery/notification capabilities/effects, installed generation,
  provider preflight, v2 fence, custody and supersession digests;
- a proof map containing exact files; and
- an independent final-conformance validation receipt binding the completion
  receipt SHA-256, proof-map SHA-256, validator/conformance/traceability hashes,
  and exact independent decision.

The validator must reject missing, stale, extra, duplicate, mismatched or
untracked evidence. `artifact exists` or `contains_text` is not sufficient.
The current absent canary artifacts should continue to fail closed; they must
not be represented as a normally completed chain.

### 2. Provider custody has duplicate JSON authority and stale identity

`custody-manifest.json` contains two `status` keys in the provider object.
Strict duplicate-key parsing reports `duplicates=['status']`; ordinary
`json.loads` silently discards the first value. Machine authority cannot depend
on parser last-key behavior.

The bounded repair has now committed cleanly after the rejected candidate:

- rejected candidate: commit `96d368de54876aaaec205290e2640d9daf78f3ea`,
  tree `e2f3633739acaa75ccb9324365a1b8b966fc4f4f`, rejection review SHA-256
  `84384d99578e0992a05ab11996d49cc753e343131c7583f483f232f7a5ddefa9`;
- repair candidate: commit `26aca6ace7f0af3279ca5b311e6983d4904a4d3a`,
  tree `5503c69c36bbd5a404742139d5c93cddad48edf3`, clean status SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- binary patch SHA-256 from `96d368de...` to `26aca6ace...`:
  `458b179bdb0487826bbe87342460927d75313cd0b5e2baee3bc2f8d31adac9ac`.

Preserve the old identity as a rejected evidence item. Add the repair as a
separate item with one status:
`CLEAN_BOUNDED_REPAIR_CANDIDATE_PENDING_INDEPENDENT_REVIEW_NOT_PREDEPLOY_AUTHORITY`.
Bind its author result when available, then a fresh independent-review path and
SHA-256. Even after source PASS, its scope is host observation/preflight
substrate only; it is not deploy or cloud-mutation authority.

### 3. Dirty and evidence custody is not fully reproducible/durable

The added T1.1/T1.2 untracked content hashes reproduce, and the live recorded
status/index/worktree hashes for the other frozen lanes reproduce. The schema
still does not declare the canonical byte recipes (including `-uall`, binary
diff choice, encoding and ordering), and untracked entries omit file mode/type
and disposition. T1.3 still lacks an explicit reference to the shared T1.2
worktree/status snapshot.

The provider author report is omitted. T1.10 and rejected T1.5 pass 3 name
reports but omit their hashes in the custody item (the hashes exist only in the
supersession index). Referenced evidence files are not in the candidate Git
tree and are not protected by the epic-directory `git_tracked` gate. Give each
item either a direct report hash or a typed reference to the exact supersession
entry, and put every referenced report in committed/durable custody or bind it
through the validated canary receipt.

README lines 82–83 and `UNFINISHED_WORK.md` lines 80–82 also still say accepted
T1.3 transport authority without the required qualifier **bounded Stage-A
component only**. The machine manifest's narrower scope does not repair
conflicting operator prose.

### 4. T3.6 and permanent-replay ownership is still temporally ambiguous

F2 now says it produces the launch-critical T3.6 release-authority receipt,
but F7 says that receipt is a prerequisite already bound by the pre-F1 T6.2
handoff. The same receipt cannot first be produced after the handoff and also
be its prerequisite. Either the validated finite-canary receipt binds the
pre-existing bounded release receipt and F2 only consumes/generalizes it, or
the F2 receipt is a distinct post-canary subeffect and must not be called the
launch-critical prerequisite. F2 done criteria also still say T3
"release/ticket" evidence is accepted although administrative ticket closure
belongs only to F7.

The proof map now assigns T8.3 only to F7, but F2 still owns a permanent
incident-replay candidate gate while F7 says the permanent replay test ships.
Type the F2 artifact as a candidate-gate input/precursor and reserve permanent
release-gate completion for F7, with separate exact proof files.

## Checks that pass

- Aside from the duplicate provider key, both JSON files parse.
- The YAML loader accepts eight strictly ordered F1–F8 milestones and the two
  declared preconditions.
- Current launch validation fails closed at the absent canary prerequisite;
  the uncommitted epic patch would also fail the directory `git_tracked` gate.
- The follow-up proof map now has exact milestone keys and 33 file-shaped paths,
  not directories or a silently ignored pseudo-milestone.
- T3.6 release-authority and administrative-closeout proof paths are distinct,
  and stale T1.5/T1.10-positive routes remain superseded.

## Pass condition

Freeze a clean successor patch that resolves the four blockers above, validates
JSON with duplicate-key rejection, loads the YAML, and proves the generalized
finite-canary receipt gate against accepted and hostile fixtures. Keep the
finite canary absent/fail-closed until its real receipt, exact proof files and
independent conformance receipt exist.
