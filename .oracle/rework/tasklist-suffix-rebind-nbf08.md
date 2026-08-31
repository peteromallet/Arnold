# Tasklist suffix rebind — NBF08 definitive chain-control ledger

Date: 2026-08-31

## Authorization and boundary

This is the authorized future-suffix rebind requested by the user: append the
fully reviewed NBF08 definitive-ledger task, make NBF07 depend on NBF08, and
update the transparent execution denominator. The accepted NBF01–NBF03
prefix and Batches 1–2 content remain verbatim; no source, plan, North Star,
goal, custody, branch, or chain-runtime content was changed. No launch,
deployment, merge, or push was performed.

The pre-rebind tasklist was verified at SHA-256
`9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.
The accepted prefix remains the existing NBF01–NBF03 contract and its
Batch-1/Batch-2 checkpoint records. The rebind changes only the future
execution suffix and its dependency/order metadata.

## Rebound identities

| Artifact | SHA-256 | Role |
|---|---|---|
| `.oracle/tasklist.md` | `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73` | authoritative tasklist after final suffix rebind |
| `.oracle/status.md` | `6fad3ea0ba543fccabda56d6dc3e9afc6d369de853c27a7ea6aa15281c0dabf5` | transparent active status after denominator update |
| `.oracle/briefs/nbf08-definitive-chain-control-ledger.md` | `ef1d0260930343d6b60ace1bf11214c418c43aaf7203f674635ba6116a19437c` | NBF08 implementation brief |
| `.oracle/plan-addenda/nbf08-definitive-chain-control-ledger.md` | `36680fe27c6c293d70691fc470db16788ce9078edead6df87e74552e684c1875` | NBF08 plan addendum |
| `.oracle/research/nbf08-control-surface-inventory.md` | `e7882d57ed32a237ad0aa6f0774ea35776717e6891a5724d4e97360f0618d5d8` | 83-row research inventory |
| `.oracle/research/nbf08-mutation-gap-sweep.md` | `1909c7a68901d40c7187dd6a4528496042e367de35f159e665b7524e175c1439` | mutation-gap research evidence |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` | unchanged North Star |
| settled plan v8 | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` | unchanged plan reference |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` | unchanged goal reference |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` | unchanged custody reference |

The tasklist's NBF08 entry binds the exact brief, addendum, inventory, and
gap-sweep identities above. The final order is:

```text
Batch 4: NBF-06
Batch 5: NBF-08
Batch 6: NBF-07
```

NBF08 depends on NBF01 through NBF06. NBF07 retains its existing task ID and
scope, but now depends on NBF01 through NBF06 plus NBF08. NBF07 remains the
sole owner of final fresh-base integration, authoritative post-rebase
validation, push, and final Sol completion judgment.

## Superseded intermediate identity

The first suffix rebind was an intermediate identity and is superseded by the
final 83-surface rebind recorded here:

| Artifact | Superseded intermediate SHA-256 |
|---|---|
| `.oracle/tasklist.md` | `95ed8adb061c6b467c86a57984ada22e2912b2e3d82877fa4aaecc0547739023` |
| `.oracle/status.md` | `6fad3ea0ba543fccabda56d6dc3e9afc6d369de853c27a7ea6aa15281c0dabf5` |
| this rebind record | `50914dc801040cbfd75959a6197f5ca5f709ec503b2828645771ee760379033d` |

The original pre-rebind tasklist SHA and accepted prefix above remain the
authoritative predecessor; the intermediate identities are retained only for
audit lineage.

## Status denominator

Status now reports `3/8 = 37.5%` accepted tasks and `2/6 = 33.3%` accepted
batches. Batch 3 is active: NBF04 is built and accepted internally, while
NBF05 remains in rework. The denominator change from 7 tasks/5 batches is
explicitly recorded as an authorized suffix rebind and does not grant
retroactive completion credit.

## Validation

- `git diff --check -- .oracle/tasklist.md .oracle/status.md` passed.
- The old tasklist SHA above was verified before mutation.
- New tasklist and status SHA-256 values above were computed after mutation.
- This rebind record is an Oracle planning artifact; its final SHA is reported
  after this file is written and does not participate in its own preimage.
