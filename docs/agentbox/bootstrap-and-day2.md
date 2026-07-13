# AgentBox Bootstrap and Day-2 Operations

This guide covers getting AgentBox running on a fresh persistent machine (Hetzner CX53-class or similar), keeping it healthy, and recovering from failure.

## Fresh-machine runbook

1. Provision the box with Ubuntu LTS, create a non-root user, and enable SSH key auth.
2. Install dependencies:
   ```bash
   sudo apt update
   sudo apt install -y git tmux python3 python3-pip python3-venv gh
   ```
3. Clone the repo and install the project:
   ```bash
   git clone <repo> /opt/arnold
   cd /opt/arnold
   pip3 install -e .
   ```
4. Run bootstrap to create `/workspace`, SSH profile stubs, and systemd unit templates:
   ```bash
   sudo mkdir -p /workspace
   sudo chown "$USER:$USER" /workspace
   agentbox bootstrap
   ```
5. Verify health:
   ```bash
   agentbox doctor
   ```
6. Install the systemd units and start services:
   ```bash
   sudo cp /workspace/systemd/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable arnold-guardian agentbox-discord-resident
   sudo systemctl start arnold-guardian agentbox-discord-resident
   ```
7. Check service status:
   ```bash
   agentbox services list
   agentbox services logs arnold-guardian
   ```

## Credentials

After bootstrap, push credentials from the operator machine:

```bash
agentbox creds push DISCORD_BOT_TOKEN
agentbox creds test
```

The Discord resident service reads `DISCORD_BOT_TOKEN` from the environment. After pushing the credential, create a systemd drop-in with the token:

```bash
sudo systemctl edit agentbox-discord-resident
# Add:
# [Service]
# Environment=DISCORD_BOT_TOKEN=<your-token>
sudo systemctl daemon-reload
agentbox services restart agentbox-discord-resident
```

## Safe Discord resident relaunch

The one canonical relaunch command is:

```bash
agentbox services restart agentbox-discord-resident
```

Each successful canonical relaunch commits a durable post-reset Discord
confirmation before the resident comes back. When the command inherited a
validated Discord request provenance, that confirmation replies to the exact
initiating message; otherwise it sends a truthful manual/non-Discord fallback
notification to the configured or most-recent resident conversation. The
outbox becomes deliverable only after the guarded supervisor reports success,
and retries use a stable Discord nonce. Inspect it with:

```bash
agentbox services reset-notifications
```

Do not substitute `pkill`, `killall`, `systemctl kill --kill-whom=all`, or tmux
cleanup. On a systemd host, the AgentBox command first reads the effective stop
policy from the installed unit and fails closed unless `KillMode` is exactly
`process` and there are no custom `ExecStop` or `ExecStopPost` hooks. With that
setting, systemd stops only the Discord resident main process.

Inside the resident container, where `systemctl` is intentionally unavailable,
the same command verifies that `megaplan-resident-discord` contains exactly one
live pane running the canonical resident command, then respawns only that pane
and waits for a replacement resident process. It refuses an absent, ambiguous,
dead, or repurposed session. It never kills the tmux session or server.
Resident-managed Codex supervisors (which are separately session-detached) and
other tmux-backed local or cloud Megaplan chains are not signaled, stopped, or
cleaned up by either backend.

After upgrading an older installation, stage and install the updated unit before
the first safe relaunch:

```bash
agentbox bootstrap
sudo install -m 0644 /workspace/systemd/agentbox-discord-resident.service \
  /etc/systemd/system/agentbox-discord-resident.service
sudo systemctl daemon-reload
systemctl show -p KillMode -p ExecStop -p ExecStopPost \
  agentbox-discord-resident.service
agentbox services restart agentbox-discord-resident
```

The inspection must show `KillMode=process` with empty `ExecStop=` and
`ExecStopPost=` values. Installing the unit and executing the live relaunch are
explicit operator actions requiring the host's normal privilege/approval path.
A relaunch does interrupt any in-flight Discord turn; send a new message after
the service reconnects if that reply was cut off. It does not interrupt durable
delegated agents or active Megaplan/cloud chains.

