# Workflow Precedent Agent Micro-Moments

This note captures UX risks for agents using the workflow precedent research
pipeline. It is based on a DeepSeek review of
`workflow-precedent-research-plan.md`.

## Position

DeepSeek-style agents can handle this pipeline if the system does the hard
graph/scoring/safety work and gives the agent structured choices. They are good
at classification, template filling, and following hard rules. They are brittle
when asked to infer topology from flat outlines, judge external trust, map
precedent nodes onto a live graph, or decide when warnings should block.

The design should therefore move scoring, trust tiers, socket checks, anchor
mapping, and semantic validation into deterministic code wherever possible.

This is a trade-off, not a judgement that the model should be boxed into a
script. If the system is too loose, the agent wastes context reconstructing
facts the code can know exactly, such as socket compatibility or whether an
audio node is dangling. If the system is too prescriptive, it underuses the
agent's judgement: the model can compare patterns, notice surprising precedent
fit, explain why a local result is "close but wrong", and decide when the
retrieved evidence does not support execution.

The target is therefore guided agency:

- deterministic code should provide exact facts, safety gates, size limits,
  validation results, and structured candidate evidence;
- the agent should decide what those facts mean for the user's task, select or
  reject precedents, ask for a better segment when the fetched excerpt is
  insufficient, and write the implementation brief;
- prompts and schemas should prevent silent failure modes, not pre-answer every
  interesting judgement call.

In practice, "precompute match signals" means "give the agent a compass", not
"force the top score to win". "Hard gates" should apply to safety, validity,
and context-size limits. Pattern choice and adaptation still belong to the
agent, provided the handoff records the evidence it used.

## Execution Through-Line

The intended agent UX is graph-native internally and Python-readable at the
evidence boundary:

```text
normalized workflow graph
-> inspection summary
-> fetched workflow slice
-> Python-rendered evidence
-> PrecedentAdaptationPlan
-> edit operations
-> validated candidate graph
-> emitted Python / Comfy API
```

The missing load-bearing handoff is not a total graph-to-graph isomorphism. It
is a narrower `PrecedentAdaptationPlan` that records:

- `selected_precedent_id`;
- `selected_slice`;
- `anchor_bindings` into the current graph;
- `required_new_nodes`;
- `required_rewires`;
- `socket_evidence`;
- `avoid_patterns`;
- `semantic_checks`.

The agent sees Python-rendered precedent evidence because that is readable and
adaptable. The system executes against graph addresses, node schemas, socket
checks, and edit operations. Final Python is produced by the existing workflow
emission path after the candidate graph validates.

## Micro-Moments

### 1. Classification Trigger

- Goal: decide whether the request routes directly to edit or to precedent
  research.
- Data: user request, current graph metadata, detected model families.
- Confusion: casual wording can hide complex edits, while explanation requests
  can look like edit requests.
- Context risk: low, but a wrong route cascades.
- Interface need: required `route`, `research_goal`, `edit_complexity`,
  `model_family`, and `change_goal`.
- DeepSeek note: good with rigid schemas; add confidence and default
  low-confidence complex model-family edits to precedent research.

### 2. Model Family Extraction

- Goal: identify LTX, Wan, Flux, SVD, or mixed families.
- Data: graph node class types and user-mentioned families.
- Confusion: model family often lives in the graph, not the text; mixed-family
  graphs break a single-string field.
- Context risk: moderate if the classifier must inspect topology.
- Interface need: pass `graph_families` and `mentioned_families`; make
  `model_family` a list.
- DeepSeek note: good at explicit extraction, weaker when asked to merge
  conflicting cues unaided.

### 3. Workflow Pattern Extraction

- Goal: turn a request into searchable workflow pattern terms.
- Data: request, family, graph task shape.
- Confusion: too narrow misses precedents; too broad returns noise.
- Context risk: low.
- Interface need: emit `exact_pattern` and `broad_pattern` from a constrained
  vocabulary such as `image-to-video`, `custom audio`, `lipsync`, `LoRA stack`.
