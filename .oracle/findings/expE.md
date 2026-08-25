# Area E — models.yml semantics (Explorer E)
Loader: ModelRegistry -> ModelsConfigFile -> ModelsConfigSchema validation + validateProviderConfiguration aux rules.
apiKey forms: literal | "$ENV_VAR" (exact-case env lookup, else literal fallback) | "!cmd ..." (isCommandConfigValue = startsWith '!').
!cmd contract: execSync timeout 10s, no cwd set, stdout trimmed (empty=failure), stderr NOT captured (leaks to terminal on sync path), failures negative-cached 30s (sync) / retried per request (async); !cmd failure NEVER throws — provider silently loses its key -> runtime auth error. hasCommandBackedApiKey() side-effect-free.
Provider entry kinds: override-only (patches bundled catalog provider of same name; needs >=1 of baseUrl/apiKey/headers/compat/transport or auth:none), custom models (models:[...] requires baseUrl+api+id, apiKey unless auth:none -> THROWS if missing), discovery ({type:...}), configuration-only (pure credential for bundled provider: just apiKey works).
Validation throws: models w/o baseUrl; models w/o api; missing id; contextWindow/maxTokens <= 0.
Grok generator contract (docs/omp-setup/grok-token.py): prints bearer to stdout, refreshes ~/.grok/auth.json via OIDC (300s margin, 20s HTTP timeout), uncaught exceptions -> nonzero exit -> undefined key.
IMPLICATIONS for Python generator:
- Configuration-only entry `providers:\n  deepseek:\n    apiKey: "<literal>"` is the minimal valid persistence for a BUNDLED provider (no models block needed!) — avoids all models-block throw rules.
- For catalog providers, literal apiKey in models.yml resolves through cascade leg 2. Simplest safe write path.
- Merge must preserve unknown fields (extras kept) and other providers; atomic replace.
- grok-style route: copy grok-token.py to ~/.omp/agent/ with $HOME-expanded path in !cmd.
Files: packages/coding-agent/src/config/{models-config.ts, model-config-values.ts, resolve-config-value.ts, model-registry.ts, custom-models.ts}.
