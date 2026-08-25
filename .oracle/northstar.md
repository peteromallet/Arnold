# North Star — Arnold first-run provider onboarding

## End state
A person who has just cloned Arnold launches `arnold` for the first time and, within a minute,
is talking to a working model — without reading docs, without editing YAML by hand, and without
ever seeing the same setup question twice.

## Principles
- **Detect before asking.** Show what already exists on the machine (CLI logins, keys in env
  or `.env` files) before offering anything manual. Found-first ordering beats blank menus.
- **One verified route is success.** Optimize time-to-first-working-model; multi-provider is an
  opt-in second visit, never first-run homework.
- **Persist once, reuse forever.** Every accepted credential lands in omp's own stores
  (agent.db / ~/.omp/agent/models.yml). Later launches silently reuse it. No re-prompts.
- **Provenance everywhere.** Every stored credential records where it came from so a later
  failure names its origin ("onboarded from ~/.codex/auth.json").
- **Headless stays fail-closed.** Non-TTY paths (cloud chains, watchdogs, RPC) behave exactly
  as today. Onboarding is strictly an interactive-terminal offer.

## Anti-patterns (hollow versions of success)
- A wizard that asks "which provider?" with a 30-row wall and no detection.
- Copying short-lived tokens as if static (dead in hours); or referencing static keys as if
  they must stay put (breaks when the .env disappears).
- Silently importing credentials without consent, or printing secrets anywhere.
- Onboarding logic duplicated inside the oh-my-pi fork (upstream merge pain) — fork stays
  vanilla unless something is proven impossible from the Arnold side.
- A half-wired exit: user configures three providers, none verified, flow ends "successfully".
- Regressing existing typed failures: any path that used to fail closed with
  `credential_preflight_failed` must still do so byte-for-byte when non-interactive or declined.
