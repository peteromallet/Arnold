# Megaplan Native Parity Corrective

Corrective epic to make canonical Megaplan reach the native representation end
state without repeating the previous false pass.

Primary anchors:

- `NORTHSTAR.md`
- `docs/arnold/megaplan-native-representation-report.md`
- `docs/arnold/megaplan-native-current-codebase-map.md`
- `docs/arnold/megaplan-native-oracle-synthesis.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`

Run profile decision:

- Overall plan difficulty: 5/5.
- Selected profile: `partnered-5` for every milestone.
- Reason: this is a public-contract/runtime-semantics migration where a bad
  plan can pass local tests while preserving hidden component/handler routing.

Sprint compression:

- The launch chain now uses 7 busy two-week milestones plus a narrow S2.5
  bridge because S1 and S2 are already complete and should not be reverted by
  default.
- The original 10 milestone briefs remain in `briefs/m*.md` as source
  appendices.
- The active launch briefs are `briefs/s1-*.md`, `briefs/s2-5-*.md`, and
  `briefs/s2-*.md` through `briefs/s7-*.md`; each sprint brief names which
  original milestone scope it absorbs or bridges.
- No end-state scope is intentionally dropped. Any future narrowing still
  requires the North Star rule: checker protection plus behavior proof.

Boundary alignment:

- S1 remains the completed source-authority/checker/outcomes foundation.
- S2 remains the completed front-half native loop.
- S2.5 audits S1/S2 and adds the minimal boundary/evidence vocabulary needed by
  native parity.
- S3-S7 must close phase migrations with both source-visible topology proof and
  durable boundary evidence.
- The broader `workflow-boundary-contracts` initiative is the follow-up
  generalization, not a competing phase migration.

Use the chain, not a single plan:

```bash
python -m arnold_pipelines.megaplan chain start \
  --spec .megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml
```

Cloud launch:

```bash
python -m arnold_pipelines.megaplan cloud chain \
  .megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml \
  --cloud-yaml .megaplan/initiatives/megaplan-native-parity-corrective/cloud.yaml \
  --fresh
```
