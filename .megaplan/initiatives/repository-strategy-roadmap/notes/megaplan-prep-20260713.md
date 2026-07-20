# Megaplan Prep — Repository Strategy Roadmap

## Sizing

This is an epic, not a single plan. The work spans five dependent architecture
slices, each sized to approximately one to two weeks of skilled engineering:

1. authoritative Markdown grammar, parser, validation, and projection;
2. ticket/epic identity, relationship, promotion, and completion lifecycle;
3. lossless CLI/operator workflows;
4. migration and mixed-version compatibility;
5. real repository adoption and end-to-end conformance.

Each milestone hands a concrete contract or implementation surface to the next.
Combining them would exceed two weeks and flatten multiple load-bearing
authority decisions into one review.

## Dial Choices

- M1 — Overall plan difficulty: 5/5; selected profile: `partnered-5`;
  because a plausible parser/projection design can pass local tests while
  creating a second strategy authority.
- M2 — Overall plan difficulty: 5/5; selected profile: `partnered-5`;
  because promotion spans immutable identity, dual artifacts, relationships,
  file/store parity, and completion semantics.
- M3 — Overall plan difficulty: 4/5; selected profile: `partnered-5`;
  because lossless Markdown mutation and CLI authority boundaries require hard
  decomposition; the default high-quality profile is retained.
- M4 — Overall plan difficulty: 5/5; selected profile: `partnered-5`;
  because mixed-version migration can silently corrupt references while green
  paths still pass.
- M5 — Overall plan difficulty: 4/5; selected profile: `partnered-5`;
  because the final authority/conformance audit must catch non-local drift; the
  default high-quality profile is retained.
- Robustness: `full` for every milestone. Cross-cutting contracts, migrations,
  and adoption need the standard critique/gate/review loop; no evidence warrants
  `thorough` or `extreme`.
- Depth: unset for every milestone. The briefs and North Star lock the product
  direction; no specific phase has demonstrated a need to override profile
  depth. Cloud Codex reasoning remains high at the runner level for D8 routing,
  but the Megaplan `depth` dial is deliberately not set.
- Vendor: Codex, consistent with the trusted resident's D8/Sol routing.
- Execution: unattended cloud chain with `merge_policy: auto` and
  `driver.auto_approve: true`; watchdogs/runners own continuation after launch.

## Anti-Scope for the Epic

Do not turn this into a generic work tracker, global portfolio, arbitrary typed
item registry, scheduling system, or rewrite of existing initiative/run-state
authority. Do not migrate unrelated artifacts merely because they share
Markdown/YAML helpers.
