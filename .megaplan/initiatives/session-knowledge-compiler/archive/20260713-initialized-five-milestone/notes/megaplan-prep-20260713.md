# Megaplan Prep Record — 2026-07-13

## Sizing

Epic, five ordered sprint-sized Megaplans. The durable event/cursor substrate is
the handoff for extraction; the extraction schema is the handoff for synthesis
and UX; those records feed promotion governance; all earlier contracts feed
paper-cut consolidation and rollout. The combined scope is materially more
than two weeks and contains several load-bearing public data contracts.

## Dial choices

- **M1:** Overall plan difficulty 5/5; selected profile `partnered-5`;
  because a bad cursor/transaction boundary can silently skip evidence while
  local happy-path tests pass. Robustness `full`; default depth; directed prep.
- **M2:** Overall plan difficulty 5/5; selected profile `partnered-5`;
  because claim/evidence classification and direct-model validation are public
  data contracts that can silently turn inference into fact. Robustness `full`;
  default depth; directed prep.
- **M3:** Overall plan difficulty 5/5; selected profile `partnered-5`;
  because correction, synthesis, and search must not create a mutable parallel
  truth source. Robustness `full`; default depth; directed prep.
- **M4:** Overall plan difficulty 5/5; selected profile `partnered-5`;
  because stale or contradictory promoted knowledge can mislead future work
  outside the producing session. Robustness `full`; default depth; directed
  prep.
- **M5:** Overall plan difficulty 5/5; selected profile `partnered-5`;
  because consolidation and default rollout can erase lineage or amplify cost
  across every session. Robustness `full`; default depth; directed prep.

Recorded shorthand: `partnered-5/full +prep` for every milestone. Depth is
intentionally unset so the profile default applies.

## Model/provider evidence

Pinned runtime revision: `962fcb0ec530594290439c7c41a1be0602467336`.

`arnold_pipelines/megaplan/profiles/partnered-5.toml` assigns canonical Pro
slots to `hermes:deepseek:deepseek-v4-pro`, including prep/critique/gate and
execution tiers 3–6. `arnold_pipelines/megaplan/profiles/policy.py` defines
`DEFAULT_DEEPSEEK_PROVIDER = "direct"`, accepts only `direct`, and maps the
canonical direct Pro spec to `hermes:deepseek:deepseek-v4-pro`. Each chain
milestone also persists `deepseek_provider: direct` explicitly.

## Execution breakpoint

The verified pinned launcher does not expose the newer `config` subcommand and
`~/.config/megaplan/config.toml` is absent, so no durable
`execution.auto_approve` override exists. The governing request authorizes
durable planning launch but does not bypass the harness's destructive execute
approval. `driver.auto_approve` is therefore `false`.
