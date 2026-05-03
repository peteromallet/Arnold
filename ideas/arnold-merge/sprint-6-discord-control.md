# Sprint 6 — Discord control plane + Arnold gutting

**Authoritative source:** `docs/arnold-merge-design.md` (section "Sprint 6 — Discord control plane + Arnold gutting", lines ~796-810, plus the "Discord control plane" architecture section).

**Predecessor:** Sprints 4-5 ported all editorial logic into megaplan. Sprint 6 makes the Discord bot a thin client that talks to megaplan via control messages + progress events.

## Scope

- `megaplan/control.py`: control message processor. Claims pending `control_messages`, dispatches them to the right editorial handler, marks processed atomically.
- `megaplan/progress.py`: emitter publishing `progress_events` from plan phase transitions, batch completions, and gate-needed signals.
- **Arnold gutting (work happens in arnold-source repo):**
  - `agent_kit/resident.py` keeps Discord I/O, message bursts, status edits, voice transcription.
  - **All editorial calls** in Arnold replaced with `megaplan.editorial.*` imports.
  - Bot polls `control_messages` (or subscribes via Supabase realtime) and subscribes to `progress_events`.
  - Arnold's Discord-specific tables stay Arnold-side: `bot_turns`, `messages.discord_message_id`, `tool_calls`, `system_logs`. These are NOT moved to megaplan.

## Reference repos

- Arnold (clone, modify, push): https://github.com/peteromallet/arnold — Sprint 6 commits to Arnold's main as well as megaplan's.

## Acceptance

- Discord user can `@arnold run sprint 2` from chat and watch live progress in the channel.
- Discord gate approval (reaction or button click) writes a `ControlMessage`; megaplan plan continues from the gate.
- `grep -r "supabase" arnold-source/agent_kit/tools/editorial*.py` returns nothing — editorial code in Arnold no longer talks to Supabase directly.
- Existing Discord conversations on `shaping`-state epics work end-to-end without regression.

## Out of scope

- Anything not listed. Hardening / migration tooling is Sprint 7.

## Robustness

`standard` — cross-repo refactor + live Discord behavior + control-message claim semantics need critique.
