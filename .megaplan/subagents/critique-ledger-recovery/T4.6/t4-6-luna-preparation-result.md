# T4.6 freeze v2 resources as read-only evidence — Luna preparation

Verdict: **NO FREEZE; preparation only.**

## Exact freeze set

Derive targets from accepted T0.2/T0.4 plus T4.1–T4.5 receipts: v2 workspace, branch/ref, Git objects, worktree metadata, initiative/spec/chain/cloud specs, North Star/briefs, plan/state/events/journals/WAL/checkpoints, raw model/critique/finalizer outputs, repair/fixer/diagnostic/notification/publication receipts, runtime/vector/import/wrapper/service identities, marker bytes, process/owner/WBC snapshots and every linked artifact. Each target is an explicit path/ref/URI with device/inode/type/mode/size/mtime, Git blob/tree/commit where applicable, SHA-256, owner classification and source query. No glob/broad recursive target is authority.

The marker is evidence: hash/copy it byte-for-byte and never edit, rebind, rename, touch or delete it. T4.5's authoritative projection supplies `should_run=false`.

## Freeze transaction and storage

1. Require accepted T4.1–T4.5, zero admitted old writers, and T0.2/T0.4 re-verification.
2. Inventory and credential-scan/redact into two classes: exact restricted originals and redacted review derivatives. Never alter originals to redact them; encrypted restricted storage retains exact bytes with access policy/key identity recorded separately.
3. Stream objects into a content-addressed archive using safe no-follow opens, hashing while reading; detect inode/type/size/mtime changes and abort on race.
4. Preserve Git commits/trees/blobs/refs in a verified bundle plus ref manifest; never rebase/force/delete source refs. Record worktree/admin metadata separately without making the old checkout runnable.
5. Create two independently verified copies: primary immutable/read-only archive and off-volume replica on a distinct device/storage domain. Prefer object-lock/WORM or immutable snapshot; otherwise read-only bind mount plus owner-controlled ACL and append-only custody ledger. Filesystem permissions alone are insufficient authority.
6. Verify manifest, archive indexes, signatures, object counts/bytes, Git bundle, random and complete hash pass, then perform a restore into disposable read-only scratch and replay representative readers.
7. Only after both copies and restore pass, revoke write capabilities/mount old live resources read-only through authorized storage interfaces. Do not delete or prune them.

## Manifest and receipt

Schema binds incident/tuple/T4 receipts; collector/verifier code+runtime; capture clocks; ordered target rows; path/ref/URI, object type, provenance, size/digest/mode; Git reachability; secret classification/redaction mapping; archive/chunk/index digests; encryption/access/key references (no secrets); primary/off-volume storage identities; object-lock/ACL/mount receipts; excluded ephemeral caches with reason; unavailable/ambiguous rows; restore commands/results; late-writer observations; signer/key/revocation heads and retention/reopen policy. Independent verifier must compute its own manifest from originals and compare, not trust producer counts.

## Late-writer detection and negatives

Take pre/post hashes and two observations separated by a bounded interval; monitor owner heads, filesystem changes, open writable handles, processes, mounts, container volumes and ref updates. Any late writer, unreadable object or UNKNOWN blocks freeze acceptance and returns to the owning T4 fence step.

Negative tests: symlink/hardlink swap; path traversal; inode replacement during read; sparse/large/WAL file; Git ref race; missing unreachable object; dirty/untracked file omission; marker drift; secret leakage in redacted derivative; encrypted original unavailable; same-device “replica”; writable archive/ACL bypass; mutable object-store key; corrupt chunk/index/signature; partial upload/response loss; restore mismatch; missing xattr/mode; clock rollback; late PID/open handle; broad glob expansion; archive tool following external link; deletion/prune presented as freeze. Every case fails closed and preserves originals.

Current execution is blocked by incomplete T4.1–T4.5 and absent authorized storage/object-lock interfaces. No code, Git, cloud, provider, process, owner, marker, ticket or checklist state was mutated. This report is the sole write; SHA-256 is external.
