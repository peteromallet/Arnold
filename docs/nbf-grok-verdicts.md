I'll ground each verdict in the actual code and the six investigator reports rather than taking their classifications at face value.The reports line up with real files. Next I’ll read the shipped seams and the ledger so the verdicts rest on current code, not just investigator summaries.The reports are consistent with the tree. One extra fact matters: babysitter routing tests still describe the pre-omp rewrite, which changes how I’d weight the identity-routing class.The 24h marathon was not six independent bugs. It was one missing **admission object**: nothing that launches or kills a worker is required to prove the model is live, the family is known, the runtime is the bound interpreter, the cgroup can hold it, and the killer is named. Most of the shipped diffs are local patches around that hole.

## 1) One-line verdicts

| Class | Verdict | Confidence |
|---|---|---|
| **A Identity-routing** | **ADHERENCE** | **90%** |
| **B Catalog-family** | **MIXED** | **88%** |
| **C Turn-timeout** | **MIXED** | **85%** |
| **D Runtime-resilience** | **MIXED** | **90%** |
| **E Dispatch-unification** | **DEEP** | **90%** |
| **F Supervision-ops** | **MIXED** | **88%** |

**A — ADHERENCE.** The instant-death path is a dropped documented branch, not a missing concept. `launch.py:27–28` still documents the worker as `launch_omp_agent.py --model=omp:deepseek/...`. `routing.py:65,67` still pass `ARNOLD_BABYSITTER_OMP_MODEL` verbatim into `launch.py:473`. `_translate_model` (`launch_omp_agent.py:99–125`) is the documented translator; G14’s rewrite omitted `"omp": ""` and the identity tail-return. Zero tests touch `_translate_model`/`_PREFIX_MAP`. That is contract drift. The *expired* ox-alpha pin is a different defect (live-catalog invariant) and belongs with B, not A.

**B — MIXED.** The glm-5.3-flash gate deaths are the adherence symptom: a catalog row was added in `workers/omp.py:104` without updating the family vocabulary. `parse_omp_spec` feeds `model_id` as `normalized_model` (`omp.py:1206–1207`); `classify_model_family` then saw `z-ai/glm-5.3-flash`, which matched neither `_PROVIDER_PREFIXES` (`model_seam.py:435–443`) nor the old
