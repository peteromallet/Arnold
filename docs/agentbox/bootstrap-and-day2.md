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
sudo systemctl restart agentbox-discord-resident
```

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
| `agentbox services restart <svc>` | Restart a service |
| `agentbox notify test` | Send a test Discord notification |
| `agentbox reconcile` | Report host-local state mismatches |
| `agentbox version` | Show version |
