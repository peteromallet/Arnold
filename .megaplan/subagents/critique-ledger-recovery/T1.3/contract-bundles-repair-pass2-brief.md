# GPT-5.6 Luna implementation brief — T1.3 repair pass 2

You are the GPT-5.6 Luna implementation owner. Work only in the isolated
worktree `/private/tmp/arnold-critique-recovery-contract-bundles-20260802`.
The exact candidate `97904d0fd8cba80c316f9607d3ac80381da77343` failed fresh
independent review. Read the complete report first:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-review-pass2-result.md`

Repair every ranked blocker at the root; do not narrow the requested end state
to current tests:

1. Replace family-prefix model acceptance with an immutable, exact,
   provider/model/tool-mode compatibility registry. Unknown, misspelled,
   family-spoofed, retired, and provider-incompatible models must fail closed.
   The registry must cover the actual current Arnold provider routes and be
   signed/digest-bound to the bundle.
2. At every production consumer boundary, re-resolve the canonical bundle by
   exact identity and verify bundle digest, manifest/artifact bytes, runtime
   compatibility, callable/enforcement identity, raw/output binding, and object
   revision. A caller-built/replaced `ContractBundle` retaining an old digest
   must never be trusted.
3. `repair_once` must derive validation errors independently from the exact
   pre-repair raw/object/bundle; it must not trust a caller-supplied error map.
   Permit exactly one independently proven invalid pointer, preserve every
   valid field byte/semantics, bind repair attempt and raw frames, and reject a
   fabricated error for a valid field.
4. Remove mutable container subclasses and rebindable module-global authority.
   Use genuinely immutable representations and a canonical registry whose
   identity/content is verified at lookup and use. Base-class method attacks,
   `dataclasses.replace`, module rebinding, monkeypatching, and stale cached
   objects must fail closed in the production path.
5. Close every remaining report finding, including mutable admitted
   snapshots/projections and finalize divergence, shadow parsing/authority,
   incomplete enforcement references, route omission, and any M6 evidence hash
   impact caused by the scoped changes.
6. Preserve platform-wide reuse: the core admission/runtime/binding authority
   must be shared by non-Megaplan pipelines; Megaplan-specific critique/graph
   adapters may sit on top. Inventory and make executable alternate/bypass
   paths fail closed or delegate to the canonical boundary.
7. Prove source checkout, materialized wrappers, and a hermetically installed
   wheel with declared minimum dependencies behave identically. Run the actual
   wheel from outside the source tree and test installed-wheel tampering and
   registry/model/repair attacks in fresh processes.

Add adversarial regression tests for every independent exploit in the report.
Run focused tests, the relevant broader dependency closure single-flight,
compile/diff/static checks, wheel build/install/parity/tamper tests, and record
exact commands/results. Do not change cloud/provider/runtime state. Do not edit
the master checklist or claim formal completion.

Commit only scoped changes in the isolated worktree. Require a clean worktree
after the commit. Write the final implementation report to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.3/contract-bundles-repair-pass2-result.md`

The report must state exact commit/tree, files changed, invariants proven,
adversarial probes, full test results, packaging proof, remaining external
owner/deployment evidence, and any limitation. If an invariant is still false,
say FAIL rather than hiding it behind green tests.
