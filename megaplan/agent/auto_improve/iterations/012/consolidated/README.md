# SWE-bench Eval Run: iteration-012

## Results
- **Pass rate: 1/1 (100%)** (scored)
- Tasks attempted: 48/20
- Predictions generated: 2
- Total cost: $0.00

## Config
- Models: {
  "prep": "MiniMax-M2.7",
  "plan": "MiniMax-M2.7",
  "critique": "MiniMax-M2.7",
  "revise": "MiniMax-M2.7",
  "gate": "MiniMax-M2.7",
  "finalize": "MiniMax-M2.7",
  "execute": "MiniMax-M2.7",
  "review": "MiniMax-M2.7"
}
- Robustness: heavy
- Dataset: princeton-nlp/SWE-bench_Verified

## Files
- `summary.json` — Full scorecard with per-task results
- `predictions.jsonl` — All patches (SWE-bench submission format)
- `scores.json` — SWE-bench evaluation results
- `tasks/<instance_id>/` — Per-task patch, audit, traces, score

## Reproduction
```bash
python -m evals.run_evals --config <config> --workers 10
```
