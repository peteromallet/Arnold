# Sprint 1b — Discord resident mode + robustness

Add the second adapter for each port — Discord transport, Supabase store. This proves the port abstractions hold (two impls each) and unlocks resident-mode features: coalescing, recovery, voice/image attachments, live status messages.

**Full spec is at `planning-bot-spec.md` in this repo root. Refer to it for complete data model schemas, tool signatures, and architectural details. Especially the sections: Execution Modes, Multi-Message Handling, Status Message, Idempotency and Recovery, Images.**

## Supabase
- URL: https://yhwflvadmefhkshwbfnf.supabase.co
- Service key: <redacted; use SUPABASE_SERVICE_KEY env>

## Scope

- Railway + Supabase setup; Supabase CLI for local dev
- First Supabase migration files mirroring SQLite schema from Sprint 1a; `supabase db push` workflow
- Supabase store adapter (second Store impl); same contract tests from 1a run green against both stores
- Discord transport adapter (push, second Transport impl): bot account via discord.py; on_message handler for DMs; user whitelist
- Multi-message coalescing — 10s window, burst handling (resident-only)
- Restart safety: messages persisted on receipt; recovery routine at startup + every 5min; abandoned turns marked; `external_requests` ledger table; idempotency-key generation (sha256-based); per-provider reconciliation
- Voice message support: Groq Whisper (whisper-large-v3) integration; transcription stored in messages.content; original audio in Supabase Storage
- Image attachment handling: Discord image detection; download to Supabase Storage; create images row with source='user_uploaded'; auto-assigned reference_key
- Image tools: list_images, view_image, send_image, update_image_metadata
- Live status message: loop sends status at turn start, edits after every tool call with count + last 3 tools + dynamic timestamp `<t:UNIX:R>`; set_activity tool annotates current step
- Mid-turn message handling: messages persist immediately; status message gets annotation; bot prompted with mid-turn messages

## Key New Tables

### external_requests
id, idempotency_key (unique), provider, endpoint, tool_call_id, turn_id, request_summary (json), status (pending|sent|confirmed|failed|orphaned), provider_request_id, provider_response_summary (json), attempt_count, first_attempted_at, last_attempted_at, completed_at, error_details (json)

Idempotency key: sha256(turn_id:tool_call_id:provider:endpoint:canonical_args)[:16]

### images
id, epic_id, source (agent_generated|user_uploaded), prompt, storage_url, quality, size, created_at, reference_key (unique per epic), description, caption, in_body, active (default true), discord_attachment_id

## Acceptance Criteria

- DM bot from whitelisted account → response within 30s
- DM from non-whitelisted → no response, log entry
- Every inbound message persists with unique discord_message_id
- Store port contract test suite runs green against Supabase impl unchanged from SQLite
- 5 messages in 8s → processed as single burst (triggered_by_message_ids has 5 entries)
- Kill server mid-turn, restart → triggering messages requeued under fresh turn; previous turn marked abandoned
- Voice message (mocked) → transcribed via mocked Groq, was_voice_message=true
- Image attachment (mocked) → downloaded to Storage, images row created with source=user_uploaded
- view_image returns image bytes via Anthropic vision
- send_image posts to Discord with caption
- Status message: turn starts → status sent; each tool call → edited; set_activity updates; turn completes → "Done. N tool calls."
- Mid-turn message: persists immediately; status gets annotation; bot prompted with mid-turn messages

## Tech Stack Additions
- discord.py for Discord gateway
- supabase-py for Supabase client
- groq SDK for Whisper transcription
- Supabase Storage for blob storage
