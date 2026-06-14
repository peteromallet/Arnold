First read `FOUNDATION_PREAMBLE.md` (shared context + output rules). Obey it.

## YOUR SUBSYSTEM: observability & emission — phase_result, receipts, history, events, status/doctor/introspect

The brief's hazard 2: the emission surface (`phase_result.json` + receipts + history + events) is
load-bearing — `status`/`chain`/cloud/`introspect`/`doctor` consume it — and the executor emits
NONE of it today. The fix is "one shared post-step emission hook." Assess whether the emission/
observability foundation is coherent enough to unify behind one hook.

Investigate (cite path:line):
- Every emission point: `_emit_phase_result` (`shared.py:374`), receipts (`receipts/`, described as
  "generic audit, currently unused" — verify), history writes, event sink. WHERE are these called
  from today — handlers, CLI, auto? Are they consistent across phases or per-handler bespoke?
- The CONSUMERS: `megaplan status` (and the `{state,next_step,valid_next,active_step,progress}`
  JSON pinned as a cloud-over-SSH contract), `doctor`, `introspect`, `chain`, cloud providers.
  What exact fields does each consumer depend on? Is there a schema, or do consumers parse
  free-form dicts? How brittle is the status JSON contract (cloud version skew)?
- `receipts/` "currently unused": is it dead code, half-built, or wired-but-dormant? If the brief
  plans to make it load-bearing via the emission hook, is the receipts schema actually sound?
- Events: is there an event system, who emits, who consumes, is it reliable or fire-and-forget?

Key question: is observability a coherent layer that can be cleanly funneled through one emission
hook, or a scattering of bespoke per-handler emissions with implicit, unversioned contracts that
consumers parse by hope? Find the consumer contracts that will silently break when emission moves,
and assess whether `receipts/` being "unused" is a hidden trap (dead vs dormant-load-bearing).
