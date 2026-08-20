# T1.3 contract bundles — repair pass 2 result

Candidate repaired: `e0b91992b2d2e01f7d7d87ba5053394a972984c6`

Commit: `97904d0fd8cba80c316f9607d3ac80381da77343` (`Repair T1.3 contract bundle boundaries`)

## Repairs

- Raw provider/capture bytes are required and strictly framed/parsed before semantic validation. Duplicate keys, non-finite values, truncation, appended prose, provider errors, missing bytes, and wrong tool framing are typed failures rather than `NO_FINDING`.
- Binding and consumer validation now compare raw-output digest, admitted/output digest, bundle, provider/model/tool/runtime identity, object revision, and repair count.
- One immutable admitted payload snapshot is bound before harness projections. Legacy recovery cannot replace it; the only permitted repair is one scoped pointer repair with original binding, raw/payload digests, bundle/runtime, and whole-object semantic checks revalidated.
- Route registries and nested manifests are deeply immutable and preflight-verified, including route-key/step/tool-mode agreement.
- Manifest enforcement references the concrete capture/parser/schema/normalizer/semantic/prompt/provider/model/tool/runtime implementations and their current hashes.
- Model identity is required, non-empty, known, and compatible; provider-error metadata fails closed.
- Prompt and tool-enabled critique/finalize paths persist exact admitted payload/raw sidecars and preserve capture metadata through worker/adapter boundaries.
- Added reviewer minimal reproductions and adversarial regression coverage.

## Verification

- Focused contract/orchestration regression set: **220 passed** in 2.83s.
- Contract-bundle focused subset: **29 passed** (included in the set above).
- `python -m py_compile` on all modified Python modules: passed.
- `ruff format --check` on all modified Python modules/tests: passed; 9 files already formatted after the final formatting pass.
- `git diff --check`: passed.
- Wheel build/install proof from an external `/tmp` working directory: installed package preflight found all 4 routes.
- Fresh-process installed-wheel tamper proof: exited with status **1** and reported `artifact digest mismatch`.
- Worktree after commit: clean.

## Limitations

- A scoped Ruff F821 check still reports pre-existing undefined-name diagnostics in legacy worker regions (`hermes.py` and `shannon.py`); these are unrelated to the contract-boundary changes and were not broadened into this repair.
- No deployment, SSH/cloud mutation, master-checklist edit, or formal T1.3 completion claim was made.
