# SWE-bench Eval Run: iteration-017

## Results
- **Pass rate: 2/2 (100%)** (scored)
- Tasks attempted: 27/20
- Predictions generated: 12
- Total cost: $0.00

## Config
- Models: {
  "prep": "zhipu:glm-5.1",
  "plan": "zhipu:glm-5.1",
  "critique": "minimax:MiniMax-M2.7-highspeed",
  "revise": "zhipu:glm-5.1",
  "gate": "zhipu:glm-5.1",
  "finalize": "zhipu:glm-5.1",
  "execute": "zhipu:glm-5.1",
  "review": "minimax:MiniMax-M2.7-highspeed"
}
- Robustness: standard
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
