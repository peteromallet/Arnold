# T1.3 contract bundles — repair pass 2

You are GPT-5.6 Luna at high reasoning. Repair every blocker in the independent
review of exact candidate `e0b91992b2d2e01f7d7d87ba5053394a972984c6`.

Worktree:
`/private/tmp/arnold-critique-recovery-contract-bundles-20260802`

Read the full report first:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-review-pass1-result.md`

The required root corrections are:

1. Raw provider/capture bytes are the source of truth at the real critique and
   finalize production seams. Require non-empty raw bytes, strict selected-bundle
   parsing/framing/tool mode, and equality between parsed payload digest and the
   admitted/promoted payload before any semantic acceptance. Missing, malformed,
   duplicate-key, non-finite, truncated, prose-appended, provider-error, or
   wrong-framing raw output must be a typed failure, never `NO_FINDING`.
2. Consumer validation must compare the exact `raw_output_digest`, output digest,
   bundle, runtime/provider/model/tool identity, object revision and repair count.
3. Define and enforce one exact immutable admitted object. Complete permitted
   harness transformations before binding. Eliminate post-bind finalize mutation
   and critique legacy replacement, or force them through the one narrow repair
   path that rechecks original binding, pointer allowlist, whole-object/raw
   digests, bundle/runtime, and whole-object semantics before use/persistence.
4. Make the route registry and nested manifest deeply immutable. A caller cannot
   swap a route, mutate policy, or leave a corrupted active registry after
   preflight. Verify route key equals the bundle's own step/tool mode.
5. Bind and invoke the actual enforcement implementations: capture/parser,
   schema, normalizer/transformation policy, semantic validator, prompt,
   provider/model/tool assumptions, fixtures, and expected runtime. Hashes/ABI
   labels for unrelated files are not sufficient.
6. Require a non-empty actual model identity and fail closed on missing, unknown,
   incompatible, or provider-error metadata.

Add the reviewer's minimal reproductions as regression tests. Audit both prompt
and tool-enabled critique/finalize paths, persisted artifacts, recovery/restart,
installed wheel, and fresh process. Do not weaken existing schemas or redefine
malformed output as a finding. Preserve exactly-one scoped pointer repair.

Run focused/adversarial tests, relevant orchestration regressions, wheel/tamper
proof, formatting/static checks, and `git diff --check`, using one controlled
test process at a time. Clean only task-created scratch output.

When and only when sound, create one new commit on this branch and leave the
worktree clean. Write:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-repair-pass1-result.md`

Include commit SHA, exact results, and limitations. Do not deploy, SSH, mutate
cloud state, edit the master checklist, or claim formal T1.3 completion.