- DeepSeek note: will invent elegant terms unless vocabulary is constrained.

### 4. Query Formation

- Goal: search local, Hivemind, and external sources appropriately.
- Data: classification fields.
- Confusion: one query string does not fit path search, metadata search, and web
  search.
- Context risk: low before results arrive.
- Interface need: structured query object or server-side per-source query
  rewriting.
- DeepSeek note: source-specific query adaptation should not be left to prose.

### 5. Summary Ranking

- Goal: choose the best precedent from compact summaries.
- Data: summaries with family, capability, segments, public I/O, validation.
- Confusion: agent may match words like `LTX` and `audio` without checking that
  the audio path is the right shape.
- Context risk: moderate with multiple summaries.
- Interface need: computed `match_signals`, graph overlap, `structural_fit`, and
  `diff_summary`.
- DeepSeek note: good at ranking pre-scored candidates; brittle with raw rows.

### 6. Local vs External Escalation

- Goal: decide whether local/Hivemind are enough.
- Data: source-kind labels, scores, structural mismatch flags.
- Confusion: helpfulness bias may over-escalate to unsafe external sources, or
  over-prefer weak local matches.
- Context risk: medium because external search opens conversion/safety work.
- Interface need: server-computed `needs_external_fallback` and hard escalation
  criteria.
- DeepSeek note: needs hard gates.

### 7. Outline Interpretation

- Goal: understand a Python build-body outline.
- Data: assignment rows with names, class types, deps, consumers.
- Confusion: flat line order can obscure DAG structure and branch points.
- Context risk: high for large workflows.
- Interface need: topologically grouped outline with segment headers, not only
  chronological rows.
- DeepSeek note: struggles with flat DAG data; grouping is essential.

### 8. Segment Selection

- Goal: choose which segment to fetch.
- Data: segment summaries and change goal.
- Confusion: fetches too much to be thorough, or too little to understand
  boundaries.
- Context risk: very high.
- Interface need: default `max_fetch_segments: 1`; include one-hop boundary;
  fetch more only after an explicit need.
- DeepSeek note: prompt discipline is weaker than tool-enforced limits.

### 9. Neighborhood Fetch

- Goal: retrieve the exact Python source excerpt.
- Data: `fetch_workflow_segment` and neighborhood tools.
- Confusion: wrong direction/depth misses dependencies or pulls half the
  workflow.
- Context risk: high.
- Interface need: prefer named segments, include `size_hint`, `max_lines`, and
  line spans.
- DeepSeek note: weak at boundary sizing; use precomputed segments.

### 10. External Workflow Preview

- Goal: decide whether an external URL is safe enough to ingest.
- Data: URL, snippet, domain, content hints.
- Confusion: random HTML pages, Discord/CDN links, embedded JSON, weak
  provenance.
- Context risk: low at decision time; high consequence.
- Interface need: mandatory `preview_external_url` before fetch/convert.
- DeepSeek note: too trusting without enforced preview gates.

### 11. Conversion Diagnostics

- Goal: decide whether converted external Python is usable.
- Data: validation flags, warnings, model drops, widget aliases, provenance.
- Confusion: structural `ok` may hide serious warnings.
- Context risk: moderate.
- Interface need: machine-readable `trust_tier` and structured `loss_summary`.
- DeepSeek note: will rationalize warnings unless hard rules define allowed
  tiers.

### 12. Hivemind Upload Decision

- Goal: upload clean external precedents for future reuse.
- Data: trust tier, hashes, source URL, validation evidence.
- Confusion: upload something merely because it was useful once.
- Context risk: low.
- Interface need: server-side `maybe_upload_precedent`, with dedupe and dry-run
  envelope; agent reports the decision but does not make it.
- DeepSeek note: upload policy should not be agent judgement.

### 13. Implementation Brief Construction

