# Verify editable auto-repair runtime and harden both prevention layers

Attach to the existing canonical Workflow Boundary Contracts run/session `workflow-boundary-contracts-corrective-20260710` and current C1 plan. Do not create a duplicate chain or disturb a healthy live worker.

The prior root-hardening result is local commit `cfe3b25ee` on branch `fix/c1-repair-unavailable-root-corrective`. Verify the actual code and commit rather than trusting this summary. Determine whether those changes are present in the exact editable Arnold checkout used by the existing WBC chain, watchdog, repair loop, resident-facing status projections, and any subprocess-isolated execution environment. Prove import origins, installed editable metadata, source revision, and runtime revision. Detect older wheels, site-packages copies, cached builds, or another workspace shadowing the intended checkout.

If the hardening is not in the authoritative runtime, safely integrate or forward-port it into the correct existing checkout and install that exact checkout editable in every relevant execution environment. Preserve all unrelated work and do not push. Do not use arbitrary remote shell; work locally inside the current machine/container and use canonical Megaplan controls only. Do not force-proceed or bypass gates.

Verify and, where necessary, fix both layers:

1. Primary prevention: prevent the original deterministic failures where reasonably possible, including editable-install/import shadowing, typed failure loss, stale projection/cursor mismatch, swallowed relaunch fallback, false liveness, and broken claim/custody transitions.
2. Secondary recovery: if a bounded deterministic failure still occurs, persist typed evidence and automatically dispatch exactly one safe bounded L1 repair; accepted-but-unclaimed requests remain visible and retry; `needs_human` is reserved for explicit typed human decisions. Unknown or broken automation must fail closed without being mislabeled as a human decision.

Confirm whether commit `cfe3b25ee` fully covers both layers. If it only improves auto-repair, add the missing prevention changes and focused regression tests. Include realistic integration tests that exercise the same editable/subprocess environment and prove: correct source import; deterministic quality/import failure produces typed repair; exactly one claim/attempt; recovery progresses without human notification; genuine approval/credential/product-decision gates remain human-only; unknown evidence remains distinct; stale markers cannot override newer recovery evidence.

After validation, safely re-drive or reconcile the existing WBC C1 only if needed and authorized by canonical state. Report the exact source commit(s), effective import paths/revisions, tests, existing session/plan state, whether changes are active for this current run, and the precise boundary of what is prevented versus merely auto-repaired. Write a concise durable note under the WBC initiative. Do not claim future failures are impossible; characterize residual classes honestly.
