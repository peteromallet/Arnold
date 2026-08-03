# Cross-pipeline remediation ledger

This is the durable source of truth for the 2026-08-03 Critique recovery and the
pipeline-wide adherence audit. A row is not `fixed` until it names an integration
commit, focused verification, and retirement or reachability proof. Raw Luna
reports are evidence inputs, not authority; findings may be accepted, merged,
rejected, or deferred after parent review.

## Status vocabulary

- `auditing`: evidence collection is incomplete.
- `accepted`: evidenced and admitted to the remediation graph.
- `fixing`: mutation-authorized Luna work is active.
- `fixed-local`: integrated and verified locally, not cloud-canary proven.
- `proven-cloud`: deployed and proven across the relevant topology.
- `follow-up`: deliberately outside the Critique relaunch gate, with an epic task.
- `rejected`: unsupported, duplicate, unreachable, or worse than the canonical design.

## Definitive ledger

| ID | Severity | Finding / invariant breach | Scope | Status | Fix / evidence | Remaining proof |
|---|---|---|---|---|---|---|
| MP-001 | P0 | Watchdog report writes could expose partial JSON and collapse status collection | cross-pipeline status | fixed-local | `c3b0be1398` | cloud crash-write canary |
| MP-002 | P0 | Critique adapter discarded supported metadata and could synthesize false zero-findings | critique transport | fixed-local | `f69bf6c880` | provider canary with preserved payload |
| MP-003 | P0 | Failure identity collapsed distinct attempts and accepted stale results | orchestration | fixed-local | `abce65bef8` | restart/incarnation canary |
| MP-004 | P0 | Notification occurrence was not durably established before provenance resolution, causing repeated alerts | notification/escalation | fixed-local | `952b7b3eca` | same-occurrence replay and Discord quietness |
| MP-005 | P0 | Provider schema dialect and typed failure routing were incomplete | all model phases | fixed-local | `f401431b7a`, `b168edbca0`, `18b279f5ef` | GLM/DeepSeek/Sol live canaries |
| MP-006 | P0 | Finalize expected inline capture, rejected a valid artifact receipt, used the wrong post-handler schema, and retried outside the inner budget | Finalize | fixed-local | `3b71e91b7d`, `5ce4605a33` | adopt recovered artifact under a new immutable attempt |
| MP-007 | P0 | Bare PID evidence and foreign PID namespaces could report a live runner dead | status/liveness | fixed-local | `f39e0133ae`, `cfc65d7b76` | real sibling-container test |
| MP-008 | P0 | Repair claim/lock paths could reclaim a foreign-container owner and create duplicate fixers | repair/fixer | fixed-local | integration `9ceacd85de`; source `d4eb9ddb6d`; 205 focused tests | real sibling-container contention canary |
| MP-009 | P0 | Current-target consumers independently converted incomplete/foreign evidence into booleans that authorized repair, retrigger, or escalation | status → repair/escalation | fixed-local | integration `c694c06f0c`; source `8cece78a36`; 569 focused tests | shell-wrapper cutover and publisher parity |
| MP-010 | P0 | Active-step orphan recovery or state-load reconciliation can treat foreign/unknown custody as dead and redispatch or erase the effect | execute/runtime | fixed-local | integration `3a0f1496d2`, `82ea057edd`; source `49bdac1a95`, `d313f8ef3f`; source suite 189 passed, 1 platform skip | combined rerun, Linux SIGSTOP, real sibling-container canary |
| MP-011 | P1 | Legacy status reducers and shell wrappers can bypass canonical bound liveness | CLI/wrappers | fixed-local | integration `c544ac6866`; source `a0d927b096`; 258 current-target/auditor tests plus all 394 wrapper cases covered green | combined suite and sibling-container cloud canary |
| MP-012 | P1 | Plan/auto launch paths may not publish the same bound owner lease as chain runs | launch/runtime | fixed-local | integration `9a3a7aa6e7`; source `b1cd719502`; 50 merged focused tests + 499 source tests | full combined suite and cloud plan/chain/epic canary |
| MP-013 | P1 | Historical tmux/status fields remain operator-visible despite being non-authoritative | status UX | accepted | MP-009 audit gap | wording/schema migration; no control consumers |
| MP-014 | P1 | Hermes/Shannon occurrence-wide retry and artifact handoff parity is not yet proven | provider runtime | accepted | Finalize adversarial review | parity implementation/tests or rejection with proof |
| MP-015 | P1 | Atomic JSON and primary-corrupt fallback behavior are not universal | persistence/projection | auditing | 50-cell Luna audit | enumerate writers/readers, consolidate, fault injection |
| MP-016 | P1 | Runtime/profile provenance is not universal across plan, epic, watchdog, and resident launch | launch/provenance | auditing | 50-cell Luna audit | dependency-closed launch identity contract |
| MP-017 | P1 | Incident version/dedupe rules may still contain hard-coded or payload-conflict bypasses | notification/escalation | auditing | 50-cell Luna audit | occurrence/version tests and canonical writer cutover |
| MP-018 | P1 | M7 cursor reconciliation may not be epoch/incarnation-bound everywhere | event journal | accepted | follow-up epic `340d76a36f` design evidence | implement and prove restart recovery |
| MP-019 | P1 | Stale sibling sessions can be resurrected without explicit lineage/retirement proof | chain/session discovery | auditing | 50-cell Luna audit | lineage admission and negative resurrection tests |
| MP-020 | — | Remaining invariant × surface cells | all pipeline surfaces | auditing | `evidence/adherence-swarm-20260803/raw/` | rolling triage into concrete rows |
| MP-021 | P0 | Default-reachable legacy force-proceed mutates state/debt/projections outside CAS custody | critique/revise/gate | fixed-local | integration `126c6810d2`; source `fdbbefb770`; 287-source-test proof | combined suite and cloud canary |
| MP-022 | P1 | Critique recovery can adopt a pre-existing unbound scratch artifact after current invocation failure | critique transport | fixed-local | integration `1a34a07aaa`; source `a2ca21701a`; legacy fallback deleted | combined/provider canary |
| MP-023 | P1 | Revise/finalize control reads `gate_carry.json` projection without canonical evidence pairing | gate/revise/finalize | accepted | raw audit `a01-s02` | verified gate reader and tamper tests |
| MP-024 | P1 | Critique custody receipts are replaceable and insufficiently bound to iteration/path | critique custody | fixed-local | integration `1a34a07aaa`; v2 create-once receipts; 325 tests, 1 skip | combined gate/clearance canary |
| MP-025 | P1 | Init/run/bridge have split initial-state ownership and may swallow durable persistence failure | prep/plan/runtime bridge | accepted | raw audit `a01-s01` | transactional canonical initializer and failure propagation |
| MP-026 | P1 | Raw `state.json` reads and conditional R1 mode let a declared projection become authority | prep/plan/general state | accepted | raw audit `a01-s01` | unconditional authority reader and direct-reader retirement |
| MP-027 | P1 | Missing/corrupt `prep.json` becomes an empty blast-radius input instead of failing closed | prep/plan | accepted | raw audit `a01-s01` | structured failure plus corrupt/missing tests |
| MP-028 | P0 | Execute merge accepts scoped entries with no dispatch/envelope authority metadata | execute merge | fixed-local | integration `686c8f93cc`; source `f65274200d`; 101 focused tests | combined Execute/replay suite and cloud canary |
| MP-029 | P0 | Execute recovery adopts latest unbound scratch/checkpoint and stamps it with current authority | execute provider recovery | fixed-local | integration `686c8f93cc`; unbound Hermes recovery deleted | provider malformed-output/restart canary |
| MP-030 | P0 | Top-level artifact evidence can synthesize done/check acknowledgement outside accepted envelopes | execute evidence | fixed-local | integration `686c8f93cc`; mutator/callers deleted | combined mutation tests |
| MP-031 | P1 | Epic child disagreement preserves projection-derived complete and advances parent | review/epic chain | accepted | raw audit `a01-s05` | validated child acceptance and fail-closed disagreement |
| MP-032 | P1 | Shadow/supervisor completion writers remain live beside CAS acceptance | chain completion | accepted | raw audit `a01-s05` | sole CAS writer and legacy-mode retirement |
| MP-033 | P1 | Cloud status accepts receipt-shaped dictionaries without canonical receipt validation | status/chain | accepted | raw audit `a01-s05` | canonical validator cutover and forgery tests |
| MP-034 | P1 | Review may transition done when required provider/evidence is unavailable | review | accepted | raw audit `a01-s05` | explicit evidence policy and transactional binding |
| MP-035 | P0 | Auto performs an unlocked stale whole-document rewrite of `finalize.json`, which can erase concurrent execution evidence/status | Finalize/Execute boundary | fixed-local | integration `c833ba5961`; source `c89f67d535`; plan lock + hash/version CAS + owner field allowlists | combined suite and cloud stale-writer/adoption canary |
| MP-036 | P1 | Post-Finalize execution, timeout, merge, and backstop paths independently rewrite `finalize.json` without one typed mutation owner | Finalize/Execute boundary | fixed-local | integration `c833ba5961`; all live writers migrated; direct-writer inventory test | installed writer inventory and Execute mutation canary |
| MP-037 | P1 | Finalize model call is marked mutable, disabling configured provider fallback | Finalize provider routing | accepted | raw audit `a01-s03` | explicit model-only fallback capability and provider matrix |
| MP-038 | P1 | Finalize promotion evidence attests the persisted schema rather than the model-capture schema and is not durable | Finalize evidence | accepted | raw audit `a01-s03` | correct schema binding and receipt persistence |
| MP-039 | P0 | `arnold-chain` treats failed, empty, malformed, or incomplete acceptance-gate output as permission to launch | launch/runtime | fixed-local | integration `2f219f88f6`; source `d7ccabd4e4`; 81 focused/adjacent tests | direct-route audit and cloud launch canary |
| MP-040 | P1 | Remote session markers and launch materialization have duplicate writers and a check/write/start race | launch/runtime | accepted | raw audit `a01-s06` | one lock/CAS launcher and winner-bound marker |
| MP-041 | P1 | `last_chain.json` projection can route pause/resume and status mode | cloud CLI | accepted | raw audit `a01-s06` | canonical marker lookup; projection non-authoritative |
| MP-042 | P1 | Cloud launcher directly unlinks canonical chain state outside chain lifecycle custody | chain launch/reset | accepted | raw audit `a01-s06` | owner/CAS reset API and race tests |
| MP-043 | P1 | Relaunch and child-agent helper failures are advisory/fail-open in watchdog/repair wrappers | repair/launch | accepted | raw audit `a01-s06` | fail-closed helper contract; dependency on MP-011 wrapper work |
| MP-044 | P1 | Synchronous Hermes compatibility path can run mutation-bearing work without a managed manifest | resident delegation | accepted | raw audit `a01-s06` | enforce read-only or route through managed launcher |
| MP-045 | P0 | Watchdog repair/relaunch still has independent raw tmux/PID/process reducers that can bypass canonical liveness | watchdog control | fixing | raw audit `a01-s07`; overlaps active MP-011 Luna wrapper cutover | verify all mutation callers removed after integration |
| MP-046 | P0 | Watchdog directly deletes canonical session/tracking artifacts instead of using hash-bound retirement/tombstones | status retirement | accepted | raw audit `a01-s07` | canonical retirement API and concurrent-marker tests |
| MP-047 | P1 | Status snapshot/provider status can report running/complete from unbound probes or watchdog projections | status UX | fixing | raw audit `a01-s07`; overlaps MP-011/MP-013 | canonical reducer cutover and tamper tests |
| MP-048 | P1 | Missing or malformed runner-fence record can still allow an otherwise valid lease to report live | liveness lease | accepted | raw audit `a01-s07` | fail UNKNOWN/degraded and fence-corruption tests |
| MP-049 | P0? | Canonical simple-fixer delegation may acquire a filesystem occurrence claim without mandatory Custody lease validation | repair authority | auditing | raw audit `a01-s08`; architecture validation required before admission | prove intended Custody owner/publisher and avoid disabling all repair |
| MP-050 | P0 | Watchdog/repair classifier can label delegation without invoking the canonical delegate, then launch a mutation-capable managed worker | repair dispatch | accepted | raw audit `a01-s08`; overlaps MP-043 | actual delegation receipt/lease gate or typed rejection |
| MP-051 | P0 | Meta-repair provider/retrigger paths remain alternate mutation owners outside canonical simple-fixer delegation | meta repair | accepted | raw audit `a01-s08` | read-only diagnosis split plus one canonical mutation funnel |
| MP-052 | P0 | Notification store exposes a parallel local authority transition without canonical incident/Run Authority custody | notification authority | fixed-local | integration `4d8783f7b8`; source `eb387a3590`; direct mutators removed | combined incident/effect tests and cloud delivery canary |
| MP-053 | P0 | Legacy repair loop directly sends Discord and turns delivery sidecars into manual-review authorization | notification/manual review | fixed-local | integration `e32fd243e5`; source `ad39f0f6bb`; direct sender/ledger writer deleted | combined cloud delivery canary |
| MP-054 | P1 | Two notification effect identities exist; one lacks a consumer and could strand or later duplicate delivery | notification delivery | fixed-local | integration `4d8783f7b8`; legacy destination tombstoned; resident effect sole active path | verify migration and single provider outcome |
| MP-055 | P1 | Notification occurrence metadata and event/outbox intent are committed in separate transactions | notification persistence | fixed-local | integration `4d8783f7b8`; projection recovered from canonical event | crash-boundary combined tests |
| MP-056 | P1 | Provider attempt/receipt tables accept unbound caller data outside canonical effect reservation/custody | notification provider | fixed-local | integration `4d8783f7b8`; EffectProtocol reservation/custody binding | forged-input combined tests |
| MP-057 | P1 | Dormant but executable repair-loop helpers directly rewrite plan/chain state outside canonical transition owners | legacy repair wrapper | accepted | raw audit `a01-s10` | delete helpers and static zero-writer proof |
| MP-058 | P1 | Repair dispatch gives a read-only shadow recovery projection precedence over canonical run state | repair classification | accepted | raw audit `a01-s10` | diagnostic-only recovery view; exact canonical provenance required |
| MP-059 | P1 | Watchdog/supervisor/meta/CLI/auditor choose targets by mtime or fallback location, affecting repair and recovery events | target resolution | accepted | raw audit `a01-s10` | exact current-target resolver; no implicit-latest paths |
| MP-060 | P2 | State-reader conformance test scans a nonexistent source tree and therefore proves nothing about live wrappers | conformance tests | accepted | raw audit `a01-s10` | correct scan root and wrapper coverage |
| MP-061 | P1 | Prep subphases and prep→plan consumption lack one enforced run/attempt/version/provider identity and upstream hash | prep/plan provenance | accepted | raw audit `a02-s01`; overlaps MP-025–MP-027 | one durable decision identity; do not bind durable artifact validity to ephemeral PID liveness |
| MP-062 | P1 | Plan completion/phase-result cleanup may clear or overwrite a replacement invocation when the effective run ID is not used | plan lifecycle | auditing | raw audit `a02-s01`; revalidate against integrated MP-010 fixes | exact-occurrence CAS clear and regression test |
| MP-063 | P1 | Generic plan recovery and duplicate provider parsers can admit unbound `plan_output.json`/extracted prose | plan provider handoff | accepted | raw audit `a02-s01` | canonical attested artifact seam and parser retirement |
| MP-064 | P1 | Generic receipts hard-code attempt `1` and omit the decision occurrence/version identity | receipt provenance | accepted | raw audit `a02-s01` | derive attempt/identity from active occurrence |
| MP-065 | P0 | Critique/gate custody was content-bound but not current invocation/attempt/provider-bound | critique control custody | fixed-local | integration `1a34a07aaa`; v2 strict binding used by gate/clearance/finalize | Hermes per-attempt path attestation follow-up; cloud provider canary |
| MP-066 | P0 | Gate signals/prompts/audits read historical critique artifacts directly without custody validation | gate decision inputs | accepted | raw audit `a02-s02` | one custody reader and zero direct production readers |
| MP-067 | P1 | Gate schema-parity failure is recorded but does not block the authority decision | gate schema contract | accepted | raw audit `a02-s02` | fail closed or prove non-authoritative compatibility scope |
| MP-068 | P1 | Finalize copies unbound gate/carry projection decisions into new projections | Finalize control projection | accepted | raw audit `a02-s02`; overlaps MP-023/MP-038 | canonical gate custody reader and identity pairing |
| MP-069 | P1 | Auto routes from a changed same-phase `phase_result.json` before proving its invocation is the admitted current occurrence | phase-result routing | accepted | raw audit `a02-s03` | current-invocation check before any retry/escalation decision |
| MP-070 | P0 | Review freshness/provider evidence is advisory, so stale, missing, or unverifiable evidence can authorize review→done | review acceptance | accepted | raw audit `a02-s05`; overlaps MP-034 | explicit required-evidence policy; no state mutation on stale/missing required evidence |
| MP-071 | P1 | Cloud/managed chain runtime binding and attestation are optional, allowing authority-bearing work without exact deployed runtime/profile provenance | cloud launch | accepted | raw audit `a02-s06` | require binding for managed cloud runs while preserving explicit local development mode |
| MP-072 | P1 | Epic launch ignores runtime refresh failure and bootstrap bypasses the standard binding path | epic/bootstrap launch | accepted | raw audit `a02-s06` | fail closed refresh; one attested launch path |
| MP-073 | P0 | Cloud supervisor consumes targeted CLI status derived from raw tmux/`ps`, allowing unbound running/dead status to suppress or trigger restart | cloud supervise | fixed-local | integration `b21689474d`, strict follow-up `47e2eaff0a`; source `aabb7760a5`, `3d1c3edbf1`; 370 adjacent, 99 final relevant, and 7 strict-fallback tests green | combined exact-target sibling-container canary |
| MP-074 | P0 | Repair request/claim and simple-fixer occurrence do not require one run/revision/attempt/custody-epoch identity | repair admission | fixed-local | integration `ddd72c446e`; source `aa63af68fa`; terminal mirror and trigger consume only persisted canonical identity; stale-claim seizure and identity-free PR-wait enqueue retired; 468 focused + 39 producer/static + 394 wrapper tests green | installed automatic-fixer canary |
| MP-075 | P0 | Authoritative repair lease validation compares host/PID but omits process-start/PID-namespace incarnation | repair lease | fixed-local | integration `3fc9d0a4e4`; source `3d1da3913e`; exact host/PID/boot/PID-namespace/process-start validation | combined sibling-container/reuse canary |
| MP-076 | P1 | In-process fixer attempts are recorded as managed child launches with fabricated manifest identity | repair status | accepted | raw audit `a02-s08` | distinct in-process attempt schema/status and truth-firewall parity |
| MP-077 | P1 | Terminal audit fabricates independent/fresh progress without occurrence-bound pre/post evidence | repair terminal audit | accepted | raw audit `a02-s08` | real target capture and evidence comparison or remain non-accepting |
| MP-078 | P1 | Finalize provider, structural-repair, outer-auto, and restart retries do not consume one durable occurrence-wide budget | Finalize retry/effects | follow-up | raw audit `a03-s03`; attempt-local receipt/handoff fixes already in `3b71e91b7d` | durable semantic-occurrence budget and replay tests; not required to adopt the valid attempt-7 candidate in clean attempt 9 |
| MP-079 | P1 | Generic execution effects/provider fallbacks have split idempotency keys and can bypass the canonical effect protocol | cross-pipeline Execute | follow-up | raw audit `a03-s04`; Critique Execute artifact authority fixed in `686c8f93cc` | consolidate generic effect routing, compensation, escalation, and provider fallback; remote-side-effect canary |
| MP-080 | P0 | Notification adapter failure or ambiguous provider outcome can fall through to a direct Discord send, bypassing durable effect identity and recreating duplicate messages | notification delivery | fixed-local | integration `e32fd243e5`; source `ad39f0f6bb`; 187 tests including 200 polls, restart, adapter failure, and lost ACK | combined cloud delivery/no-spam canary |
| MP-081 | P0 | Simple-fixer mutation budgets reset after process/session/claim release and mutation effects lack a durable occurrence-wide idempotency record | repair/fixer | fixed-local | integration `b976ab4cda`; source `96f8c44b03`; 90 tests including interpreter restart, two-container contention, crash/timeout, and claim reacquisition | combined cloud automatic-fixer canary |
| MP-082 | P1 | Launch, resident, repair, scheduler, and reset paths keep independent retry budgets instead of one occurrence policy | launch/runtime/effects | follow-up | raw audits `a03-s06`, `a03-s09` | shared budget service after MP-081 proves canonical repair implementation |
| MP-083 | P0 | SSH provider status invokes `arnold status --plan`, but that executable is the native Arnold CLI rather than Megaplan; live status fails before canonical liveness can be read | cloud status/supervisor | fixed-local | integration `b21689474d`, `47e2eaff0a`; exact attested module route and canonical runner projection; missing marker/runtime remains degraded; raw probes diagnostic-only | installed CLI-collision and supervisor fail-closed canary |
| MP-084 | P0 | The preserved r5 session marker predates managed runtime/run identity, so supported runtime-cutover CAS correctly refuses to repoint it | cloud cutover | fixed-local | integration `77eed1769e`, live-shape correction `0cd025b2e2`; source `eb5596a93a`, `6e126eb2de`; migration now requires both canonical chain spec fields to match the live r5 shape; 18 focused runtime-cutover tests | execute exact live migration only after candidate provenance is generated and verified |
| MP-085 | P0 | Exactly-once `DeliveryEffects` exists but production resident constructors do not inject it, leaving autonomous completion/subagent sweeps on the direct Discord path | notification production wiring | fixed-local | integration `6d8e131c4c`; source `662a93f036`; real constructor + 200 polls across restart = one provider attempt; 218 focused/adjacent tests | installed resident restart/no-fallback/no-spam canary |
| MP-086 | P0 | `partnered-5-glm` has a GLM Execute default but tiers 1–6 override it with DeepSeek, and existing plans retain the old tier table after a registry deploy | profile/routing | fixed-local | integration `6d4314207d`, persisted-refresh `57af2dd119`; tiers 1–10 direct Zhipu GLM 5.2 → Fireworks GLM 5p2 → direct Zhipu; same-profile refresh has before/after routing hashes and preserves gated/cancellation/chain/WBC custody; 12 control-binding tests | execute receipted refresh and installed profile-resolution canary |
| MP-087 | P0 | Resuming the chain from `gated` permits three identical deterministic Finalize invocations, so attempt-9-only is not enforced by external retry settings | Finalize launch control | fixed-local | integration `6d4314207d`; direct CLI/WBC proof: cancelled ordinal 8 creates exactly one ordinal 9; success→finalized/Execute, failure→gated terminal/no attempt10; 146 adjacent tests | use the proven one-shot command during cutover before chain resume |
| MP-088 | P0 | Same-named user/project profiles can silently shadow the reviewed built-in registry during a same-profile refresh | profile registry custody | proven-cloud | integration `73b9dba2ea`; receipts bind selected layer, effective digest, and ordered candidate hashes; project profile fixed in product `b9add7e867`; live refresh bound source `project` and digest `2c1dabb0cab708f7131d14221f79e4ba1be8dc6a311546be2318f348d8ab548c` with GLM-only Execute tiers 1–10 | retain legitimate overlays and add an installed source-shadow regression canary |
| MP-089 | P0 | AgentBox terminal completion bypasses the resident `DeliveryEffects` ledger and can duplicate Discord DMs after restart or ambiguity | notification delivery | fixed-local | integration `a5d4d03738`; stable operation/state occurrence key, persistent owner, no direct fallback; 107 focused tests | installed AgentBox completion/restart canary |
| MP-090 | P0 | The public phase-WBC cancellation API assumes in-process writer registration, so exact recovery cancellation fails from a fresh operator process | recovery custody | proven-cloud | integration `b2cef1d43f`; controlled writers bootstrap before the guarded append; exact live attempt 8 now `STARTED(1) → CANCELLED(2)` with active custody cleared | retain a fresh-process crash/replay regression canary |
| MP-091 | P0 | Strict v2 critique producer custody made intact pre-v2 plans impossible to finalize, but the missing historical producer invocation cannot be reconstructed honestly | critique custody migration | fixed-local | integration `e0ad1811a2` plus lifecycle correction `128b8f03ac`; create-once `legacy_unbound` sidecars bind exact v1 receipts, artifacts, gate/clearance lineage and authority limits without rewriting history; migration→clearance lifecycle tests pass | run the exact-SHA migration for live r5 iterations 1 and 2 under runtime `b38460e4d3`; prove original bytes unchanged and Finalize custody roundtrip |
| MP-092 | P0 | Parallel Critique bypasses the phase worker wrapper, inherits a stale invocation, and same-model fanout units collide because worker-dispatch identity lacks a unit key | critique phase/worker WBC | fixed-local | integration `b38460e4d3`; every parallel Critique owns a fresh phase WBC, stable per-check `dispatch_key`, terminal child manifest, and reducer-to-ledger binding; 261 focused tests and 118 combined incident tests pass | cloud canary on the next Critique phase, including same-model fallback/replay |
| MP-093 | P1 | Chain-state projection appends repeatedly report a cursor record-count/digest regression while canonical state remains intact | chain event projection | follow-up | observed on r5 pause/resume: `645→640` then `653→649`; mutation correctly continued against intact canonical state | reconcile projection cursor under canonical owner; prove no authority consumer trusts the stale projection |
| MP-094 | P1 | A session-bound resident can be exactly attested while global watchdog/auditor/supervisor selectors still point at another runtime, creating a split installed topology | runtime release/selectors | follow-up | resident epoch `critique-attempt9-b384-20260804-0115` is healthy and binds exact runtime `b38460e4d3f2605b341fa117dc838c6e51a1d3c8`, tree `f0acc45ff8f726d38e67fa665179b65353bac336`, and identity digest `21ff19b6bd117b18f85643781b999167c4b8eb882601a5e77d9b3c9858eff476`; r5 chain+marker are bound separately | after r5 enters Execute, atomically promote and attest all long-lived global selectors; reject mixed-generation service startup |

