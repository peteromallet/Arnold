# a01-s08-authority-ownership-repair-fixer: authority-ownership × repair-fixer

## Verdict

FAIL. The repository defines a canonical occurrence/mutation path, but several reachable callers treat filesystem locks, managed manifests, or classifier output as authority. The highest-risk gaps are P0 authority mutations; related launch/dispatch records can also misreport status.

## Intended canonical contract

`simple_fixer` is explicitly the single exact-occurrence repair entry point; authority must derive only from the exact F01 tuple, and the fixer must not spawn child agents (`arnold_pipelines/megaplan/cloud/simple_fixer.py:L1-L29`). `CanonicalRunner` is intended to be the sole implementation for immediate and reconciliation mutations (`simple_fixer.py:L789-L803`).

The single delegation funnel is `delegate_to_simple_fixer`, which validates identity, claims the occurrence, runs `CanonicalRunner`, releases the claim, and returns a typed result (`cloud/wrappers/repair_delegation.py:L218-L245`, `L261-L339`). The Custody registry independently states that repair-request queues, locks/leases, loops, and source/install/retrigger paths are Custody-owned, with PID locks downgraded to projections (`custody/controlled_writer_registry.py:L277-L326`).

However, the lock contract says mkdir/PID locks are only admission/projection evidence; authoritative decisions require a current Custody lease (`cloud/repair_lock.py:L1-L19`). Therefore the canonical solution is `delegate_to_simple_fixer` plus lease-backed Custody validation; the current implementation is incomplete because it does not perform that validation.

## Evidence and complete path inventory

I searched with `rg --files` and `rg -n` across `arnold_pipelines/megaplan` and `tests`, then inspected every definition and caller with `nl -ba`. Searches covered `delegate_to_simple_fixer`, `CanonicalRunner`, `acquire/release_repair_lock`, `claim_active_repair_request`, `validate_lease_authority`, `Popen/subprocess/setsid`, `managed_agent`, `retrigger`, `meta_dispatch`, and all authority-gate names.

- Writers: `claim_singleton_occurrence` writes the mkdir lock (`simple_fixer.py:L306-L367`); active request claims use the same primitive (`repair_requests.py:L1596-L1661`); repair-loop and watchdog wrappers launch managed workers (`arnold-repair-loop:L8157-L8200`, `arnold-watchdog:L5077-L5155`); meta-repair launches Codex/Hermes workers (`arnold-meta-repair-loop:L1312-L1377`, `L1532-L1578`).
- Readers/validators: `inspect_repair_lock` supplies PID/liveness evidence; `validate_lease_authority` checks current, unexpired lease ownership by host and PID (`repair_lock.py:L405-L464`); managed launch confirmation reads manifests only (`arnold-watchdog:L447-L494`).
- Canonical callers: manual trigger delegates (`manual_repair_trigger.py:L518-L535`), terminal audit delegates (`terminal_audit.py:L208-L240`), and the normal repair trigger delegates (`arnold-repair-trigger:L1019-L1129`).
- Bypass callers: watchdog and repair-loop authority functions only build/print delegation-shaped JSON (`arnold-watchdog:L4328-L4412`; `arnold-repair-loop:L6403-L6481`), while their callers proceed to launch workers. Meta-repair retrigger invokes `run_managed_command` on `arnold-repair-loop` (`arnold-meta-repair-loop:L2030-L2077`).
- Consumers/projections: repair goals persist request IDs and owner manifests (`repair_goal.py:L1062-L1144`); terminal audit writes records and indexes (`terminal_audit.py:L311-L328`); watchdog status derives “canonical” launch from a managed manifest and status label (`arnold-watchdog:L389-L443`); managed-agent binding records the claim in the manifest (`managed_agent.py:L574-L624`).

## Adherence gaps

1. **P0 — authority mutation: canonical delegation has no authoritative lease gate.**  
   `delegate_to_simple_fixer` calls `claim_singleton_occurrence`, then immediately runs `CanonicalRunner` (`repair_delegation.py:L276-L314`). That claim only calls `acquire_repair_lock` and never supplies a lease store or lease ID (`simple_fixer.py:L343-L367`). The repository-wide call-site search found `validate_lease_authority` only inside lock release/renewal internals and tests (`repair_lock.py:L467-L474`, `L518-L531`; `tests/cloud/test_repair_lock.py:L853-L964`), not in the canonical mutation path. Thus a valid mkdir owner can mutate while expired, fenced, or absent from Custody.

2. **P0 — authority mutation: active claims and stale reclamation bypass Custody.**  
   `claim_active_repair_request` creates the filesystem claim first; Custody acquisition is explicitly optional “shadow” state and failures never block the flow (`repair_requests.py:L1647-L1704`, `L2090-L2119`). Release omits lease store/lease ID and is therefore only best-effort cleanup (`repair_requests.py:L1707-L1720`). More seriously, `arnold-repair-loop` treats local PID/liveness as sufficient to release and reacquire a stale lock (`arnold-repair-loop:L741-L866`), contradicting the lock contract that stale evidence must not confer authority (`repair_lock.py:L346-L360`).

