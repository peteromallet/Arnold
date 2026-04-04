# Hermes-Megaplan

Fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent) with [Megaplan](https://github.com/peteromallet/megaplan) integration for automated SWE-bench evaluation. We intend to merge improvements back upstream.

Two open-weight models work together through Megaplan's structured phases (prep, plan, critique, gate, execute, review) to solve real GitHub issues from SWE-bench Verified. The goal: beat the best closed-source models on this benchmark.

**[Live dashboard](https://peteromallet.github.io/swe-bench-challenge/)** -- watch the experiment in real time.

## How It Works

```
prep → plan → critique → gate → [revise → critique → gate]* → finalize → execute → review
```

Each phase can use a different model and provider. The critique phase runs parallel sub-agents (one per check). The gate enforces structured flag resolution before proceeding. After execution, an independent review checks the changes.

Scoring happens via Modal (remote Docker containers) against the official SWE-bench harness.

## Quick Start

```bash
# Prerequisites: megaplan CLI on PATH, Modal account configured, API keys set up
pip install -e .

# Run an iteration (3 parallel workers):
python -m auto_improve.loop --workers 3

# Monitor progress:
python -m auto_improve.dashboard

# Compare scores across iterations:
python -m auto_improve.check_scores
```

See [`auto_improve/README.md`](auto_improve/README.md) for full details on configuration, CLI commands, the improvement process, architecture, and failure analysis.

## Configuration

Model selection and robustness levels are controlled via `auto_improve/base_config.json`. Each pipeline phase can use a different model with provider prefixes (`zhipu:`, `minimax:`, `google:`, or OpenRouter by default).

Three robustness levels -- `light`, `standard`, `heavy` -- control how many critique checks run and whether the gate loop iterates.

## Links

- [Live dashboard](https://peteromallet.github.io/swe-bench-challenge/) -- score progression, per-repo breakdown, task details
- [Megaplan](https://github.com/peteromallet/megaplan) -- the planning harness
- [Original Hermes Agent](https://github.com/NousResearch/hermes-agent) -- the upstream project
- [Detailed docs](auto_improve/README.md) -- full CLI reference, architecture, failure catalog

## License

MIT -- see [LICENSE](LICENSE).