## Rolling disposition log

| Time (Europe/Berlin) | Input | Disposition |
|---|---|---|
| 2026-08-03 20:55 | P0 repair ownership Luna implementation | Accepted, integrated as `9ceacd85de`, remains `fixed-local` pending real two-container canary. |
| 2026-08-03 20:55 | P0 bound current-target liveness Luna implementation | Accepted, integrated as `c694c06f0c`; explicit wrapper/publisher gaps split into MP-011–MP-013. |
| 2026-08-03 20:58 | Combined MP-008/MP-009 regression | 224 tests passed on the integration head across repair lock/request, current target/liveness, repair goal, terminal audit, and progress-auditor paths. |
| 2026-08-03 21:01 | P0 active-step incarnation Luna implementation | Integrated as `3a0f1496d2`; conflict resolved by retaining full lease identity plus target PID; 53 combined tests passed, 1 Linux-only skip. |
| 2026-08-03 21:02 | Raw audits `a01-s01`, `a01-s02` | Accepted MP-021–MP-027; immediate P0 force-proceed fixer dispatched. P2 duplicates remain source inputs pending deduplication. |
| 2026-08-03 21:05 | Raw audits `a01-s04`, `a01-s05` | Accepted MP-028–MP-034. P0 Execute single-owner Luna fixer launched immediately; P1 review/chain work dependency-queued. |
| 2026-08-03 21:05 | P0 active-step follow-up | Integrated `82ea057edd` so state-load reconciliation also preserves LIVE/UNKNOWN custody; source suite 189 passed, 1 skip. |
| 2026-08-03 21:07 | Raw audit `a01-s03` | Accepted MP-035–MP-038. MP-035 is P0 but overlaps the active Execute-authority fixer in `auto.py`/execute writers, so it is dependency-queued rather than creating conflicting concurrent edits. |
| 2026-08-03 21:10 | Raw audit `a01-s06` | Accepted MP-039–MP-044. Immediate isolated Luna fixer launched for non-overlapping P0 MP-039; broader wrapper/marker items dependency-queued. |
| 2026-08-03 21:14 | Raw audits `a01-s07`–`a01-s09` | Accepted/merged MP-045–MP-056. MP-049 remains explicitly unadmitted pending owner/publisher proof; MP-054 downgraded to P1 because the second path currently has no consumer. Existing wrapper work absorbs overlapping findings. |
| 2026-08-03 21:17 | Raw audit `a01-s10` | Accepted MP-057–MP-060; these are dependency-queued behind active wrapper/current-target consolidation. Dormant direct writers must be deleted, not wrapped. |
| 2026-08-03 21:26 | Raw audits `a02-s01`, `a02-s02` | Accepted/merged MP-061–MP-068. Parent narrowed the proposed identity: durable artifacts bind to run/attempt/version/provider and hashes, while PID namespace/liveness remains mutation-custody evidence rather than making restartable evidence invalid. |
| 2026-08-03 21:29 | Raw audit `a02-s03` | Merged Finalize-writer and receipt findings into MP-035/MP-036/MP-038/MP-064; added MP-069. Parent again rejected making PID liveness part of durable artifact validity. |
| 2026-08-03 21:29 | Canonical force-proceed | Integrated as `126c6810d2`; legacy writer deleted and unconditional CAS custody route proven by 287 tests on the source branch. |
| 2026-08-03 21:33 | Canonical wrapper liveness | Integrated as `d15d107889`; legacy process evidence is diagnostic-only and cannot authorize repair/retrigger/escalation/relaunch/retirement. |
| 2026-08-03 21:39 | MP-011 broader regression | Parent rejected over-fencing: 39 broader wrapper failures showed UNKNOWN suppressing legitimate read-only status/lifecycle behavior. Luna redirected to split observation from mutation and run the full wrapper suite. |
| 2026-08-03 21:42 | Raw audits `a02-s05`–`a02-s07` | Merged duplicate review/epic/liveness findings and accepted MP-070–MP-073. Parent scoped runtime binding to managed cloud authority, not every local developer invocation. |
| 2026-08-03 21:45 | Raw audits `a02-s04`, `a02-s08` | Execute replay finding merged into active MP-028–MP-030 fixer. Accepted MP-074–MP-077; parent limits durable repair identity to run/revision/attempt/custody epoch and mutation incarnation, not provider trivia. |
| 2026-08-03 21:49 | Critique artifact custody | Integrated `1a34a07aaa`; stale scratch adoption deleted and create-once v2 receipts bind current iteration/invocation/attempt/provider/path/hashes. V1 migrates by quarantine+rereun, not synthesis. |
| 2026-08-03 21:52 | Execute, chain gate, notification authority | Integrated `686c8f93cc`, `2f219f88f6`, `4d8783f7b8`. External Luna sandboxes could not update Git refs, so parent verified diff state and created commits before cherry-pick. Residual legacy Discord wrapper remains MP-053. |
| 2026-08-03 21:58 | Owner-lease publisher parity | Integrated `9a3a7aa6e7`; conflict resolution preserves schema-v2 managed identity, single publisher flock, monotonic active-step fence, and diagnostic-only markerless tmux discovery. |
| 2026-08-03 22:10 | Bounded Luna audit completion | All 25 judgment-selected authority, identity, and highest-risk retry/effect cells completed with zero launcher failures. The matrix is closed; further exploration now requires a concrete uncovered path. |
| 2026-08-03 22:14 | Retry/effect audit triage | Accepted MP-080/MP-081 as relaunch gates because they can repeat user-visible effects or fixer mutations after ambiguous/restarted attempts. Deferred generalized Finalize/Execute/launch budget unification as MP-078/MP-079/MP-082; those do not block clean candidate adoption and initial GLM Execute progress. |
| 2026-08-03 22:33 | Installed SSH status probe | Accepted MP-083 and merged it with MP-073 implementation scope. `SshProvider.status_payload()` invokes the wrong CLI family on the live runner; the replacement must be runtime-attested and must not restore raw tmux/process authority. |
| 2026-08-03 22:55 | Finalize transactional authority | Integrated `c833ba5961` (source `c89f67d535`). All `finalize.json` mutations now use one locked hash/version CAS seam with field ownership and committed immutable history; exact attempt/invocation cancellation was added for attempt 8. Source reported 279 tests; parent reran the new authority/WBC slice: 17 passed. |
| 2026-08-03 23:04 | Canonical wrapper regression closure | Integrated `c544ac6866` (source `a0d927b096`). UNKNOWN continues to fence authority-bearing mutation while terminal/manual-review/status observation remains available; 258 current-target/auditor tests and all 394 wrapper cases are covered green. |
| 2026-08-03 23:06 | Notification exactly-once closure | Integrated `e32fd243e5` (source `ad39f0f6bb`). Selected DeliveryEffects now fail closed, ambiguous/lost acknowledgements persist as `INDETERMINATE`, the legacy repair-loop sender is retired, and stable identities dedupe 200 polls plus restart to one provider call; 187 tests passed. |
| 2026-08-03 23:14 | Repair occurrence and lease authority | Integrated `3fc9d0a4e4` (source `3d1da3913e`). Canonical normalized occurrence/grant/custody identity now spans lifecycle publication, queue, claim, dispatch, delegation, and simple-fixer mutation; exact process incarnation is required. The positive managed path and 340 focused tests are green. Parent keeps MP-074 open until old identity-free producers are migrated or explicitly retired; they will not be made claimable by weakening the boundary. |
| 2026-08-03 23:17 | Legacy r5 runtime-marker cutover blocker | Accepted MP-084. The preserved r5 marker has neither managed `run_id` nor runtime binding, while its relaunch command is pinned to the old candidate. Fresh-session restart is forbidden because the plan can continue; the fix is a narrow external-provenance-bound CAS migration, not a manual marker rewrite. |
| 2026-08-03 23:28 | Durable repair budget | Integrated `b976ab4cda` (source `96f8c44b03`). The sole simple-fixer runner now reserves mutation in a canonical-occurrence SQLite CAS ledger; completion is adopted and ambiguous/crashed reservations become non-redrivable `INDETERMINATE`. Ninety focused/adjacent tests passed. |
| 2026-08-03 23:29 | Canonical cloud status and supervisor | Integrated `b21689474d` (source `aabb7760a5`). SSH status uses the exact Megaplan module runtime; status exposes canonical current-target liveness; every supervisor relaunch/advance site requires the exact dead target while raw tmux/`ps` stays diagnostic. 370 adjacent and 99 final relevant tests passed. |
| 2026-08-03 23:30 | Strict status fallback and legacy-marker migration | Integrated strict status follow-up `47e2eaff0a` and migration `77eed1769e` (sources `3d1c3edbf1`, `eb5596a93a`). Missing/unreadable selected runtime stays degraded; the r5 legacy marker can be upgraded only through independently reverified provenance and nine exact CAS guards. |
| 2026-08-03 23:36 | Merged notification wiring gap | Accepted MP-085 as a relaunch blocker. The effect protocol and injected tests were correct, but the production resident factory never constructed/injected `DeliveryEffects`; autonomous notifications could therefore still use direct Discord. A dedicated Luna production-wiring fix is active. |
| 2026-08-03 23:40 | Merged profile and Finalize launch gaps | Accepted MP-086/MP-087 as relaunch blockers. The actual Execute tier resolver overrides the flat GLM route with DeepSeek for tiers 1–6, and whole-chain resume can make three deterministic Finalize calls. The bounded route is GLM-only Execute tiers plus one direct WBC-backed attempt-9 Finalize before chain resume. |
| 2026-08-03 23:47 | Production notification effect owner | Integrated `6d8e131c4c` (source `662a93f036`). The real resident factory now constructs one persistent effect owner and injects autonomous scheduled/reset/completion/subagent paths; missing owner/adapter fails closed and only explicit interactive replies stay direct. Across 200 polls and restart the provider ran once; 218 tests passed. |
| 2026-08-03 23:49 | GLM Execute and one-shot attempt 9 | Integrated `6d4314207d` (source `da13155beb`). Every Execute tier is GLM-family; DeepSeek remains critique/gate and Sol high remains Finalize. Direct CLI/WBC tests prove one ordinal-9 invocation with success→Execute or terminal failure→no attempt10; 146 adjacent tests passed. |
| 2026-08-04 00:46 | Exact cloud cutover reached custody preflight | Obsolete r2/r3 sessions were durably paused; the frozen attempt-8 process incarnation was killed by exact PID/start guards; r5 was paused; attempt 8 was durably cancelled; marker and chain were migrated/rebound to content-addressed runtime `a5d4d03738`; the resident recovered healthy on that exact runtime. No attempt 9 was created. |
| 2026-08-04 00:48 | Project profile shadow exposed | The new source guard found the project-owned `partnered-5-glm` overlay still routed Execute tiers 1–6 to DeepSeek. The authoritative project profile was updated in product commit `b9add7e867`; the supported same-profile refresh then bound source `project`, digest `2c1dabb0…`, Finalize Sol/high, and GLM-only Execute tiers 1–10. |
| 2026-08-04 00:50 | Legacy custody compatibility stop | Direct Finalize stopped before WBC/model dispatch because both accepted r5 critique receipts predate producer binding. Independent forensics verified every receipt/artifact/gate hash and proved the missing invocation cannot be reconstructed. MP-091 adds an explicit `legacy_unbound` migration instead of fabricating v2 authority. |
| 2026-08-04 01:04 | Parallel Critique root-under-root | Forensics proved the current scatter path never establishes a Critique phase occurrence, and its worker-dispatch identity cannot distinguish same-model lenses. MP-092 is now a relaunch gate because later epic milestones would otherwise repeat the custody defect. |
| 2026-08-04 01:15 | Final root-fix candidate admitted | Integration `b38460e4d3f2605b341fa117dc838c6e51a1d3c8` (tree `f0acc45ff8f726d38e67fa665179b65353bac336`) contains MP-091 lifecycle-safe legacy migration and MP-092 parallel-Critique WBC/manifest binding. Its isolated cloud runtime identity is `21ff19b6bd117b18f85643781b999167c4b8eb882601a5e77d9b3c9858eff476`; 118 critical cloud tests passed. This admits the candidate, not attempt 9 or Execute success. |
| 2026-08-04 01:17 | Exact resident and r5 runtime custody | Resident epoch `critique-attempt9-b384-20260804-0115` recovered `healthy/discord_ready`, listener-only, on exact `b38460e4d3`; chain and marker were rebound to the same identity while `should_run=false`. Global watchdog/auditor/supervisor selector promotion is deliberately MP-094 follow-up, not silently inferred from the session binding. |
| 2026-08-03 20:49 | 50-cell Luna audit matrix | Started with five concurrent read-only agents; every completed report will be triaged here before fixer dispatch. |

