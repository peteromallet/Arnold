# Live Agentic Harness

This directory is reserved for true live-agentic VibeComfy tests.

A test belongs here only when the subject-under-test is a real model or agent
using production-like tools, and the evidence comes from the actual run. Fake or
faking actors, deterministic builders, scripted `messages.jsonl`, and structural
contract scenarios do not belong here.

Current deterministic scenario coverage lives in `tests/structural_harness/`:

```bash
python -m tests.structural_harness.runner --mode structural --actor fake --tag run
```
