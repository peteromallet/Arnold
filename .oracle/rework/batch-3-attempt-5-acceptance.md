# Batch 3 attempt-5 acceptance metadata

## Decision and scope

This metadata receipt records the authorized acceptance of NBF-04 and NBF-05
only.  It does not alter their task text or dependencies, and it does not
authorize execution of Batch 4, commit, push, merge, deployment, `main`
mutation, or epic launch.  NBF-08 remains a future-suffix planning task and
its artifacts are not candidate implementation evidence.

- Branch: `reconcile/nbf-attempt4-2297`
- Base/head: `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`
- Accepted tasks: `NBF-04`, `NBF-05`
- Final packet: `.oracle/rework/batch-3-attempt-5-combined-nbf04-nbf05.md`
  SHA-256 `8481da7b8575d98ba4019e1620cfc72b1a9b6b2f26e93e942ce0cdf473e4e792`
- Luna review brief: `.oracle/briefs/review-batch-3-attempt-5-combined-nbf04-nbf05-luna.md`
- Framed aggregate: `7f134a29fee76c1f68436798482dca46a301a380456c0793ce3b2b0ecf80c958`

The status denominator is now 5/8 accepted tasks = 62.5% and 3/6 accepted
batches = 50%.  Batch 3 is complete; the next eligible batch is Batch 4,
NBF-06.  The NBF08 suffix ordering remains Batch 4 NBF-06 → Batch 5 NBF-08
→ Batch 6 NBF-07, as determined by the dependency DAG rather than physical
file order.

## Evidence identities

| Artifact | SHA-256 / identity |
|---|---|
| Candidate manifest, 49 paths | `632acc64daf412220eafeb290f26431122b436a22a5b7aaf1c2a748ce27b2ec0` |
| Python validation | `6ce40640ad901186936285da8861dcefd22d7de4f97985410de3ce726bc3930a` |
| Static/runtime validation | `e56ab2c88a21189d05eab78e672462c7dde54b69586ebb744c483a6c1a4808d5` |
| Inventory, 120 entries | `e92b6c90c6adf7c6d5f05a8d10c888f4900b1a2395cf35ce55689323987568da` |
| Inventory source digest | `60d5d933e722d8f49905b534866e1a2bdb6d0c7766103f3176adacd7cd33a958` |
| Tasklist before acceptance metadata | `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73` |
| North Star | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Plan | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Goal | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| Custody | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| NBF08 suffix rebind | `b2c09eee42da4e1fb251315773ca527aa31cb0e8159bc6b08901ffec59048723` |

The two framed outputs are byte-identical, with 759851 raw diff bytes and
aggregate `7f134a29fee76c1f68436798482dca46a301a380456c0793ce3b2b0ecf80c958`.
The project Python 3.11 safepath test passed 1/1; the stripped Homebrew 3.14
optional-`fire` failure is outside the manifest and receives no acceptance
credit or penalty.  Compile, shell syntax, inventory, focused validation,
and diff checks are recorded in the bound evidence.

## Review and adjudication history

The single Sol review for this segment returned REWORK on authority/custody
and inventory concerns.  Those concerns were remediated through the native
confirmation and cleanup custody fixes, retained-handle and cross-reservation
guards, canonical shell/operator/fan authority, and action-aware inventory
correction.  No second Sol review was commissioned.

All subsequent Luna review rounds were kept independent and evidence-bound;
the attempt-2, attempt-3, attempt-4, and attempt-5 review briefs remain
historical/current review inputs, while this receipt records the final
attempt-5 metadata acceptance.  The accepted NBF-04 attempt-11 packet remains
linked at SHA `83f35cbc29f559d212fd1fc2bad8f8178fabd4d726bb30eafbc3c46a02c83071`
with aggregate `b3945b43cc62136d463745c2c18e2066ee7b1ff8a4d2d81b3c41b4a2c6963f4b`.

## Tasklist/status mutation and exclusions

Only the following metadata was changed: NBF-04 and NBF-05 received explicit
`ACCEPTED` markers tied to the attempt-5 packet; the Batch 3 checkpoint was
marked `PASS — ACCEPTED (attempt 5)`; and the status header was advanced to
Batch 3 accepted with the 5/8 and 3/6 progress math and next-batch pointer.
The accepted prefix before Batch 3, all task text, and all dependency lines
were preserved.  The post-change tasklist SHA is
`a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959`; its
accepted-prefix SHA (bytes before the Batch 3 header) is
`57964293ef9675b6f9c6af155b1b30f681ffa5bc7b46d5abde98a581d99233db`.
The post-change status SHA is
`d1bc45abd8d9bb247e1ce15eec08f7bda37cac3e691b1f2b937ee7dd355c7128`.

Excluded are NBF-06 provider implementation, NBF-08 implementation, source
changes beyond the already-frozen candidate, historical contaminated runs,
M11/babysitter/demo artifacts, commits, pushes, merges, deployments, and
launches.  `git diff --check` passes.  This receipt is ready for the parent
coordinator to review before any later authorized checkpoint action.
