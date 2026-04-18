# Overlay pointer-events cleanup

Follow-up to `a5909c871` (`fix(overlay): neutralise the legacy body-pointer-events synchronizer to stop racing with Base UI`). The fix landed the minimal behavioral change. This plan removes the dead code and vestigial defenses around it.

## Context (read first)

Before the fix: two systems managed `document.body.style.pointerEvents` — our overlay-stack helper and Base UI's Dialog primitive. They raced during close; body sometimes stayed locked (all clicks disabled) or clicks inside popups fell through (popup inherited `pointer-events: none` from locked body). Media Lightbox survived because its children each set `pointer-events: auto` explicitly; Settings Modal and other vanilla Dialogs did not.

After the fix: the legacy overlay-stack synchronizer is a no-op. Base UI alone owns body pointer-events. Everything below is cleanup — none of it is load-bearing for correctness.

## Master checklist (quick wins first)

- [ ] **T1** — Delete the legacy body-pointer-events synchronizer and its call sites (zero-risk dead code removal)
- [ ] **T2** — Remove defensive `pointer-events-auto` overrides from Media Lightbox components, OR leave them with a load-bearing comment
- [ ] **T3** — Unbreak `overlayStack.test.ts` (3 pre-existing failures — updates required regardless of this cleanup)
- [ ] **T4** — Dedupe `handleOverlayPointerUp` + `handleOverlayClick` close paths in `useLightboxShellInteractionHandlers.ts`
- [ ] **T5** — Audit: grep for any other code still reading/writing `document.body.style.pointerEvents` directly
- [ ] **T6** — Add a one-line docstring on `pushOverlay`/`popOverlay` clarifying the stack does NOT manage body pointer-events (so future contributors don't re-introduce the bug)

## T1: Delete the Legacy Body-Pointer-Events Synchronizer

**Files:**
- `src/shared/state/overlayStack.ts` — remove the no-op function (lines ~131–145), remove all 3 call sites in `pushOverlay`, `updateOverlay`, `popOverlay`, remove the `document.body.style.pointerEvents = ''` line from `__resetOverlayStackForTests`.

**Why:** Dead code. The no-op was a tombstone to minimize diff during the hot-fix; it has no purpose now. Keeping it invites someone to "un-neuter" it and reintroduce the race.

**Verification:** `npx vitest run src/shared/state/overlayStack.test.ts` still passes (after T3), `npx tsc --noEmit` clean.

## T2: Media Lightbox `pointer-events-auto` audit

**Files to audit (found via grep):**
- `src/domains/media-lightbox/components/MediaDisplayWithCanvas.tsx:325,386`
- `src/domains/media-lightbox/components/RepositionOverlay.tsx:49,124`
- `src/domains/media-lightbox/components/WorkflowControlsBar.tsx:43`
- `src/domains/media-lightbox/components/SegmentSlotFormView.tsx:235,247`
- `src/domains/media-lightbox/components/layouts/LightboxLayout.tsx:406`

**Decision per site:** for each `pointer-events-auto`, determine if it's still load-bearing:
- If the element is inside a Portal/Dialog/Popover that itself has explicit `pointer-events: auto` (Base UI sets this), the override is vestigial → **delete**.
- If the element is a child of a container that sets `pointer-events: none` for a reason (e.g., `MediaDisplayWithCanvas.tsx:325` toggles between none/auto for inpaint mode — that's legit), keep it and add a one-line comment explaining why.

**Why:** Vestigial overrides lie about the code's needs. Future readers will assume they're load-bearing and preserve them during refactors, or — worse — add more of them "defensively" elsewhere.

**Risk:** Low. If an override was actually load-bearing and we miss it, the regression is visible immediately (a button doesn't respond to clicks).

**Verification:** Open the Media Lightbox, click every interactive element (edit buttons, navigation arrows, reposition handles, canvas, inpaint controls, workflow bar). If everything still responds, the delete was safe.

## T3: Fix `overlayStack.test.ts`

**File:** `src/shared/state/overlayStack.test.ts`

**Current state:** 3 failures (pre-existing, unrelated to the fix). Failures are because tests call `pushOverlay` without `elements`, but `isOverlayActuallyOpen` returns false for empty elements, so `isTopmostModalOverlay` returns false when the test expects true.

**Fix:** port test updates from commit `1b9045cc5` (on a sibling branch that landed the same fix independently). That commit adds a `createOpenElement()` helper and threads `elements:` through each `pushOverlay` call, then drops the now-moot `document.body.style.pointerEvents` assertions.

**Why:** Tests will keep failing on main regardless of this cleanup — fix them now while the context is loaded.

**Verification:** `npx vitest run src/shared/state/overlayStack.test.ts` passes 4/4.

## T4: Dedupe lightbox close paths

**File:** `src/domains/media-lightbox/hooks/useLightboxShellInteractionHandlers.ts`

**Current state:** `handleOverlayPointerUp` (line 44–65) and `handleOverlayClick` (line 67–85) implement the **same** close-if-click-started-and-ended-on-overlay logic. They both fire for a normal click (pointerup fires first, then click). The `pointerDownTargetRef.current = null` reset happens at the end of each, so the second handler sees null and doesn't double-close — but this is fragile and depends on event-order invariants.

**Fix options:**
- **(a) Keep only `handleOverlayPointerUp`, delete `handleOverlayClick`.** Pointer events are the modern standard and fire before click. Simpler.
- **(b) Keep only `handleOverlayClick`, delete `handleOverlayPointerUp`.** `click` is the canonical dismiss event; `pointerup` adds nothing.

**Recommendation:** (a). Modern React codebases gravitate to pointer events. Touch/pen/mouse all synthesize pointer events consistently.

**Risk:** Medium. These handlers have existed through several bug-fix commits (`272346bc6`, `e3da6fa14`). Removing one may re-expose an edge case someone handled by adding the other. Before deleting, read those two commits and confirm the reason the second handler was added.

**Verification:** Open lightbox, click backdrop on desktop (mouse), click backdrop on mobile (touch), press X close button — all still close cleanly.

## T5: Grep for other `body.style.pointerEvents` writers

```
rg "body\.style\.pointerEvents" src/
rg "document\.body\.style.*pointer" src/
```

**Why:** If anything else in the codebase writes body pointer-events directly, it'll start fighting Base UI now that the overlay stack is out of the picture. Find and remove any such code (or document why it's necessary).

**Risk:** Low. Expected to find none. If found, they're almost certainly bugs.

## T6: Defensive docstring on overlay stack API

**File:** `src/shared/state/overlayStack.ts`

Add a one-line comment on `pushOverlay` / `popOverlay` / `updateOverlay`:

```ts
/**
 * Registers an overlay in the z-order stack.
 * Does NOT manage document.body.style.pointerEvents — that is Base UI's responsibility.
 * See commit a5909c871 for the race this avoids.
 */
```

**Why:** Prevents re-introduction of the bug. Someone will notice "hey, we have an overlay stack but we're not locking body — surely that's a bug?" and add it back. The comment heads that off.

**Risk:** Zero.

## Not in scope

- Rewriting the overlay stack's `isOverlayActuallyOpen` DOM-reading strategy. It's used for focus restoration and z-order only now, where racey reads are harmless. Leave it.
- Migrating away from Base UI. Too far out.
- Tests for the Settings Modal close → click-outside flow. The behavior is now Base UI's, and Base UI has its own tests. Adding a component-level regression test would require real browser (Playwright), which is a much larger commitment.

## Suggested sequencing

T1, T3, T5, T6 are ~15 minutes each, zero-to-low risk — bundle them in one PR.
T2 is an audit with per-site judgment calls — separate PR, easier to review.
T4 is the riskiest — separate PR with its own test plan.
