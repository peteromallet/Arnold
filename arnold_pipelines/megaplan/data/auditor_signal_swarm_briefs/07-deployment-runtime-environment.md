You are a DeepSeek subagent in a research swarm. Work read-only.

Goal: enumerate deployment/runtime signals that should appear in the 6-hour check: host vs container wrapper drift, source checkout sync_dirty, dirty editable install, running process start time vs wrapper mtime, auth/provider problems, tmux/session health, docker/container health, disk/resource constraints, Python path/import drift, CLI availability, and feature flags.

Inspect:
- arnold_pipelines/megaplan/cloud/wrappers/*
- arnold_pipelines/megaplan/cloud/systemd/*
- docs/hetzner-watchdog-meta-loop.md
- cloud host/container read-only status commands

Return ranked signals with evidence commands, expected report fields, and false-positive guards. Include which signals are host-only, container-only, or both.
