# T1.8 GEN-DEPLOY — Sol repair pass 2

You are GPT-5.6 Sol at high reasoning. Repair the full independent FAIL report
for exact candidate `69be00087f0d469b1e551fa8617c257f28783b7a`.

Worktree:
`/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802`

Read the complete report before editing:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-independent-review-pass1-result.md`

Do not narrow the task to easier modeled/hermetic behavior. Correct every ranked
blocker and the listed completeness gaps at the authority boundary:

1. Owner-installed production authority cannot be self-minted from arbitrary
   JSON/store metadata, same-UID files, caller-selected paths, keys or roots.
   Define an externally authenticated, privileged provisioning/discovery
   contract pinned to target/domain/store/lock/root/inodes/trust/executor/observer
   identities. Ordinary library/CLI callers and source possession must not create
   it. If the real venue integration is unavailable, production remains typed
   unavailable; no local facsimile may claim production capability.
2. Once an external effect is attempted after durable intent, only proven
   NOT_APPLIED evidence may terminalize rejection. Transport error, response
   loss, invalid/missing receipt, or any unproven result must reconcile or become
   indeterminate for every operation, including bootstrap; exact replay and
   signed recovery must remain possible.
3. Implement explicit forward-fix and rollback transition tables over durable
   store projection plus fresh signed target observation for genuine selector-CAS
   effect-applied/store-not-committed ambiguity. Recovery effects themselves need
   intent, evidence, reconciliation, crash/response-loss handling and idempotency.
4. Authenticate the complete offline custody root with a key pinned outside the
   receipt. Cover ordered event head/count, decisions/effects, selector/fence/
   writers, timestamps, terminal outcome and bootstrap retirement. Recomputed
   tampering must fail; verify temporal and terminal semantics.
5. Production verification requires fresh challenge-bound signed observation by
   a pinned observer/executor identity. Reject arbitrary Protocol/duck objects and
   stale snapshots; report typed missing production observer integration.
6. Set/lock the real compatible Pydantic range (minimum at least 2.11 if proven),
   and prove isolated minimum-supported and locked-wheel canonical bytes,
   signatures, schemas, round-trips, imports and module origin. No system-site
   package masking; import/startup failures must be typed/controlled where
   technically possible.
7. Remove the claim that Python name mangling is an unforgeable permit. Custody
   mutations must depend on independently authenticated evidence or a true
   privileged service-held capability. Ordinary in-process callers cannot create
   authoritative custody events by reading attributes/calling mangled methods.
8. Make production store/lock/root/path custody symlink/inode/replacement safe:
   protected directories, no-follow/safe opens, stable owner/mode/device/inode,
   trusted descriptors and descriptor-relative traversal as appropriate. Add
   symlink, hardlink, unlink/replace and two-process lock-race proofs. Where Python
   cannot deliver the venue guarantee, keep production unavailable and express a
   precise adapter/provisioner contract instead of pretending lexical checks are
   sufficient.

Also repair every additional completeness gap in the report: authenticated
adapter registration, `resolve --adapter production` must fail before store
touch, one public schema/validation registry, truly isolated wheel proof, and
crash-durable atomic JSON artifact writes.

Use the reviewer's probes as mandatory regressions. Add effect-then-error and
effect-then-invalid-receipt coverage for every operation; forward-fix/rollback
from real CAS effect ambiguity; recompute-capable receipt tampering; stale duck
observer; owner-store self-mint; minimum-Pydantic; symlink/lock races; public
registry parity. Preserve all positive signature/envelope/SQLite properties.

Run focused, wheel/minimum-dependency, static, crash/race and relevant broader
regressions using controlled scratch and one large test process at a time.

When and only when the implementation is reviewable, create one new commit and
leave the worktree clean. Write:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-repair-pass1-sol-result.md`

Include exact results and explicit remaining external integration limitations.
Do not deploy, SSH, mutate cloud state, edit the master checklist, or claim
formal T1.8/production availability. This creates only another review candidate.
