# Agent Jury — Pi-Native Deliberation System

A blind multi-agent deliberation framework for high-stakes decisions, designed to run on Raspberry Pi 4/5 hardware with quantized local models.

## Architecture

```
                    ┌─────────────────────────────┐
                    │      PROPOSAL SUBMISSION     │
                    │  (decision to be evaluated)  │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │       JURY ORCHESTRATOR      │
                    │  - strips identity markers   │
                    │  - fans out to jurors        │
                    │  - enforces time/budget caps │
                    └──┬──────┬──────┬──────┬─────┘
                       │      │      │      │
              ┌────────▼┐ ┌──▼──┐ ┌─▼───┐ ┌▼────────┐
              │  JUROR 1│ │ J2  │ │ J3  │ │ J4   J5 │
              │  Risk   │ │Ethic│ │Util │ │Systems  ││Devil's│
              └────────┬┘ └──┬──┘ └─┬───┘ └┬────────┘└───┬───┘
                       │      │      │       │            │
                       └──────┴──┬───┴───────┴────────────┘
                                 │
                    ┌────────────▼────────────────┐
                    │      BLIND SYNTHESIS         │
                    │  - reads all verdicts        │
                    │  - identifies agreements     │
                    │  - AMPLIFIES disagreements   │
                    │  - confidence-weighted merge │
                    └────────────┬─────────────────┘
                                 │
                    ┌────────────▼────────────────┐
                    │      FINAL JUDGMENT          │
                    │  verdict + dissent log +     │
                    │  confidence + action items   │
                    └──────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `jury_orchestrator.txt` | Master prompt: fans out, collects, enforces caps |
| `jurors/risk_analyst.txt` | Worst-case analysis lens |
| `jurors/ethicist.txt` | Moral/ethical implications lens |
| `jurors/utility_maximizer.txt` | Cost/benefit, ROI, practicality lens |
| `jurors/systems_thinker.txt` | Second-order effects, systemic impacts lens |
| `jurors/devils_advocate.txt` | Assumption-challenging, opposition steel-manning lens |
| `blind_synthesizer.txt` | Aggregation, disagreement surfacing, final verdict |
| `schemas/verdict_schema.json` | JSON Schema for individual juror output |
| `schemas/final_judgment_schema.json` | JSON Schema for synthesized final output |
| `caps.json` | Runtime caps: token limits, time budgets, model assignments |
| `example_proposal.md` | A sample proposal to run through the jury |

## Design Principles

1. **Blind Deliberation** — Jurors never see each other's responses. Prevents anchoring, groupthink, and deference to "louder" agents.
2. **Lens Diversity** — Each juror uses a different prompt persona, model, or both. Diversity of perspective is the engine of the system.
3. **Disagreement Amplification** — The synthesizer explicitly surfaces dissent rather than averaging it away. A single strong objection can flip a verdict.
4. **Confidence Calibration** — Every output includes a confidence score (0.0-1.0) with required justification. Synthesizer cross-validates.
5. **Pi-Native Constraints** — Models are quantized GGUF (Q4_K_M), timeouts are strict, total deliberation < 5 minutes on Pi 5.
6. **Structured Output** — All verdicts are valid JSON against schemas. Machine-parseable, human-auditable.