- Goal: turn precedent + segment into an edit brief.
- Data: fetched excerpt, current graph anchors, change goal.
- Confusion: omits avoid-patterns or names precedent nodes that have no current
  graph analog.
- Context risk: moderate.
- Interface need: structured brief with `pattern_to_adapt`, line references,
  `current_graph_anchors`, `avoid_patterns`, and semantic checks.
- DeepSeek note: good at filling templates when required fields are explicit.

### 14. Implementation Handoff Consumption

- Goal: execution applies the pattern to the current graph.
- Data: current graph, `PrecedentAdaptationPlan`, Python-rendered slice
  evidence, edit tools.
- Confusion: copies precedent names verbatim or creates duplicate unattached
  nodes instead of mapping onto existing anchors.
- Context risk: highest in the pipeline.
- Interface need: explicit `anchor_bindings`, required new nodes, required
  rewires, socket evidence, and avoid-patterns.
- DeepSeek note: adequate with mapping; poor without it.

### 15. Semantic Validation Execution

- Goal: check that the candidate satisfies the actual request.
- Data: candidate graph and required semantic checks.
- Confusion: presence-only checks pass dangling nodes.
- Context risk: low.
- Interface need: connectivity-aware checks with states such as `satisfied`,
  `present_but_dangling`, and `missing`.
- DeepSeek note: should be deterministic code, not model judgement.

### 16. Semantic Validation Interpretation

- Goal: decide pass/retry/block from semantic results.
- Data: per-check severity and action.
- Confusion: agent downgrades a hard miss or over-blocks a soft warning.
- Context risk: low.
- Interface need: validator assigns `severity` and `action`; agent must not
  override.
- DeepSeek note: good at following explicit action fields.

### 17. Empty Search Results

- Goal: stop cleanly when no precedent exists.
- Data: exhausted local/Hivemind/external results.
- Confusion: hallucinated precedent or infinite query retries.
- Context risk: low, but hallucination risk high.
- Interface need: `precedent_status: none_found`, `max_retries`, and explicit
  fallback mode.
- DeepSeek note: forced terminal states are critical.

### 18. Ambiguous Precedents

- Goal: handle two plausible but different patterns.
- Data: competing summaries and scores.
- Confusion: arbitrary pick or merged pattern that no real workflow uses.
- Context risk: high if both are fetched in detail.
- Interface need: computed `tiebreak_signals`; if pattern categories differ,
  ask the user or carry both as alternatives without merging.
- DeepSeek note: will confidently choose unless forced into tiebreak rules.

### 19. Graph Anchor Identification

- Goal: identify where the precedent pattern attaches to the current graph.
- Data: current graph topology, node definitions, precedent segment.
- Confusion: class-type match ignores socket version differences.
- Context risk: high.
- Interface need: suggested anchors with socket-level compatibility:
  current node id, class, target input, socket exists, socket type.
- DeepSeek note: socket reasoning should be a system function.

### 20. Clarification Loop

- Goal: ask the user when "add audio" could mean different workflows.
- Data: competing precedents with different pattern categories.
- Confusion: proceeds with lipsync when user meant background music, or vice
  versa.
- Context risk: moderate because the pipeline has momentum.
- Interface need: `needs_clarification` when top precedents have different
  categories or the request lacks a critical disambiguator.
- DeepSeek note: will detect ambiguity if explicitly prompted; rarely volunteers
  it unasked.

## Design Implications

- Precompute match signals, structural fit, trust tier, anchor mappings, socket
  compatibility, and validation actions outside the model.
- Make external ingestion a two-phase gate: preview before fetch, analyze before
  convert, validate before use, dry-run before upload.
- Keep research in a "summary first, fetch one segment, hand exact excerpt"
  rhythm. Reject accidental full-workflow dumps unless explicitly requested.
- Treat the implementation brief as a schema, not a paragraph.
- Give DeepSeek agents rigid output contracts and terminal states; do not rely
  on them to infer safety policy from prose.
