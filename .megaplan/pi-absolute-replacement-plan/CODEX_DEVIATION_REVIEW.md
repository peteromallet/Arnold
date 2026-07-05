# Codex Deviation Review

Date: 2026-07-04  
Prompt: `/tmp/codex-deviation-review.md`  
Raw output: `/tmp/codex-deviation-review.out`

## Overall Verdict

Codex mostly agrees with the oracle decision:

> thin facade first, runtime replacement later, deletion only behind evidence
> gates.

Codex does not reject the split. It does, however, argue that the current split
still leaves some cross-cutting concerns too late or under-owned.

## Top Deviations

1. **Security is too late as M6.** Minimum enforcement must constrain M0/M1.
   M6 should become hardening/red-team/supply-chain, not the first real security
   track.
2. **Fanout needs an earlier throwaway architecture probe.** The M2 fanout spike
   is right, but pooling may affect adapter contracts, run records, kill
   semantics, and streaming events, so a disposable N=50/N=100 probe should run
   during discovery.
3. **Do not overstate "`claude -p` replaces Shannon."** The better framing is:
   retire Shannon as a contract. Stream-Shannon can likely move to `claude -p`;
   tmux-Shannon may require a sessionful Claude adapter.
4. **Adoption is under-owned.** Skills, docs, aliases, CI, runbooks, Makefiles,
   cloud runners, default profiles, failure diagnostics, and human workflows
   need a dedicated track.
5. **Quality gates are too abstract.** Codex review/apply and high-N research
   need labeled evaluation sets, blind comparison where feasible, and explicit
   thresholds before implementation starts.

## Epic Shape Recommendation

Codex still recommends seven epics, but with slightly different grouping:

1. Discovery/contracts/evaluation baselines
2. Thin facade + recording + minimum enforcement
3. Fanout feasibility and adapter design
4. Claude/Shannon retirement, split stream then sessionful
5. Codex review/apply governance
6. Consumer migration/adoption
7. Final hardening, deletion, bakeoff, installed-artifact proof

This differs from the previous grouping by promoting consumer migration/adoption
to its own epic and pushing security minimums into the facade epic.

## Gate Corrections

Too weak:

- Codex quality gate needs labeled corpus and explicit false-negative /
  patch-success thresholds.
- Adoption gate needs a concrete percentage of newly touched workflows,
  direct-command bypass count, and diagnosis-time target.
- Security gate needs negative tests before broad facade adoption.

Too strong:

- "No runtime replacement work begins before M0 passes" is too strict for
  disposable throwaway probes. Production migration should be blocked; harmless
  feasibility probes should be allowed.

Missing:

- Adapter contract freeze before M1 is considered stable.
- Rollback gate: emergency fallback must be time-boxed, telemetered, and unable
  to become permanent.
- MCP/tool permission parity gate.
- Install/runner reproducibility gate before adoption expands.

## Single Most Important Added Recommendation

Add a one-page decision map with kill criteria per track:

- what ships
- what can fail independently
- what evidence kills or resequences it
- what old path is deleted when

Codex's concern is that the plan is now strategically sound but can still read
like a very large plan with many gates. A human decision-maker needs the map to
see exactly how the split avoids becoming another monolith.
