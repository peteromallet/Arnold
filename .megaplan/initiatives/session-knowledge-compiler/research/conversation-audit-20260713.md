# Authoritative Conversation Audit — 2026-07-13

## Scope and method

The product definition was reconstructed from resident conversation
`rconv_85a1c2bfd5f1` using only the constrained resident context/search CLI and
always passing that conversation ID. Searches were repeated for the product
terms `100,000`, `session knowledge`, `paper-cut`, `summarizer agent`,
`immutable`, `promotion`, `backlog`, `DeepSeek`, `observed`, `transcript/tool`,
and related category terms. The bounded conversation page at cursor 175 was
also read to preserve ordering and the governing user request.

Resident search intentionally bounds long message excerpts. Decisions below
are included only where they were confirmed by the retrieved discussion, by
term-specific searches against the same authoritative message, or by the
current governing request. The resident's immutable Discord launch provenance
is inherited by the harness environment; this artifact does not construct or
replace it.

## Concise user request and product intent

Build a durable session knowledge compiler for every managed agent/session. It
should compile each roughly 100,000-token increment and every terminal session
range without harming the primary run; preserve immutable evidence-linked
checkpoints plus rolling/final synthesis; keep activity, reusable knowledge,
paper-cut observations, and improvement candidates separate; retain claim kind
and primary transcript/tool evidence; support correction, scoped search, and
cautious version/commit-aware promotion; and consolidate recurring paper cuts
into prioritized backlog work without deleting source observations. Operation
is automatic with lightweight agent controls, and bounded extraction uses the
canonical direct DeepSeek Pro route used by partnered-5.

## Concise factual summary of this conversation/session

The authoritative conversation record shows four product-definition turns:
the user proposed incremental per-subagent summarization
(`msg_af16e8600ccc`), added a paper-cuts ledger (`msg_d406fc21f99b`), clarified
the activity/knowledge/UX/backlog distinction (`msg_89cc57c1fa72`), and asked
for a Megaplan using partnered-5's direct DeepSeek Pro semantics
(`msg_534f83393205`). The corresponding assistant turns
`msg_63610d4bb911`, `msg_e7b43d46d642`, and `msg_5d47dbb7a366` developed the
locked design captured below.

The delegated operator used repeated constrained searches against this same
conversation, created the canonical five-milestone
`session-knowledge-compiler` initiative, authored its North Star,
conversation audit, prep record, five self-contained briefs, and chain, and
verified persisted `partnered-5/full`, default-depth,
`deepseek_provider: direct` routing. Chain `chain-c256f171485f` initialized M1
as plan `m1-durable-capture-cursors-20260713-2045` at
2026-07-13T20:45:09Z. The authoritative resident completion record
`msg_3e70b98cfb87` confirms the prepared assets, search verification, chain
identifier, initialization time, and direct-provider configuration. It does
not claim the product was implemented. A control-plane read at
2026-07-13T21:07:18Z found the plan still `initialized`; its `prep` worker was
dead/stale with no lock, so no milestone or implementation had completed.

## Relevant discussion sequence

| UTC timestamp | Message | Direction | Contribution |
|---|---|---|---|
| 2026-07-13T20:21:49.798664Z | `msg_af16e8600ccc` | inbound | Asked for per-subagent structured summarization at each roughly 100,000-token increment, updating a durable session document. |
| 2026-07-13T20:22:26.053126Z | `msg_63610d4bb911` | outbound | Defined the product as a durable session knowledge compiler; added incremental and terminal triggers, optional idle policy, durable offsets/idempotency, immutable checkpoints, rolling/final synthesis, evidence/claim distinctions, cautious promotion, and harmless asynchronous failure. |
| 2026-07-13T20:23:47.747534Z | `msg_d406fc21f99b` | inbound | Added a paper-cuts capability for struggles/confusion that should feed useful improvement work. |
| 2026-07-13T20:24:11.474482Z | `msg_e7b43d46d642` | outbound | Separated evidence-backed friction observations from codebase facts and improvement candidates; introduced distinct categories including discoverability, ambiguous contract, missing capability, reliability, performance/cost, and workaround evidence; linked prioritization to recurrence/impact. |
| 2026-07-13T20:28:44.550611Z | `msg_89cc57c1fa72` | inbound | Asked for the agent UX, whether reusable knowledge differs from activity, and how paper cuts overlap with an improvement backlog. |
| 2026-07-13T20:29:33.263943Z | `msg_5d47dbb7a366` | outbound | Made operation nearly invisible and defined four linked outputs: activity, reusable knowledge, paper-cut observations, and improvement candidates/backlog; kept source observations when consolidating repeated issues. |
| 2026-07-13T20:32:04.276729Z | `msg_534f83393205` | inbound | Requested reconstruction from the whole message log and conversion into Megaplan, using the same direct DeepSeek Pro semantics as partnered-5 execution. |
| 2026-07-13T20:47:58.923017Z | `msg_3e70b98cfb87` | outbound | Recorded the delegated operator's partial outcome: initiative assets were prepared, authoritative search verified the key requirements, chain `chain-c256f171485f` initialized M1, and direct partnered-5 configuration persisted. |

## Locked product decisions

- Cover every managed subagent/session through one shared compiler contract.
- Trigger on about 100,000 newly persisted tokens and terminal states;
  completed, failed, cancelled, and superseded are terminal for eligibility.
- Idle-triggered compilation is optional policy, not a default requirement.
- Process only the new persisted source range plus prior synthesis/checkpoint
  context; store durable offsets and idempotency state.
- Compiler failure is asynchronous, visible, and retryable but never changes
  the primary session result or delivery.
- Store immutable checkpoints and separate rolling and final syntheses.
- Emit separate evidence-linked activity, reusable knowledge, paper-cut
  observation, and improvement candidate records.
- Label claims as observed, performed, inferred, proposed, or unverified.
- Keep transcripts, tool events, logs, manifests, commits, and tests primary.
- Promote session knowledge cautiously with repository/version/commit
  applicability, contradiction detection, and stronger review for
  authoritative claims.
- Provide automatic operation plus lightweight agent controls:
  `record-learning`, `record-friction`, `correct-summary`,
  `search-session-knowledge`, and `propose-promotion`.
- Consolidate recurring paper cuts into deduplicated, prioritized backlog work
  without deleting or rewriting any source observation.
- Use canonical DeepSeek Pro slots through the direct DeepSeek provider. At the
  pinned runtime, the exact agent spec is
  `hermes:deepseek:deepseek-v4-pro`; Fireworks is not an accepted DeepSeek
  provider route.

## Open design questions delegated to milestones

- The canonical provider-neutral token accounting rule when exact persisted
  usage is missing or cumulative counters reset.
- Whether idle triggering should ship disabled or behind an explicit threshold
  policy after cost/noise measurement.
- The minimal stable paper-cut taxonomy and merge-key algorithm; categories
  must aid grouping without becoming a second unreviewed truth model.
- Which claims require human review versus a lower-cost automated reviewer at
  project-promotion time.
- Retention, redaction, access control, and indexing boundaries for sensitive
  transcript/tool evidence already governed by the underlying session store.

## Historical product context

The same conversation documents repeated operational confusion around managed
agent progress, terminal delivery, evidence truthfulness, and Run Authority
adherence. Those incidents motivate the product but are not silently converted
into facts in this initiative: the compiler must preserve observed/performed
distinctions and link derived records to primary evidence precisely because
status prose can otherwise become misleading.
