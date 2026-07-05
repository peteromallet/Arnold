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

- The launch chain now uses 7 busy two-week milestones.
- The original 10 milestone briefs remain in `briefs/m*.md` as source
  appendices.
- The active launch briefs are `briefs/s1-*.md` through `briefs/s7-*.md` and
  each names which original milestone scope it absorbs.
- No end-state scope is intentionally dropped. Any future narrowing still
  requires the North Star rule: checker protection plus behavior proof.

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
