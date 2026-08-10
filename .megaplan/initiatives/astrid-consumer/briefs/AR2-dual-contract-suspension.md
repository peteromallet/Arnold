# AR2: Dual-contract suspension — produces re-verification on resume

**Milestone id:** `AR2-dual-contract-suspension` · **Profile:** `premium` · **Robustness:** `thorough` · **Depth:** `high` · **Vendor:** `codex`

**Depends on AR1:** AR2 re-verifies an edited *media* produces artifact through the **AR1 media reference-metadata validator**. AR1 must land first so the media content-types + reference validators exist before AR2's resume re-verification can reuse them.

Covers ticket area **D**. Bases off `arnold-generalized-pipeline` with C1–C4 landed. **This is
the real one.** C3 delivers a *decision-string* resume (the human's answer arrives as
`human_input` in the step context, matched against `resume_input_schema`). Astrid's human gate
needs MORE: the resume payload is ALSO a `produces` artifact the human may have **edited in the
run dir** ("the run-dir IS the edit surface"), and that edited artifact must be **re-verified
through the contract chokepoint on resume** before the run advances. C3 builds none of this.

## Outcome

A suspended step can resume on a **dual contract**: (1) the human's decision delivered into ctx
(C3, consumed unchanged), AND (2) a declared `produces` artifact that the human may have edited
between suspend and resume, which the runtime **re-verifies** through C1's executor seam +
chokepoint + the structural audit (and, for media, the AR1 reference-metadata validator) BEFORE
the result is treated as completed. A failed re-verification keeps the step suspended (or fails
it) with an author-facing diagnostic — the edit can never silently bypass the contract.

## Scope

IN:

- **Declare the dual-contract resume on the typed `HumanSuspension`.** The 11-field
  `HumanSuspension` envelope (`arnold/pipeline/types.py:617`, fields lines 629-639; `Suspension`
  is an alias of it) already carries `resume_input_schema`, `resume_cursor`, and `display_refs`.
  Add a NEUTRAL way to declare that resume must
  re-verify a named `produces` port against its content-type contract — WITHOUT changing the
  `ContractResult` (`types.py:739`, fields 756-763) or `HumanSuspension` field set (frozen by the
  migration). Carry it in the
  `resume_input_schema` shape and/or `display_refs` (the artifact under edit), resolved by a new
  resume-side helper — not a new dataclass field. (If a field genuinely must be added, that is an
  open question escalated to the contract owner; the default is to ride the existing fields.)
