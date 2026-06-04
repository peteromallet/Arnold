# Agent-edit chat panel — visual spec & wireframes

> Produced by the Opus visual lens (2026-06-04), companion to
> `agent-edit-chat-interface.md`. Panel = right sidebar ~400px wide.
> Frame = Header (fixed top) / Thread (scroll, newest at bottom) / Composer (fixed bottom).

## Header (always present)
```
┌────────────────────────────────────────────┐
│ ✨ Agent  ●green     ＋▾       ⚙        ✕   │  title · status dot · New(▾=history) · Settings · Close
└────────────────────────────────────────────┘
   ● green = provider ready · ● grey = not configured · ● amber = working
```
`＋` is a split-button: tap = new conversation; tap `▾` caret = History dropdown
(scoped to the current workflow), no drawer, no main-window clutter:
```
   ┌──────────────────────────────┐
   │ Conversations (this graph)   │
   │ • Now · 6 turns      (active)│
   │ • 11:02 · "make it 30"       │
   │ • Yesterday · 3 turns        │
   │ ＋ New conversation          │
   └──────────────────────────────┘
```

## (a) Unconfigured — no provider/key
Warning is a centered card IN the thread area (it is the empty state when
unconfigured), gear ⚙ pulses, composer visible but DISABLED (blocks send):
```
│        ⚠  Not connected                     │
│   Choose a provider and add a key to start   │
│        [  Open Settings  ]                   │
├──────────────────────────────────────────── │
│ │ Connect a provider to start… (locked) │    │
│                                  Send ▷(off) │
```

## (b) Empty but configured
```
│              ✨                              │
│      Edit this graph by chatting.            │
│   Try:  › "set steps to 28"                  │  ← tappable, prefill composer
│         › "swap the sampler to euler"        │
│         › "add a second KSampler pass"       │
│   Editing: graph "untitled" · 14 nodes       │  ← dim baseline context
│ │ Message the agent…                 │ Send ▷│
```

## (c) Active — mid-thread (collapsed + one expanded)
```
│ ░░░░░░░░░░░░░░░ make it cinematic            │  USER: right, filled accent
│ ✨ Updated the prompt and set CFG to 6.5.    │  AGENT: left, light surface
│    Applied ✓ · Show details ▸                │
│ ░░░░░░░░░░░░░░░ now 30 steps                  │  USER (follow-up; memory)
│ ✨ Set KSampler.steps to 30.                 │  AGENT, expanded:
│    Show details ▾                            │
│    ╭ steps: 28 → 30  (ksampler)         ╮    │  diff row
│    │ search ✓ · batch(1) ✓ · gate ✓     │    │  machinery (dim/mono)
│    ╰ Audit ⤓                            ╯    │
│    [ Apply ]  [ Reject ]                     │  inline, LIVE (latest only)
│ │ Message the agent…        │ ↩ Undo  Send ▷ │  thread-level Undo iff stack non-empty
```

## (d) Working — turn in progress
```
│ ░░░░░░░░░ add an upscale pass                │
│ ✨ Working…                            ◐     │  live spinner; amber header dot
│    › searching nodes                         │  streamed turn-feed lines,
│    › planning batch (2 statements)           │  auto-collapse into Show-details on resolve
│    › applying…                    [ Stop ]   │  Stop = abort POST → "cancelled"
│ │ (locked while working)              │      │  composer disabled during turn
```

## (e) Clarify — agent asked a question
```
│ ░░░░░░░ make it bigger                        │
│ ✨ Bigger which way — resolution, or the      │  question bubble; trailing "?"
│    latent batch size? · Show details ▸        │  (no Apply/Reject unless it also edited)
│  Answering ✨'s question                      │  composer label flips
│ │ resolution                       ⌷ │ Send ▷ │  input accent left-border
```

## (f) Candidate review — latest live, older superseded
```
│ ✨ Set steps to 28.  · Show details ▸         │  OLDER proposing bubble
│    [ Apply (superseded) ]  [ Reject ]         │  Apply DISABLED, dim
│        ⓘ "A newer change replaced this"       │  tooltip on hover
│ ░░░░░░░ actually use 35                        │
│ ✨ Set steps to 35.  · Show details ▸         │  LATEST proposing bubble
│    [ Apply ]  [ Reject ]                      │  Apply LIVE (only the latest)
│        ⓘ "Queue blocked: lower 1 intent…"     │  if blocked: Apply dim + 1st blocker msg
```

## (g) Failure — with re-baseline recovery
```
│ ░░░░░░░ change the seed                        │
│ ⚠ I couldn't apply that — the canvas changed   │  failure bubble, amber left-border;
│   since I last looked.                         │  text = user_facing_message
│   [ ↻ Re-sync & retry ]                        │  re-baseline recovery (StaleState only)
│   Show details ▾                               │
│    ╭ kind: StaleStateMismatch                ╮ │  kind/stage/raw under details
│    ╰ stage: gate · Audit ⤓                   ╯ │
```

## (i) Settings popover — from the gear
```
│                  ┌──────────────────────────┐│  anchored under ⚙
│                  │ Settings            ✕    ││
│                  │ Route   [deepseek-v4 ▾]  ││
│                  │ Model   [deepseek-v4-pro]││
│                  │ API key [••••••••••]     ││
│                  │ ● provider ready          ││  live route-resolution line
│                  │ [ Test ]      [ Save ]    ││
│                  │ ▸ Developer (debug)       ││  session/turn hashes, raw JSON here
│                  └──────────────────────────┘│
```

## Visual hierarchy (keep it light)
- **Zero-tap (always visible):** header; the thread; each agent reply's one-line
  summary; inline Apply/Reject on the latest candidate; the composer; thread-level
  Undo (only when undo stack non-empty).
- **One-tap:** "Show details ▸" (diff rows + search/batch/gate + Audit), expands
  inline-down with the bubble top anchored; Settings (⚙); History (＋ caret).
- **Two-tap / debug:** session/turn/baseline hashes, raw gate booleans, raw
  response JSON — behind Settings ▸ Developer. Never top-level.
- **Bubble cues:** USER right/filled-accent; AGENT left/neutral (summary medium
  weight, machinery dim mono); FAILURE/SYSTEM left + amber 3px left-border + ⚠;
  WORKING animated ◐ amber; CLARIFY agent bubble + "?" and composer gains accent
  border + "Answering…" label.
- **Collapsed vs expanded:** collapsed ≈ 2 lines (summary + Apply/Reject + any
  recovery); expanded adds a bordered nested card, same width, indented; chevron ▸→▾.

## Visual lock-in defaults
History = ＋ split-button → dropdown, lazy. Composer when unconfigured = shown
disabled. Working lines = stream live then auto-collapse into Show-details.
Superseded Apply = disabled in place + "(superseded)" + tooltip. Undo = composer
row, left of Send, only when stack non-empty. Blocked Apply = dim + ⓘ first-blocker
tooltip. Clarify cue = composer label + accent border. Example prompts = tappable
(prefill).
