Provider preflight gap: `preflight.py` reports command and environment-variable hints only. It does not verify that the effective credential exists, aliases resolve consistently, the base URL is usable, or the provider can authenticate. Its provider map is also narrower than `KeyPool` and `DeepSeekAdapter`: routing, aliases, key variables, and defaults are duplicated across modules. `tests/arnold/agent/test_pool.py` is absent.

Single source of truth: create one provider registry containing provider name, model parsing, credential aliases, base URL defaults, supported agents, and a secret-safe authentication probe. Make preflight, `KeyPool`, adapters, and Hermes consume that registry. Preflight should validate the resolved provider/model against the registry, check effective credential presence without printing values, and optionally perform a bounded auth probe. A failed probe must block launch.

Acceptance tests:

1. A chain resolving `hermes:zhipu:<model>` must require the same credential aliases and base URL in preflight, `KeyPool`, and runtime dispatch; missing credentials fail preflight before launch.

2. Every configured alias pair—such as Zhipu/GLM, Kimi/Moonshot, Gemini/Google, and Fireworks variants—must produce identical effective credentials and base URLs across all consumers.

3. For every supported provider-prefixed model, preflight and the adapter must resolve the same provider, model name, endpoint, and authorization mode; no unsupported provider may pass preflight.

4. A managed cloud launch with failed credential preflight or failed lease acquisition must not emit `executing`, mutate execution state, dispatch a worker, or continue without an exact marker-bound PID/start-identity lease.
