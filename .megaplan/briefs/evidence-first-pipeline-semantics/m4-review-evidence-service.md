# M4: Review-Time Evidence Service

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Generalize the M1 review-start evidence seam across all review prompt paths and migrate review payloads toward evidence-reference citations.

Review should consistently consume engine facts first, then produce semantic judgments over those facts.

## Scope

IN:

- Promote the first-slice review evidence seam into a reusable service.
- Feed fresh evidence into all relevant review prompt builders.
- Migrate review payload fields toward `evidence_ref` citations:
  - `criteria`
  - `task_verdicts`
  - `checks/findings`
  - `rework_items`
- Treat reviewer claims that contradict engine evidence as review infrastructure failure or advisory, not implementation rework.
- **Ground bulk-change verdicts in LIVE file state, not serialized deviation claims (the grounding that makes a cheap semantic summary safe).** When the data plane (Step-IO m3) represents a provably-uniform bulk operation as a cheap `rule + scope + manifest` summary rather than enumerated edits, review must VERIFY it against ground reality — query the actual current tree (e.g. an evidence fact "0 residual `from megaplan.` imports outside the plugin" computed by a live `grep`, an EvidenceRef to the real files) rather than trusting the summary or the engine's claimed deviation list. This is why the heuristic can be crude (GitHub-style): the verdict is corroborated against what is REALLY on disk. Pair with Step-IO m3's `bulk_operation`/`manifest` routable rework-target so a failed bulk-change verdict ("rule applied everywhere except N sites: …") routes to a real owner instead of an unattributable `task_id:"REVIEW"` that execute drops. Concrete motivating failure: a 337-file rename milestone spun forever because review's global rule-failures (residual `megaplan.` imports in `scripts/`, `acceptance/`, `_gen_corpus.py`) were real but un-routable, and review trusted serialized change-claims over the live tree.
- Preserve reviewer semantic judgment for coverage, placement, simplicity, and genuinely human/semantic checks.
- Add compatibility handling for existing review artifacts without evidence refs.

OUT:

- No objective gate compiler internals; use available engine evidence and leave gate compilation to M3.
- No full transition route expansion beyond review surfaces.
- No chain/cloud enforcement.

## Locked Decisions

- Review is judgment over engine facts, not the source of objective facts.
- Reviewer-provided `commands_run` and `deterministic_check` fields are claims unless linked to engine evidence.
- Prompt changes should not solve this by asking reviewers to inspect harder; the engine provides the facts.

## Open Questions

- How strict should schema validation be for review payloads during warn/shadow rollout?
- Which review findings can remain advisory without evidence refs?
- How should parallel/extreme review workers share the same immutable evidence baseline?

## Constraints

- Existing valid review artifacts remain readable.
- Large-diff and re-review behavior must remain compatible with existing review-rework fixes.
- Avoid duplicate suite/gate execution paths.

## Done Criteria

1. Every review prompt path receives the same review-time evidence object for a given code hash/head/base.
2. Blocking review findings cite engine evidence or are downgraded/incomplete.
3. Review claims contradicting engine facts cannot trigger implementation rework.
4. Existing semantic review still functions.
5. Tests cover normal review, large review, re-review, missing evidence refs, and contradictory reviewer claims.

## Touchpoints

- `megaplan/handlers/review.py`
- `megaplan/prompts/review.py`
- review parsing/normalization helpers
- `megaplan/orchestration/completion_contract.py`
- `megaplan/orchestration/execution_evidence.py`
- review and rework tests

## Rubric

- Profile: `partnered`
- Robustness: `full`
- Depth: `medium`

Rationale: cross-cutting review migration after the hard contract decisions are settled.