- **Re-verify the edited produces artifact on resume.** On `StepwiseDriver.resume(envelope,
  cursor: ResumeCursorRef)` (C3's concrete driver), after the human edit, re-read the named
  `produces` artifact from the run dir and re-run it through the SAME C1 executor-seam validation
  + structural audit (+ AR1 media reference validator for a media content-type) that a fresh
  produce would face. Reuse the existing chokepoint — do not fork a second validation path.
- **Three resume outcomes, total + deterministic:** (a) decision-only resume (no produces
  re-verification declared) behaves exactly as C3 today; (b) decision + a valid edited produces →
  step completes, the re-verified artifact is the authoritative output; (c) decision + an
  INVALID edited produces → the step does NOT complete: it re-suspends (default) or fails, with
  an author-facing runtime-violation diagnostic distinct from operator telemetry (the C4 diagnostic
  shape). The choice (re-suspend vs fail) is a declared policy on the suspension, defaulting to
  re-suspend so the human can fix the edit.
- **Drive it autonomously with a simulated fixture** (the C3/C4 autonomy rule): the suspend→edit→
  resume cycle is driven by a PROGRAMMATIC fixture that writes a valid (and, in a negative case,
  an invalid) artifact to the run dir + supplies the decision matching `resume_input_schema` — it
  NEVER waits on a real human.
- **Bridge cleanly to C3's composite suspension + opaque cursor:** the re-verification hooks
  behind the opaque `ResumeCursorRef` and composes with C3's composite-suspension group (a
  targeted resume of one child re-verifies only that child's produces). The generic layer takes no
  `plan_dir` (C3 finding preserved).

OUT:

- The `human_review` verb, resume UX/CLI, who-answers routing — features that plug into the
  primitive (C3's OUT, preserved). AR2 provides the re-verification hook, not the human verb.
- Producing the suspended result in the first place (C2 model seam / the adapter emits `status`).
- Decoupling the generic resume protocol from `plan_dir` (already decoupled — C3).
- Any change to the `ContractResult` type or `HumanSuspension` field set (frozen). The dual contract
  rides the existing fields + a resume-side helper.
- Astrid's gateway operator loop / approve-or-edit UX — Astrid-side.

## Locked decisions

- **The edit is the resume payload.** A produces artifact the human edited in the run dir is a
  first-class resume input, not out-of-band. It is re-verified through the contract on resume.
- **One validation path.** Re-verification reuses C1's executor-seam validation + structural
  audit + the AR1 media reference validator — never a second, weaker check. (Mirrors C2's
  "always-on audit, uniform path" decision.)
- **Fail-closed on an invalid edit.** An invalid edited produces NEVER advances the run; default
  is re-suspend (let the human fix it), with a declared `fail` policy alternative.
- **No new contract field by default.** The dual contract is expressed through the existing
  `HumanSuspension` fields (`resume_input_schema` / `display_refs`) + a resume-side helper; adding a
  field is an escalation to the contract owner, not a default.
- **Autonomy.** The cycle runs to completion under a simulated fixture; never waits on a human.
- **Decoupled.** The generic layer takes no `plan_dir`; re-verification sits behind the opaque
  `ResumeCursorRef` and composes with the composite-suspension group.

## Open questions

- Exactly how to name the re-verified produces port inside the existing `HumanSuspension` fields
  (a key in `resume_input_schema`, vs. a convention on `display_refs[*].name`) without a new field
  — and whether that survives `to_json`/`from_json` round-trip cleanly. **Default: proceed with a
  named key in `resume_input_schema` (verified to round-trip through `to_json`/`from_json`); refine
  in-milestone only if it fails.**
- Where the re-verification executes relative to C3's resume mechanics: inside the concrete
  `StepwiseDriver.resume`, or in a thin generic resume-validation helper the driver calls.
  **Default: proceed with a thin generic resume-validation helper the concrete `StepwiseDriver.resume`
  calls; refine in-milestone only if it fails.**
- The diagnostic surface for an invalid edit — reuse C4's author-facing runtime-violation
  diagnostic vs. a suspension-specific one; how it distinguishes from C1's operator telemetry.
  **Default: proceed by reusing C4's author-facing runtime-violation diagnostic (distinguished from
  C1 operator telemetry); refine in-milestone only if it fails.**
- Whether re-suspend reuses the SAME `resume_cursor` (idempotent re-edit) or mints a successor
  cursor; the idempotency contract for repeated bad edits. **Default: proceed by reusing the SAME
  `resume_cursor` so repeated bad edits are idempotent; refine in-milestone only if it fails.**
- For a media produces (large-by-ref), confirm re-verification stays reference-metadata-only
  (size/digest/content_type), never re-hashing a 2 GB file every resume (ties to E/CAS). **Default:
  proceed with reference-metadata-only re-verification (size/digest/content_type, never re-hashing
  blob bytes), per the locked decision; refine in-milestone only if it fails.**

## Constraints

- Must not modify the `ContractResult` type or `HumanSuspension` field set.
- A decision-only resume (no produces re-verification) must behave BYTE-IDENTICALLY to C3 today
  (no regression of the existing megaplan / evidence-pack resume path).
- Re-verification must be deterministic and total over {valid edit, invalid edit, no edit}.
- The generic layer must not re-couple to `plan_dir`; reuse the opaque `ResumeCursorRef`.
- An invalid edit must never be observable as a completed produces at the parent (the
  silent-completion regression class — must not regress C3's invariant).
- Media re-verification stays reference-metadata-only; no full-content re-hash on resume.

## Done criteria

1. A suspended step can declare (via the existing `HumanSuspension` fields + a resume-side helper) that
   resume must re-verify a named `produces` artifact; a test asserts the declaration round-trips
   through `HumanSuspension.to_json`/`from_json` with no new field on the frozen type.
2. On resume, an edited produces artifact in the run dir is re-read and re-verified through the
   SAME C1 executor-seam validation + structural audit (+ AR1 media reference validator for a media
   content-type); a valid edit completes the step with the re-verified artifact authoritative
   (test).
3. An INVALID edited produces does NOT complete the step: it re-suspends (default) or fails per the
   declared policy, with an author-facing runtime-violation diagnostic distinct from operator
   telemetry; the invalid artifact is never observable as completed (test, including the
   re-suspend→fix→resume→complete loop).
4. A decision-only resume (no produces re-verification declared) behaves exactly as C3 today — a
   regression test over the existing resume path shows no behavior change.
5. The full suspend→edit→resume cycle is driven by a PROGRAMMATIC fixture (writes the run-dir
   artifact + supplies the decision matching `resume_input_schema`) and runs to completion without
   ever waiting on a real human; a negative-case fixture exercises the invalid edit.
6. Re-verification composes with C3's composite-suspension group: a targeted resume re-verifies
   only the targeted child's produces; the generic layer takes no `plan_dir` (test/inspection
   confirms it sits behind the opaque `ResumeCursorRef`).
7. For a media produces, re-verification is reference-metadata-only (content_type/size/digest) and
   never re-hashes the blob content on resume (test asserts no content read).

## Touchpoints

- `arnold/pipeline/types.py:617` (`HumanSuspension`; `Suspension` is an alias — fields 629-639:
  `resume_input_schema`, `resume_cursor`, `display_refs`; CONSUMED, the dual contract rides these)
- `arnold/runtime/driver.py:135` (`StepwiseDriver.resume(envelope, cursor: ResumeCursorRef)` —
  the resume signature; today a `Protocol` stub, C3 lands the concrete driver; re-verification hooks here)
- `arnold/runtime/resume.py:51` (`ResumeCursorRef` — opaque cursor; CONSUMED)
- C1's executor-seam validation + chokepoint + structural audit (the SAME path re-verification
  reuses; CONSUMED)
- `arnold/pipeline/content_validation.py` + the AR1 media validators (media produces re-verify)
- `arnold/pipeline/contract_reduce.py` composite-suspension group (C3; targeted re-verification
  composes with it)
- a new generic resume-validation helper (the only genuinely-new code) + dual-contract /
  invalid-edit / decision-only-regression / composite / media-by-ref / autonomy tests

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is novel correctness work at the contract boundary — extending resume from a
decision string to a re-verified produces artifact, fail-closed, without modifying the frozen
contract type, without re-coupling to `plan_dir`, without regressing the existing decision-only
resume, and composing with C3's composite-suspension group. A wrong cut lets an edited artifact
silently bypass the contract (the exact failure class the epic exists to close), so it earns
premium/thorough/high.
