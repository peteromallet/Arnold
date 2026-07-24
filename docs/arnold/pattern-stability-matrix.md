# Pattern Stability Matrix

This page records the stability classification for every public symbol exported
by `arnold.patterns`.  The same markers are exposed programmatically in
`arnold.patterns.PUBLIC_EXPORTS`, `arnold.patterns.PROVISIONAL_EXPORTS`, and
`arnold.patterns.INTERNAL_EXPORTS`.

## Stability Definitions

- **stable** — safe to rely on in shipped packages and external tooling. The
  symbol's name, signature, and lowering semantics are covered by the canonical
  fixture matrix.
- **provisional** — available for early adopters, but the signature or lowering
  may still change until the canonical fixture matrix validates the behavior.
- **internal** — not part of the public authoring contract. May change without
  notice.

## Base Constructors (stable)

| symbol | returns | notes |
|---|---|---|
| `agent` | `arnold.workflow.Step` | explicit agent node with durable prompt ref |
| `external_call` | `arnold.workflow.Step` | explicit external-call node with durable endpoint ref |
| `merge` | `arnold.workflow.Step` | explicit merge node with optional reducer ref |
| `subpipeline` | `arnold.workflow.Step` | explicit subpipeline node referencing a manifest by hash |

## Control Constructors

| symbol | stability | returns | notes |
|---|---|---|---|
| `branch` | stable | `arnold.workflow.Step` | conditional branch node |
| `fanout` | stable | `arnold.workflow.Step` | fanout node |
| `loop` | stable | `arnold.workflow.Step` | bounded loop node |
| `human_gate` | stable | `arnold.workflow.Step` | suspension/gate node lowered to capability routes |
| `panel` | provisional | `arnold.patterns.PatternBlock` | multi-participant block; lowering still under fixture validation |
| `retry` | provisional | `arnold.workflow.Step` | retry node; policy lowering still under fixture validation |

## Review Constructors

| symbol | stability | returns | notes |
|---|---|---|---|
| `critique` | provisional | `arnold.patterns.PatternBlock` | critique block |
| `review` | provisional | `arnold.patterns.PatternBlock` | review block |
| `revise` | provisional | `arnold.patterns.PatternBlock` | revise block |
| `tournament` | provisional | `arnold.patterns.PatternBlock` | tournament block with bounded tiebreaker |

## Internal Symbols

| symbol | notes |
|---|---|
| `PatternBlock` | composite carrier for advanced callers; not a public authoring primitive |

## Rules of Use

- Stable constructors may be used directly in `build_pipeline()` return values.
- Provisional constructors may be used, but their output must be expanded or
  composed into an `arnold.workflow.Pipeline` before returning from
  `build_pipeline()`.
- Internal symbols must not cross into package source contracts.