## Admission and completion rule

For each raw report:

1. Verify cited code and reachability on the integration head.
2. Merge duplicates into one invariant-level item; preserve all source report IDs.
3. Reject speculative or display-only issues incorrectly presented as authority mutation.
4. Order accepted work by dependency and overlapping files.
5. Dispatch Luna with one mutation scope and one worktree per non-overlapping item.
6. Require a commit, focused tests, regression tests, and explicit duplicate-path retirement proof.
7. Integrate, rerun the combined suite, then promote only after the relevant cloud canary.

## Current cutover authority — Attempt 10 quota stop (2026-08-04)

This section supersedes every still-open Attempt-9 relaunch checklist in this
ledger and the linked runbook. Attempt 9 is historical. Attempt 10 was created
and terminated; no checklist that requires “no ordinal 10” or instructs an
Attempt-9 launch remains executable authority.

The deployed root-repair train is:

- `4ab819d7913352f797d8a01a5ea3b00f17e2236f`: exact Finalize response
  handling. Semantic repair receives the authenticated full candidate, terminal
  selection binds the last assistant message to `-o`, and response occurrence
  identity comes from the canonical invocation. Mismatched terminal evidence
  fails closed instead of launching another repair loop.
- `4cf84138de029ca8c2ec654f5a70d58d50cf6b81`: lifecycle projection and
  immutable lineage are no longer conflated. Current bound lifecycle history
  may append through its controlled writer while accepted legacy lineage
  remains immutable.
