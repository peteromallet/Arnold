# Brief — Area 2: Profile construction contract

Explore this area in depth in `/Users/peteromalley/Documents/arnold-oracle` (worktree). Link: `.oracle/agent_goal.md`, `.oracle/northstar.md`.

Goal: R3 generates `.agentbox/resident_profile.py` as a subclass of `AgentBoxOperatorProfile`. Establish exactly what subclassing requires.

Read:
- `agentbox/resident_profile.py` — `AgentBoxOperatorProfile` dataclass: `__post_init__` (tool registration), `system_prompt()`, `load_hot_context()`, `tools()`/tool catalog exposure, `AGENTBOX_OPERATOR_PROMPT_VERSION`, `SUBAGENT_SYSTEM_PROMPT`; the `_register_default_tools` mechanism and `_registered_default_tools` flag.
- `arnold_pipelines/megaplan/resident/runtime.py` — how the runner calls the profile: `request.profile.tools()`, `system_prompt()`, `load_hot_context()`; any other methods the runtime expects (duck-typed surface).
- `arnold_pipelines/megaplan/resident/agent_loop.py` — prompt composition points that consume the profile's `system_prompt()`.
- Tests: `tests/agentbox/test_resident_profile.py`.

Report (verified facts, file:line): (1) the minimal complete surface a subclass must satisfy to run as a Discord resident (methods, signatures); (2) whether tool registration is inherited automatically or per-instance; (3) the exact constructor/injection contract (fields: store, authorizer, config, confirmation_manager, agentbox_config_factory, tool_registry); (4) how `system_prompt()` relates to the omp agent-file markdown body (byte-parity requirement); (5) anything a naive subclass would get wrong; (6) unknowns and risks. Ranked findings, <300 words.
