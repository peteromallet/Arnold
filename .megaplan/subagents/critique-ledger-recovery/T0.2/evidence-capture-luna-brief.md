# T0.2 implementation brief — off-volume evidence manifest

You are the evidence-capture owner for task T0.2 in the Critique Ledger recovery.
Use GPT-5.6 Luna judgment. The repository is:

`/Users/peteromalley/Documents/Arnold`

The user's checkout is very dirty. Treat every existing file/change as user-owned.
You may write only beneath:

`/Users/peteromalley/Documents/Arnold/evidence/critique-ledger-recovery/T0.2/`

and ephemeral `/private/tmp` paths you create. Do not edit repository code, specs,
markers, plans, branches, worktrees, or any cloud state. Do not commit, push, deploy,
kill, stop, resume, clean, rotate, truncate, or notify.

## Authority boundary

All remote access must be read-only. The old `megaplan-cloud` command surface is
zero-authority historical material under M11; do not invoke legacy `cloud chain`,
`--fresh`, tmux control, marker editing, direct-copy promotion, or mutation wrappers.
You may inspect repository connection documentation and use the accepted read-only
transport/probe surface. If no accepted read-only transport can be established, record
the exact blocker rather than improvising authority.

## Incident target

- session: `critique-ledger-accountability-v2-20260728`
- workspace: `/workspace/critique-ledger-accountability-v2-20260728/Arnold`
- spec: `/workspace/critique-ledger-accountability-v2-20260728/Arnold/.megaplan/initiatives/critique-ledger/chain.yaml`
- plan: `cl2-wbc-backed-ledger-20260731-1411`
- observed terminal state: `manual_review`, `gated`, `stalled`, stopped
- model tiers: DeepSeek v4 Flash, DeepSeek v4 Pro, GLM 5.2
- diagnostic failure: `DelegationProvenanceError: cloud session marker has no resident delegation provenance`

## Required result

Capture an immutable, machine-verifiable manifest of the old incident evidence onto the
independent local filesystem above. Include, where discoverable without mutation:

- session marker and cloud spec;
- exact initiative spec, workspace/repository state, branch/commit/dirty facts;
- plan state, chain state, event journals/projections;
- raw model outputs, normalized critique attempts, finalizer candidates;
- repair/fixer records and diagnostic launch state;
- runtime vector: commit, package/image, Python, wrappers, process command/executable,
  imports/config/model routes;
- notification escalation/attempt/provider receipts;
- disk bytes/inodes/mount facts and relevant store/database/WAL metadata;
- provider facts already persisted locally/remotely (do not query/send to providers);
- all relevant paths/URIs, without copying secrets or credentials.

For each object/claim record at least:

- stable logical name and category;
- source path/URI and capture method;
- SHA-256 (or explicit `unavailable` reason), byte size, file type;
- capture timestamp and clock basis;
- collector version and local repository commit;
- remote runtime/commit when known;
- minimal safe query/excerpt sufficient to support the claim;
- whether independently copied, hash-verified, missing, ambiguous, or blocked.

Requirements:

1. Do not follow symlinks outside the explicitly inspected incident scope.
2. Do not copy credentials, environment secrets, private keys, tokens, or full sensitive
   environment dumps. Redact safely and record redaction metadata.
3. Avoid huge blind copies. Inventory first, then capture the minimum sufficient raw
   artifacts with per-file limits and explicit omissions.
4. Produce a canonical JSON manifest plus a human-readable README/report and a verifier
   script or command that re-hashes all copied artifacts from an independent path.
5. Copy raw artifacts into a content-addressed `objects/sha256/...` layout when feasible;
   the manifest is the logical-path mapping. Never overwrite a differing digest.
6. Record remote commands and exit status without leaking secrets. Use read-only commands
   only (`stat`, `find` with bounded scope, hashing, database read-only queries, process
   inspection, filesystem capacity inspection, Git read operations).
7. Independently verify the completed local manifest and write the verification receipt.
8. If remote access or an artifact is unavailable, keep the overall manifest usable and
   mark the exact gap/blocker. Do not fabricate completeness.

Return a concise result naming the output paths, counts/bytes, verification result, exact
gaps, and whether T0.2's formal completion criterion is satisfied. It is satisfied only
if the manifest verifies from the independent filesystem and the required incident
classes are either captured or explicitly evidenced unavailable with an authoritative
reason.
