---
id: 01KYSS5QA9D8YD28W24TGSABDP
title: Standardize semantic completion specs for durable tasks, steps, and workflows
status: open
source: human
tags:
- architecture
- completion-contract
- native-parity
- platformization
- rework
codebase_id: null
created_at: '2026-07-30T15:09:34.409902+00:00'
last_edited_at: '2026-07-30T15:11:06.121548+00:00'
epics: []
---

Problem

Completion meaning is currently distributed across task objectives, success criteria, write sets, tests, sense checks, validation jobs, Workflow Boundary Contracts, and terminal evidence providers. A legacy done projection can disagree with accepted authority evidence, and genuinely new review work can become unroutable because it has no admitted semantic subject. Captured M10/M11 history demonstrates both failures.

Proposal

Introduce one neutral CompletionSpec -> CompletionBinding -> CompletionVerdict model, reusing existing Step-IO, WBC, EvidenceRef, CompletionVerdict, Custody, validation-job, and acceptance-transaction machinery.

- Generate mechanical obligations for every durable workflow, durable step, dynamic task, human gate, and effect.
- Require only small explicit domain obligations.
- Exclude pure helpers and projections.
- Bind specs content-addressably at admission.
- Evaluate candidate dispositions against scoped evidence.
- Propagate waiver taint and support complete-capture absence proof.
- Require new or reopened rework to use the normal admission and execution path.
- Treat accepted(...) as a proposed disposition, never authority to mark work done.
- Generate canonical machine records plus a disposable Markdown completion view.

Roadmap

- Custody M11 remains focused on transactional admission and acceptance.
- Megaplan Native Parity proves the model and migrates Megaplan.
- Workflow Platformization extracts the reusable public standard and proves a second consumer.

Required first vertical slice

finalize/admit -> execute -> landed-write and validation evidence -> verdict/acceptance -> review -> reopen an existing task or admit a new rework task -> execute -> aggregate workflow completion.

The captured REVIEW pseudo-task and legacy done-without-accepted-attempt trace is the mandatory negative fixture.

Design and oracle checklist

docs/arnold/standardized-completion-spec-proposal.md

Do not create a second evidence registry, verdict system, waiver subsystem, scheduler, or acceptance authority.