- `fdbdfb72cb32a1d7c42bc9a0d5f19eba023d5a30`: canonical stop intent is
  preserved by status projection. Explicit `should_run=false` or active
  `operator_pause` renders nonterminal work `paused`, never synthesized
  `running`/`attention`; process facts remain a separate diagnostic dimension.

Cloud attestation admits exact runtime commit
`fdbdfb72cb32a1d7c42bc9a0d5f19eba023d5a30`, tree
`05a77aa883d06df09d745b01047e64d1f75e8267`, runtime-identity digest
`d1f9cd20568f3fe325ea384c7adf7df8d9bba61de651ef95011e51361bf71a7b`,
and launch-seed `content_sha256`
`7cd0f51f2ec028418209bb0511e4c70b3791b0ad2b8c070766f56ef6130f7504`.
Resident epoch `critique-attempt10-fdb-live-20260804-0149`, container
`8be0aa325b119a00f8c62e7e4a4b2e0cb5e499999759cca4384201469f361430`,
and image
`sha256:78474208a513bfa03c51d6e04f3d31381ae07305b1c291db112098c05ba82c20`
were validated `healthy/discord_ready`, `listener_only=true`. Every future
isolated launch must create the venv with `--copies` and attest the copied
venv interpreter's exact path and digest; a base-interpreter or symlink identity
is not launch authority.

