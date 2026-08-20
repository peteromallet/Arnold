# T1.8 GEN-DEPLOY — independent Sol review pass 1

You are a fresh GPT-5.6 Sol at high reasoning. Independently and adversarially
review exact candidate commit:

`69be00087f0d469b1e551fa8617c257f28783b7a`

Worktree:
`/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802`

Do not trust the implementer, its DeepSeek audit, or its tests. Do not edit
source, amend the commit, deploy, SSH, mutate cloud state, or claim formal T1.8
completion. You may write only the report path below and disposable test output.

Review the whole 7,885-line authority surface as an adversarial release/security
boundary, not as a normal feature patch. Prove or falsify:

1. Production authority cannot be locally self-created, duck-typed, anchored to
   an attacker-chosen store, repinned, or bootstrapped by possession of source.
2. Owner-installed provisioning is one-time, external, path/target/key/domain
   bound, authenticated, replay/response-loss safe, and distinct from hermetic
   test authority.
3. Every decision and envelope is canonical, strictly typed, signed, fresh at
   the right boundary, scope/capability/target/generation/fence/selector/CAS
   bound, nonce/idempotency safe, and supersedable only by authorized lineage.
4. No caller can fabricate an executor permit, effect receipt, installed
   observation, writer rejection, recovery outcome, or custody receipt.
5. Deployment, supersession, and recovery cannot interleave into two winners;
   all external effects and store transitions remain serialized and reconcile
   correctly across crashes and final-CAS/commit/response ambiguity.
6. An indeterminate deployment stops further effects and can be resolved only
   by signed owner recovery plus genuine adapter evidence that old writers are
   fenced/rejected. Wrong results/targets/digests must be nonmutating.
7. Offline receipts cryptographically/content-addressably bind every decision,
   operation, effect, prior/result selector, fence, old/rejected writer,
   timestamp, outcome, and bootstrap retirement. Tampering any field fails.
8. The absence of a production adapter is explicit and fail closed in every CLI
   and library path—no hermetic adapter or local path can masquerade as production.
9. Public CLI, schemas, docs, exports, package data, lockfile, installed wheel,
   and source behavior are complete and byte/semantic-parity checked.
10. Error and recovery paths preserve traceback-free typed machine output and do
    not expose secrets, silently retry unknown external effects, or leave an
    unrecoverable false-success state.

Inspect implementation rather than trusting tests. Add your own minimal probes
for any suspicious boundary. Run focused, wheel, static, and relevant regression
checks once with controlled temp output. Consider SQLite/WAL/filesystem locking,
two-process races, partial writes, fsync/rename assumptions, clock boundaries,
signature confusion, Pydantic coercion, path aliases/symlinks, and replay after
restart. A fail-closed missing production integration is a limitation, not a
PASS for production deployment.

Write:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-independent-review-pass1-result.md`

First line exactly `PASS` or `FAIL`. Rank blockers; include exact files/lines,
minimal reproductions, and required corrections. On PASS, enumerate commands
and results plus residual limitations. Explicitly distinguish local candidate
soundness from formal T1.8 acceptance and production availability.
