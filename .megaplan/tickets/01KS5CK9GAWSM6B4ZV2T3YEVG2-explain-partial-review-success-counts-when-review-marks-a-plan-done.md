---
id: 01KS5CK9GAWSM6B4ZV2T3YEVG2
title: Explain partial review success counts when review marks a plan done
status: addressed
source: human
tags:
- review
- observability
- ux
codebase_id: null
created_at: '2026-05-21T13:46:29.770124+00:00'
last_edited_at: '2026-05-21T17:33:09.251632+00:00'
resolution_note: 'Fixed 2026-05-21: review success summaries now include waived, deferred-human,
  and non-blocking failed criteria counts when not all criteria pass. Covered by tests/test_handlers_review.py
  summary breakdown tests. DeepSeek post-patch review found no blockers.'
addressed_at: '2026-05-21T17:33:09.251635+00:00'
epics: []
---

During the Sisypy `sisypy-undetermined-recurring-run-semantics` run on 2026-05-21, the final review completed with:

```text
Review complete: 16/18 success criteria passed.
state: done
issues: []
rework_items: []
```

That may be internally valid, but from an operator perspective it is ambiguous. If 16/18 passed and the plan is done, the missing two criteria should be explained as skipped, advisory, not applicable, superseded, or otherwise non-blocking.

Why this matters:

The operator needs to know whether a terminal `done` plan has residual risk. A partial pass count with no issues forces manual artifact inspection even though the reviewer already had enough context to classify the two non-passing criteria.

Desired behavior:

1. Review output should include a breakdown: passed, failed, skipped/not-applicable, advisory, and not-evaluable.
2. If `state=done` and `issues=[]`, any non-passed criteria should have explicit non-blocking reasons.
3. `megaplan status` should summarize that distinction, not just `16/18 success criteria passed`.
4. Review JSON should retain criterion IDs/names for the non-passed criteria so operators can audit without reading the whole review artifact.

Concrete evidence:

- Plan: `sisypy-undetermined-recurring-run-semantics`
- Final review summary: `Review complete: 16/18 success criteria passed.`
- Terminal state: `done`
- Issues/rework: none.
