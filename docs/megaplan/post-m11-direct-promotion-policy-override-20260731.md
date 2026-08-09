# Post-M11 direct-promotion policy override

Date: 2026-07-31

Status: authorized policy amendment for the post-M11 consolidation release.

## Decision

The release owner explicitly rejected creating a pull request and authorized
the completed consolidation to be pushed directly to GitHub `main`. This
amends only the transport/review mechanism in
`post-m11-loose-work-consolidation-release-plan-2026-07-29.md` and
`final-cloud-runtime-promotion-runbook-2026-07-31.md`.

Promotion must use an ordinary, non-force, fast-forward Git push of the exact
fully validated release-candidate commit. Immediately before the push, the
operator must fetch `origin/main`, prove it still equals the frozen expected
old SHA, prove that old SHA is an ancestor of the candidate, and prove the
remote consolidation ref equals the candidate. A raced or non-fast-forward
update fails closed. Rebasing, history rewriting, `--force`, and
`--force-with-lease` are not authorized.

After the push, the operator must fetch again, prove both `origin/main` and
`git ls-remote` equal the candidate, and require the GitHub CI run whose head
SHA is that exact candidate to pass. This direct-promotion decision waives no
validation, provenance, packaging, deployment, canary, rollback, evidence,
checkpoint-protection, or cleanup-approval gate.

## Tag ordering

The release uses two distinct tag roles:

1. A source tag may be created on the fully validated candidate before runtime
   construction. It proves only the immutable Git source identity.
2. The final annotated acceptance tag is created on that same commit only
   after deployment, rollback, health, and deployed-workflow-canary receipts
   exist. Its annotation records the hash and durable location of the external
   final acceptance receipt.

Neither tag changes the release commit. A source tag is not acceptance, and a
manually written terminal label is not evidence.

## Done projection

Once the actual implementation, exact-revision validation, remote `main`,
deployed runtime, health probes, and independent canary verifier all agree, a
`done` label may be generated as a convenience projection. It must cite the
final acceptance-receipt digest and cannot precede it.
