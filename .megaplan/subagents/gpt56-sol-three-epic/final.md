Implemented the three-initiative reshape without launching plans or touching M11.

### Changed files

- Native Parity: [chain.yaml](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml), [README.md](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/megaplan-native-parity-corrective/README.md), [NORTHSTAR.md](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md), [GOLDEN_TRACE_CONTRACT.md](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/megaplan-native-parity-corrective/GOLDEN_TRACE_CONTRACT.md), and briefs for C1, C2, S2F, S2R, S5A, S5B, and S7.
- Completion source initiative: [.retired](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/standardized-completion-specifications/.retired), [chain.yaml](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/standardized-completion-specifications/chain.yaml), [cloud.yaml](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/standardized-completion-specifications/cloud.yaml), [README.md](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/standardized-completion-specifications/README.md), [NORTHSTAR.md](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/standardized-completion-specifications/NORTHSTAR.md), and [SUPERSESSION_CROSSWALK.yaml](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/standardized-completion-specifications/SUPERSESSION_CROSSWALK.yaml).
- Platformization: [chain.yaml](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/native-workflow-platformization/chain.yaml), [README.md](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/native-workflow-platformization/README.md), [NORTHSTAR.md](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/native-workflow-platformization/NORTHSTAR.md), [PLATFORM_CONTRACT.md](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/native-workflow-platformization/PLATFORM_CONTRACT.md), and all seven S1–S6 briefs.

### Result

- Native order is exactly `S1 → S2F → C1 → C2 → S2R → S3A → S3B → S4 → S5A → S5B → S6 → S7`.
- All 12 Native stages now have executable gate declarations; seven authority-changing stages have receipt-consuming transitions and independent post-transition verification.
- Platform order remains `S1 → S2A → S2B → S3 → S4 → S5 → S6`, with seven gates and three transitions.
- C1/C2 are explicitly Completion M1/M2 hosted inside Native. C2 remains shadow-only; S2R GO-0 is the sole first enforcement point.
- All 19 oracle amendments, including low-boilerplate authoring, have explicit proof rules.
- All 83 preserved requirements now map to 30 hashed source slices, exact active milestone labels, and 40 concrete proof rules.
- Platformization consumes the landed kernel and existing acceptance transaction; it cannot fork or re-enable them.

### Preservation

The five historical Completion briefs and proposal were not modified. Legacy Native briefs remain unreferenced historical appendices. M11/Custody files and live cloud state were untouched. No plan was launched, and no commit, push, or PR was created.

### Validation

- Strict YAML and duplicate-key validation: passed.
- Chain order, dependencies, gates, transitions, and source references: passed.
- Crosswalk hashes, ranges, owners, proof references, and IDs: passed.
- Platform acceptance families `PWC-AF-01..38`: passed.
- Stale active milestone/order search and whitespace checks: passed.
- Documented Platform `chain status` and `chain verify` both fail closed with `required_proof_artifacts` unknown. This is expected until the milestone-gate bootstrap installs that schema.

Unresolved empirical dependencies are the still-running M11 completion manifest, Custody’s bounded-projection/57k handoff, bootstrap readiness artifacts, and milestone-produced validators/proof maps. Historical platform evidence recovery/reproof also remains assigned to Platform S1.