### Discord voice-message transcription

Audio attachments and native Discord voice messages are transcribed before the
resident turn runs. The transcript becomes the inbound user message; the
original Discord message/attachment IDs and non-secret transcription provenance
are stored separately for diagnosis. Ordinary text messages are unchanged.

Transcription uses the same OpenAI-compatible API configuration as the resident:

- `MEGAPLAN_RESIDENT_MODEL_BASE_URL` (or `OPENAI_BASE_URL`) selects the endpoint.
- `MEGAPLAN_RESIDENT_MODEL_API_KEY_ENV` selects the environment variable that
  contains the API key; it defaults to `OPENAI_API_KEY` for Codex/OpenAI.
- Codex CLI login is sufficient for text turns using the Codex runner, but the
  Audio Transcriptions API still needs the configured API key environment
  variable and an endpoint that implements `/v1/audio/transcriptions`.
- At startup, the resident logs the selected transcription model, endpoint host,
  credential environment-variable name, and whether it is present. It never logs
  the credential value. Per-message failures retain a safe stage-specific code
  such as `transcription_credential_missing` or `transcription_request_timeout`.

Safe defaults and overrides:

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_ENABLED` | `true` | Enable audio preprocessing. |
| `MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_MODEL` | `gpt-4o-mini-transcribe` | Audio transcription model. |
| `MEGAPLAN_RESIDENT_VOICE_MAX_BYTES` | `20971520` | Hard limit applied to declared, response, and streamed byte counts. |
| `MEGAPLAN_RESIDENT_VOICE_DOWNLOAD_TIMEOUT_S` | `20` | Total Discord CDN download timeout. |
| `MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_TIMEOUT_S` | `90` | Audio normalization/API timeout. |

The resident accepts MP3, MP4, MPEG, MPGA, M4A, WAV, and WebM. Discord-native
Ogg/Opus voice messages are remuxed locally to WebM/Opus before upload; audio is
never sent to an unrelated service and signed Discord CDN URLs are not persisted.

## Backup / restore

AgentBox state lives in `/workspace`. Back it up regularly:

```bash
sudo tar czf agentbox-backup-$(date +%Y%m%d).tar.gz /workspace
```

To restore on a fresh box:

1. Provision and bootstrap as above (steps 1-4).
2. Restore the archive:
   ```bash
   sudo tar xzf agentbox-backup-YYYYMMDD.tar.gz -C /
   sudo chown -R "$USER:$USER" /workspace
   ```
3. Re-push credentials (they are not included in the backup by design):
   ```bash
   agentbox creds push DISCORD_BOT_TOKEN
   ```
4. Restart services:
   ```bash
   agentbox services restart arnold-guardian
   agentbox services restart agentbox-discord-resident
   ```
5. Run `agentbox doctor` and `agentbox reconcile` to confirm the host is healthy.

## Break-glass: Discord is down or silent

1. Check overall health:
   ```bash
   agentbox doctor
   ```
2. Inspect service logs:
   ```bash
   agentbox services logs agentbox-discord-resident
   agentbox services logs arnold-guardian
   ```
3. Test the notification path directly:
   ```bash
   agentbox notify test --dm-user-id <your-user-id>
   ```
4. If the Discord resident is stuck, restart it:
   ```bash
   agentbox services restart agentbox-discord-resident
   ```
5. If all else fails, log in via plain SSH (`ssh agentbox` once the host profile is configured) and inspect `/workspace` directly.

## Day-2 commands

| Command | Purpose |
| --- | --- |
| `agentbox bootstrap` | Ensure workspace layout and systemd templates exist |
| `agentbox doctor` | Read-only health check |
| `agentbox services list` | Show service status |
| `agentbox services logs <svc>` | Tail service logs |
| `agentbox services restart agentbox-discord-resident` | Safely relaunch only the Discord resident main process after a fail-closed unit preflight |
| `agentbox services reset-notifications` | Inspect durable post-reset Discord confirmation delivery state |
| `agentbox notify test` | Send a test Discord notification |
| `agentbox reconcile` | Report host-local state mismatches |
| `agentbox version` | Show version |
