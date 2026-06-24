# M2: Render Boundary Hardening

## Outcome

Make normal chat bubbles and expanded details raw-data-blind. `panel_thread.js`
and related render paths should consume only `TranscriptMessage` and
`ResponseDetail` selectors, while audit/debug internals remain behind explicit
debug affordances.

## Scope

In:

- Make collapsed chat rendering consume only safe transcript messages.
- Make expanded bubble/detail rendering consume only safe response details and
  explicit audit affordance metadata.
- Remove or isolate normal render reads of `panel.state.turns`,
  `canonical_activity.details`, raw `batch_turns`, diagnostics, paths, budgets,
  exit modes, and provider payloads.
- Add hostile sentinel browser tests for collapsed chat, expanded details, and
  below-thread/history mount.
- Preserve stage display, candidate preview/apply, apply/reject, clarify,
  failure, respond, and research-route behavior.

Out:

- Changing visual design.
- Rewriting status poller/composer/candidate ownership.
- Backend storage migrations.

## Locked Decisions

- Renderers do not inspect raw execution events or audit payloads.
- Audit/download/report paths are allowed only through explicit debug controls.
- `vibecomfy_roundtrip.js` changes must be wiring-only unless directly required
  to route safe selector output into renderers.

## Done Criteria

- Sentinel internal strings cannot appear in collapsed chat or expanded normal
  details.
- Explicit audit/debug download behavior remains available.
- Browser tests cover normal chat, details, rehydrate, candidate actions, and
  status display.

## Touchpoints

- `vibecomfy/comfy_nodes/web/panel_thread.js`
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- `tests/browser/roundtrip_smoke.test.mjs`
- `tests/browser/panel_thread_rating.test.mjs`
- new or expanded browser sentinel test

## Validation

```bash
node --test tests/browser/roundtrip_smoke.test.mjs
node --test tests/browser/panel_thread_rating.test.mjs
node --test tests/browser/*.mjs
```
