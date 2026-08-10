# M8: Acceptance Gate (Hard)

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

The hard acceptance gate — not a cleanup bucket. Prove the epic against its own failure class and against the platform-scale claim it was built to support. Re-run every motivating failure as a regression, benchmark the validation overhead under concurrency, produce a seam-coverage matrix over the architectural spine, and stand up a SECOND toy pipeline that rides the contract end-to-end as a generalization proof.

This milestone passes or fails the epic. It validates that the four motivating failures can no longer occur, that the always-on structural audit and chokepoint do not impose unacceptable cost, that every spine seam is accounted for (implemented / delegated / out-of-scope), and that the contract is genuinely a platform primitive — not a megaplan-shaped one — by carrying a different pipeline.

## Scope

IN:

- Regression of all four motivating failures, rebuilt against the merged result:
  1. wrong-typed payload passes validation (closed by the structural-type audit, m0b/m3).
  2. char→token overflow silently exceeds the model budget (closed by the real-tokenizer assembly-time budget, m3).
  3. first-key-valid parse accepts a malformed output (closed by `capture_step_output` + structural audit, m3).
  4. suspended child silently treated as completed (closed by suspension-aware composition, m4).
- A validation-overhead / concurrency benchmark with CONCRETE thresholds: the audit fails the gate if validation adds >10% phase wall-clock, OR >500ms on a short phase, OR p95 per-artifact exceeds {2ms metadata, 8ms ≤1MiB, 25ms 1-4MiB, 150ms 100MiB-with-hash}. Load profile = a linear 10-stage pipeline + fan-out at width 8/32/64, artifacts 1KiB-100MiB, 20 runs reporting median + p95, with the gate evaluated at width 32. By-ref policy under test: full-parse the envelope and structured payloads ≤1MiB; for >1MiB validate the sidecar manifest (content-type / schema-hash / size / sha256); blobs are always by-ref; hashing happens on WRITE, not read.
- A seam-coverage matrix: every seam in the architectural spine (Step⇄Step, Step⇄Model incl. Engine⇄Worker, Step⇄State, Author⇄Runtime, plus Engine⇄World and control-flow forks) marked implemented / delegated (to Evidence-First) / out-of-scope, with the location of each.
- A SECOND pipeline — a deterministic, Arnold-native `evidence-pack` verifier (NOT a renamed megaplan clone, which proves nothing) — authored purely via the m7 authoring API and riding the contract end-to-end. Its non-planning-shaped flow `ingest → parallel_validators → reduce → human_review? → emit_attestation` forces the contract through external `ReadRef`/`WriteRef`, multiple content-types, fan-out-reduce, a typed verdict (not megaplan's labels), human suspend/resume, route-bypass-prevention, and large-by-ref — the platform-scale generalization proof that the primitive is not megaplan-specific.
- A go/no-go acceptance verdict gating the merge.

OUT:

- New feature work or new milestones; m8 only proves what m0a–m7 built.
- The `human_review` verb / resume UX (a feature on top of m4, not part of the acceptance gate).
- Running Evidence-First (a separate epic); m8 only confirms the seam is delegated, not implemented here.
- Re-opening any prior milestone's design; m8 reports failures for fix, it does not redesign.

## Locked Decisions

- m8 is a HARD acceptance gate (Codex adjudication), including the seam-coverage matrix + perf benchmark — NOT a cleanup bucket.
- The four motivating failures (wrong-typed passes, char→token overflow, first-key-valid parse, suspended-child-silently-completed) are regressed as the failure-class proof.
- Benchmark thresholds are CONCRETE: gate fails on >10% phase wall-clock, OR >500ms short-phase, OR p95/artifact over {2ms metadata, 8ms ≤1MiB, 25ms 1-4MiB, 150ms 100MiB-hash}. Load = linear 10-stage + fan-out 8/32/64, artifacts 1KiB-100MiB, 20 runs median/p95, gate at width 32. By-ref: >1MiB validated via sidecar manifest (content-type/schema-hash/size/sha256), blobs always by-ref, hash on WRITE not read.
- The 2nd pipeline is a deterministic Arnold-native `evidence-pack` verifier (`ingest → parallel_validators → reduce → human_review? → emit_attestation`) exercising external refs, multi-content-type, fanout-reduce, typed verdict, human suspend/resume, route-bypass-prevention, and large-by-ref — NOT a renamed megaplan clone (which proves nothing).
- The seam-coverage matrix must account for every spine seam as implemented / delegated / out-of-scope.

## Open Questions

- Whether the regression harness rebuilds the engine from the merged result (as Evidence-First m11 does) or runs in place, and where the four failures' fixtures live.
- The exact columns/granularity of the seam-coverage matrix and where it is published.
- The go/no-go thresholds for a partial pass (e.g. all regressions pass but the benchmark misses budget).

## Constraints

- The gate must be objective: each motivating failure has a concrete reproduction that fails pre-contract and passes post-contract.
- The benchmark must exercise the always-on audit path (the place cost concentrates) and a realistic concurrency level.
- The 2nd toy pipeline must use the public authoring API (m7), not internal hand-rolling, or it does not prove the seam-4 claim.
- The seam-coverage matrix must be exhaustive over the spine — an unaccounted seam is a gate failure.
- Bases on the full merged epic (m0a–m7); does not modify their code beyond fixes surfaced by the gate.

## Done Criteria

1. All four motivating failures have a reproduction that demonstrably fails before the contract and passes after: wrong-typed payload rejected, char→token overflow fails at assembly, malformed first-key output rejected, suspended child suspends its parent.
2. A validation-overhead benchmark exists and FAILS the gate on any of: >10% phase wall-clock, >500ms short-phase, or p95/artifact over {2ms metadata, 8ms ≤1MiB, 25ms 1-4MiB, 150ms 100MiB-hash}. It runs the defined load profile (linear 10-stage + fan-out 8/32/64, artifacts 1KiB-100MiB, 20 runs, median + p95) and is gated at width 32. The by-ref path is exercised: >1MiB validated via sidecar manifest (content-type/schema-hash/size/sha256), blobs by-ref, hashing on write.
3. A seam-coverage matrix exists marking every architectural-spine seam implemented / delegated / out-of-scope with its location; no spine seam is unaccounted.
4. A 2nd pipeline — a deterministic Arnold-native `evidence-pack` verifier (`ingest → parallel_validators → reduce → human_review? → emit_attestation`), authored via the m7 authoring API — rides the contract end-to-end and the test RUNS IT TO A GREEN typed verdict (machine assertion), exercising external `ReadRef`/`WriteRef`, multiple content-types, fan-out-reduce, a typed verdict (not megaplan labels), suspend/resume, route-bypass-prevention, and large-by-ref. The `human_review` suspend step is driven through to completion by a PROGRAMMATIC/SIMULATED resume answer (a fixture matching `resume_input_schema`), so the pipeline runs autonomously end-to-end and NEVER waits on a real human; the gate asserts the emitted attestation/verdict validates against its contract. It is NOT a renamed megaplan clone; a clone fails this criterion.
5. A go/no-go acceptance verdict is produced and gates the merge.
6. Any failure surfaced by the gate is reported with a concrete locus for fix; m8 does not silently paper over a miss.
7. The acceptance criteria state the SHAPE-not-MEANING limit explicitly (pre-mortem risk 5): the contract guarantees STRUCTURAL validity, NOT semantic correctness — a well-typed lie still passes — so "validated" is never oversold as "correct"; the gate documents what the contract does and does not catch (semantic/perf/human failures remain outside its guarantee).
8. An OUTBOUND coverage proof is produced as an acceptance artifact (pre-mortem risk 5, the twin of m3's inbound closure): every `validate_payload` / output-parse site is catalogued and closure-proven, so every OWN model output is captured through a catalogued parse/validate site with no live orphan — the outbound mirror of the inbound `render_step_message` closure.

## Touchpoints

- regression harness + fixtures for the four motivating failures
- the merged engine from m0a–m7 (rebuilt or in-place for regression)
- validation-overhead benchmark harness (always-on audit + chokepoint hot path; concrete thresholds 10%/500ms/p95-by-size; load linear-10 + fan-out 8/32/64, 1KiB-100MiB, gate at width 32; by-ref sidecar-manifest + hash-on-write)
- seam-coverage matrix document over the architectural spine
- the 2nd pipeline: a deterministic Arnold-native `evidence-pack` verifier (`ingest → parallel_validators → reduce → human_review? → emit_attestation`) authored via the m7 authoring API
- m0b validator, m3 model-seam + token budget, m4 suspension composition, m7 authoring API (all exercised)

## Rubric

- Profile: `partnered`
- Robustness: `thorough`
- Depth: `medium`

Rationale: this is the hard gate that passes or fails the epic, so it must be rigorous (thorough) — objective regressions, a real benchmark, an exhaustive seam matrix, and a genuine generalization proof. It is partnered/medium rather than premium/high because it is proving and measuring already-built work against fixed criteria rather than designing new abstractions; the intellectual load was spent upstream, and m8's job is to be an unforgiving, well-instrumented judge.