Attempt 10 is an immutable terminal failure, not a WBC completion:

- phase attempt `646ab9ed-2706-5be8-a249-7b52e49ac102`, ordinal `10`,
  invocation `b437b9ee2a8b4c37`, run
  `cl2-wbc-backed-ledger-20260803-1357`, step `finalize`;
- worker-WBC attempt `b0e96460-a8d7-5577-9b5f-4ed080e18c71`, occurrence
  `de3040a3c789bdaa92330e08c5f8ade7cbda3136d8015194e02141d4608678ce`,
  repair-0 receipt
  `sha256:6fa1eac08c732ade7116a3fa30160b807cdc3562388de150156a5bcb582051f4`;
- terminal event `FAILED`, outcome `indeterminate`, typed error
  `quota_exceeded`. Cloud and local Sol probes both hard-failed quota and
  displayed resets on Aug 9 at 11:06 AM and 1:06 PM respectively (the Codex
  display did not specify a timezone). No alternative authorized Sol
  credential exists.

r5 therefore remains `gated`, with no active step, marker `should_run=false`,
and canonical projected status `paused`. Do not resume it and do not retry it in
an automatic, shell, watchdog, or chain loop. The only authorized forward path
is to replenish or explicitly authorize Sol capacity, reattest the same runtime
and copied interpreter, then issue exactly one direct same-model
`codex:gpt-5.6-sol:high` Finalize retry in the same r5. It must create exactly
ordinal 11 with fresh bound IDs. Before any chain resume, require terminal
`COMPLETED` WBC evidence, exact response/publication receipts, and
`finalized -> execute`; then prove GLM-only Execute, one current r5 status row,
and unchanged-poll notification dedupe/no-spam.

The cached `/workspace/.megaplan/status/cloud-status.json` remains a follow-up
freshness defect. `/whats-cooking` currently uses the fresh local snapshot
builder, so the stale cache must not be used as canonical command evidence.
Repair and attest the cache writer/freshness contract separately. This record
does not claim Finalize, Execute, the Critique epic, or this follow-up epic is
complete.
