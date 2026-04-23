# SWE-bench Eval Run: iteration-004

## Results
- **Pass rate: 8/13 (62%)** (scored)
- Tasks attempted: 104/500
- Predictions generated: 34
- Total cost: $0.00

## Config
- Models: {
  "prep": "zhipu:glm-5.1",
  "plan": "zhipu:glm-5.1",
  "critique": "zhipu:glm-5.1",
  "revise": "zhipu:glm-5.1",
  "gate": "zhipu:glm-5.1",
  "finalize": "zhipu:glm-5.1",
  "execute": "zhipu:glm-5.1",
  "review": "zhipu:glm-5.1"
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
