---
type: anchor
anchor_type: north_star
slug: boundary-turn-end-to-end
title: "North Star: BoundaryTurn End To End"
---

# North Star: BoundaryTurn End To End

Build BoundaryTurn as the clean, reusable boundary between model-authored draft
outputs and harness-owned canonical artifacts.

The end state is:

- Models edit drafts.
- Validators inspect expected drafts or explicit legacy recovery payloads.
- The harness alone promotes canonical artifacts, state, history, receipts, and
  route proposals.
- Worker parsing, model-seam recovery, phase validators, transition policy, and
  stage-specific semantics remain in their proper layers.
- Megaplan gets cleaner boundaries without losing any behavior.
- Other Arnold pipeline authors get a standard draft/capture/validate/promote
  recipe without importing Megaplan registries or artifact names.

This epic must not flatten Megaplan stages into a generic engine. It should make
the mechanics elegant while preserving the meaning of each stage.
