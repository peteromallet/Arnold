---
type: initiative-note
initiative: custody-control-plane
target_milestone: m9-rebuildable-projections-and-liveness
created_at: '2026-07-14T16:34:30+00:00'
---

# Discord attention-overlay status obligation

The resident Discord `Currently running` epics/chains filter omitted the live
Custody chain when the cloud projector transiently classified the session as
`attention`, even though `progress.display_state` was `executing` and a live
runner was present. Attention is an operator overlay and must not replace or
hide active execution truth.

The canonical M9 brief now requires the Discord projection to keep live or
actively repairing attention-classified sessions in the active listing, label
them from `progress.display_state` (then `progress.plan_state` only when absent,
with active execute rendered as `executing`), and expose the attention reason.
Its blocking regression obligation has three cases: active
executing-plus-attention remains listed; non-active attention remains on the
attention surface; and normal running entries are unchanged.

The executing Custody chain was in the immutable M5 execute phase when this
note was written, so its workspace and snapshotted/current milestone scope were
not edited. Before M9 admission, reconcile this canonical M9 brief and note
through the chain's normal exact-version execution-binding/handoff process and
record the focused Discord regression suite as blocking evidence. Do not infer
coverage from M9's broad resident/Discord or cross-view-agreement language.