3. **P0 — authority mutation: classifier gates are bypasses, not delegation.**  
   Both watchdog launch functions print `"outcome": "delegated"` after only constructing a `RepairDelegation`; neither calls `delegate_to_simple_fixer` (`arnold-watchdog:L4391-L4411`, `L4479-L4499`). The caller rejects only `zero_authority_rejected`, so the normal `no_authority_claim` result proceeds to launch a managed repair loop (`arnold-watchdog:L5110-L5124`). The repair-loop equivalents have the same structure (`arnold-repair-loop:L6440-L6481`, `L6520-L6561`) and are followed by actual danger-full-access worker launch (`arnold-repair-loop:L8196-L8200`).

4. **P1 — status misreporting: manifest/status evidence is treated as canonical launch evidence.**  
   `report_item` labels a dispatch canonical when a managed manifest is structurally valid and contains a running history entry; it does not require a delegation receipt or Custody lease (`arnold-watchdog:L404-L427`). The tests reinforce the false contract: an exact F01 input is expected to return `delegated` from the classifier, although the classifier does not execute delegation (`tests/cloud/test_watchdog_wrappers.py:L17335-L17347`, `L17464-L17476`). This can report a canonical repair while the actual owner is a managed child.

5. **P0 — authority mutation: meta-repair provider and retrigger paths remain alternate owners.**  
   The Codex path launches a danger-full-access managed agent directly (`arnold-meta-repair-loop:L1532-L1578`); the Hermes fallback directly launches a repair agent with source-checkout instructions (`L1312-L1377`). After meta repair, the retrigger constructs and executes `arnold-repair-loop` through `run_managed_command` (`L2030-L2077`), entering the bypassed repair-loop owner. Provider choice therefore changes the mutation path.

6. **P2 — latent duplicate: dormant compatibility and exported retrigger helpers are not retired.**  
   `arnold-repair-trigger` hard-codes `meta_dispatch=False`, but retains a second `Popen` launch block (`arnold-repair-trigger:L512-L518`, `L788-L886`). `meta_repair.retrigger_ordinary_repair` remains exported, releases an unbound lock, and invokes `subprocess.run` (`meta_repair.py:L2296-L2375`); repository call-site search found tests but no production caller (`tests/cloud/test_meta_repair.py:L2526-L2536`). It is dormant, not proven retired.

## Incident reachability and severity

Observed: when `ARNOLD_REPAIR_F01_OCCURRENCE` is absent, the watchdog classifier returns `no_authority_claim`, not rejection (`arnold-watchdog:L4371-L4386`), and the caller launches the repair process anyway (`L5116-L5139`). The source search found this variable only in classifier code and tests, not in the actual launch construction. Therefore the bypass is reachable on the ordinary path.

Observed: two-container/PID-namespace stale handling can locally conclude “dead,” release the shared lock, and reacquire it without lease validation (`arnold-repair-loop:L748-L751`, `L850-L866`). Inference: this permits duplicate mutation owners when the original process is alive in another namespace.

## Minimal generalized remediation

1. Make Custody lease acquisition/validation a mandatory operation inside `delegate_to_simple_fixer`, immediately before claim and immediately before `CanonicalRunner.run`; fail closed on missing, expired, mismatched, or unavailable lease. The mkdir lock remains projection/admission evidence only.
2. Convert `claim_active_repair_request`, managed-run binding, and release into projections of that canonical lease, or make them call the same lease-backed adapter. Remove shadow-mode “never block” behavior for mutation paths.
3. Delete classifier-only authority gates. Every mutating watchdog, repair-loop, meta, provider, and retrigger caller must either call the canonical delegation function or return typed zero-authority rejection. Read-only investigation may remain managed.
4. Delete the dormant `meta_dispatch` branch and exported direct retrigger helper, then remove direct Codex/Hermes mutation launches unless they are invoked by the canonical owner.

A broader rewrite is unnecessary: the repository already has the exact F01 identity, typed outcomes, canonical runner, and lease authority check; the defect is consolidation failure and missing enforcement at their shared boundary.

## Required tests and retirement proof

- Two concurrent processes with the same F01 tuple: exactly one current lease and one mutation callback; the loser cannot mutate.
- Restart/expiry/fencing: expired lease, changed host/PID/boot identity, or lease-store outage must prevent mutation and produce typed rejection.
- Provider matrix: Codex and Hermes paths must both delegate or reject; no direct danger-full-access mutation path remains.
- Mutation/status firewall: `delegated` and `dispatched` require a successful canonical receipt plus current lease, never merely a manifest or return code.
- Two containers/PID namespaces: shared lock with foreign namespace PID, PID reuse, and local `kill -0` failure must not permit release or reclaim.
- Static retirement proof: production AST/source search shows no mutation caller invoking `acquire_repair_lock` without lease authority, no classifier returning `delegated` without calling the delegate, no direct meta/retrigger mutation subprocess, and no reachable `meta_dispatch` compatibility branch. Delete or make unreachable every duplicate, then assert zero production call sites.

## Unknowns

This was source- and test-level only; no services, containers, cloud lease store, or deployed wrappers were run. I cannot establish whether deployment configuration currently supplies an external lease gate absent from this checkout. The repository evidence nevertheless shows that the checked-in repair-fixer paths do not enforce that gate themselves.