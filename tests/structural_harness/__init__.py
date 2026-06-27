"""VibeComfy deterministic structural contract harness.

This package provides the Sisypy-compatible adapter, runner, builders, scenarios,
and briefs for deterministic structural contract testing.

These tests are not live agentic tests. The true live-agentic lane is reserved
for ``tests.live_agentic_harness`` and must use real dispatchers with production-like
tools.

Layout:
  adapter.py   — VibeComfyProjectAdapter (extends FakeProjectAdapter)
  runner.py    — Scenario runner: load scenarios, dispatch actors, freeze evidence
  actors.py    — Structural evidence builders for scenario families
  actors_m4/   — M4 recovery evidence builders
  actors_m5/   — M5 runtime/readiness evidence builders
  scenarios/   — Scenario YAML files (one per user ask)
  briefs/      — User-shaped markdown briefs
  README.md    — Structural contract harness documentation
"""

from __future__ import annotations
