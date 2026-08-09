# Luna explorer 2 — runtime/source custody and lineage

You are GPT-5.6 Luna, read-only, high reasoning. Do not edit files, launch
cloud commands, or use collaboration tools. Return an evidence report under
1200 words.

Read `evidence/critique-ledger-recovery/sol-p2-framing-result-20260804.md`,
`sol-final-plan-20260804.md`, and `luna-vj9-review-20260804.md`. The known
symptom is that the clean v3 snapshot still has older silent-dedup logic while
captured r5 validation used content-safe behavior, alongside wrapper/chain
interpreter differences.

Audit: `arnold_pipelines/megaplan/cloud/cli.py` command constructors,
`agentbox_adapter.py`, chain templates/driver, runtime/source binding helpers,
editable-install/PYTHONPATH logic, and any code that reports module paths,
revision, or runtime hash. Trace how validation, resident, chain, status, and
resume each resolve Python and imports.

Decide whether two stages can claim one attempt while executing different code.
Specify the minimum immutable custody fields and the exact hostile-PATH,
dirty-worktree, divergent-import, and changed-test-hash acceptance tests that
P2 must add. Flag anything that is already solved versus merely documented.
