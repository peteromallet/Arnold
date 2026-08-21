# Plan — megado run: custom-agent implementation (R1–R3)

Author: GPT-5.6 Sol (planner), read-only. Base: `744a417198`; foundation `b7c682798e`; run contract `eac81e57d2`.

## Execution tasklist (11)

1. **Preserve and prove R1 foundation** — keep `agentbox/agents/arnold.md`, installer, `arnold` CLI untouched except R2 extension. *Acceptance:* packaged install succeeds, `~/.bun/bin/agent list` discovers `arnold`, `agent run arnold` probe completes, no alternate dispatch command.
2. **Extend `install-omp-agent` with minimal identity overrides** — add only `--name` and `--description` to `agentbox/cli.py`; positional `name` stays the source template. *Acceptance:* `<target>/<name>.md` atomically written with matching frontmatter and unchanged prompt body; unsafe names/malformed templates/unknown sources fail cleanly.
3. **Lock canonical-persona parity** — test parsing `agentbox/agents/arnold.md` body vs `AgentBoxOperatorProfile.system_prompt()` byte-for-byte; rule: persona edits change both surfaces + bump `AGENTBOX_OPERATOR_PROMPT_VERSION`. *Acceptance:* drift fails; current v1 passes exactly.
4. **Open one external-profile seam** — `ResidentConfig.profile` from two-value literal to validated string; remove hard-coded `choices` in Discord CLI; built-ins `megaplan`/`agentbox_operator` keep meanings. *Acceptance:* built-in tests green; arbitrary specs reach loader without changing defaults/env names.
5. **Load and validate repo-relative profiles** — `resident/cli.py` `_resident_profile` receives project root, recognizes `path.py:Class`, confines file beneath root, deterministic import, requires `AgentBoxOperatorProfile` subclass, constructs with existing store/authorizer/config/confirmation_manager; built-ins on current paths. *Acceptance:* valid external subclass runs through Discord dry-run; malformed specs/absolute paths/missing files/import failures/wrong types give concise diagnostics before network startup.
6. **Create five hand-editable templates** — `agentbox/templates/resident/{agent.md,resident_profile.py,resident.env.example,run-resident,resident.service}`; generated profile subclasses `AgentBoxOperatorProfile`, system prompt from project agent markdown, inherits tool registry. *Acceptance:* rendering yields exactly the five files; no hidden manifest; markdown sole identity surface.
7. **Implement `agentbox new-resident <name> --repo <path>`** — validate portable slug + existing repo dir; render five files; executable mode on `run-resident`; preflight destinations (clean refusal on collision). *Acceptance:* one command creates complete scaffold; rerun against collisions changes nothing.
8. **Ship templates in built artifacts** — `pyproject.toml` artifacts for `agentbox/templates/resident/*`; strengthen `tests/agentbox/test_package_smoke.py` for installed distribution. *Acceptance:* clean wheel/sdist install contains templates; installed `new-resident` generates scaffold.
9. **Cover behavior and rejection paths** — expand `tests/agentbox/test_cli.py` (overrides, validation, atomic/non-overwrite, exec mode, tree contents) and `tests/agentbox/test_resident_profile.py` (built-ins, external loading/injection, markdown prompt, dry-run, rejection classes). *Acceptance:* targeted suites pass; agent-file `tools` don't alter Discord profile's tool catalog.
10. **Document** — `docs/custom-resident-agents.md`: PATH caveat, R1 flow, R2 markdown editing, agent-tools vs Discord-tools, persona discipline, generator output, env setup, dry-run, systemd, omp auth, discovery precedence, portal steps. *Acceptance:* user can scaffold/configure a second-repo resident from the doc alone.
11. **End-to-end acceptance + evidence** — frozen targeted tests, import smoke, wheel smoke, list/run probe, generated-repo import, launcher dry-run; inspect delta for forbidden changes. *Acceptance:* every R1–R3 criterion maps to evidence; worktree green; no live Discord call; no `main` mutation.

## Areas to explore (Phase 2)

1. **Resident selection/import lifecycle** — `resident/cli.py` (`_register_resident_subcommands`, `_resident_config`, `_resident_discord`, `_resident_profile`) + `resident/config.py`: authoritative project root, import timing vs token/network validation, loader-error diagnostics.
2. **Profile construction contract** — `agentbox/resident_profile.py` (`AgentBoxOperatorProfile`, `__post_init__`, `system_prompt`, `tools`) + `resident/runtime.py`: required methods, inherited tool registration, store/authorizer/confirmation-manager injection contract.
3. **Launcher/env/systemd conventions** — `agentbox/systemd/agentbox-discord-resident.service`, `agentbox/config.py`, resident CLI entry points, bootstrap/package-smoke tests: smallest portable launcher, env loading, cwd, store root, exec permissions, token handling.
4. **Generator mechanics/packaging** — `agentbox/cli.py`, `pyproject.toml`, `tests/agentbox/test_package_smoke.py`: diagnostic/JSON conventions, atomic-write helpers, artifact inclusion, installed-wheel resource lookup.
5. **omp project-agent behavior** — `/Users/peteromalley/Documents/oh-my-pi/packages/coding-agent/src/task/discovery.ts`, `src/task/index.ts`, `test/task/discovery.test.ts`: `.omp/agents` precedence, exact-name collision, frontmatter/name grammar, fresh-repo invocation.
6. **Documentation boundaries** — `docs/agentbox-resident-boundary.md` + nearby docs: reuse terminology; don't import transport internals.

## Open questions (explorers must close)
- Precise safe-name grammar shared by omp filenames and systemd units.
- Whether current dry-run constructs enough runtime state to validate an external class fully.
- Installed-wheel resource API that works without source-tree assumptions.

## North Star check
Advances the named-agent platform through one runtime and one narrowly defined profile-loading seam; preserves byte parity with the live Discord prompt; markdown stays the declarative identity surface; five-file scaffold readable and hand-editable; only the two installer flags authorized by the goal; no re-architecture, flag soup, omp fork changes, compat renames, Discord tool-catalog changes, purge work, portal automation, or `main` mutation.
