/goal

# Rules

* Drive this **whole epic** to completion. Do not treat it as a partial implementation, exploration, or best-effort cleanup. Keep going until the epic is complete, validated, and no known blockers remain.

* Work in a **new git worktree** for this epic. Do not do this work directly in the existing checkout.

* Always use Codex subagents, via the subagent launcher, to explore and fix issues. Use them to investigate failures, inspect relevant code, repair broken behavior, update tests, validate fixes, and resolve anything blocking progress.

* Unblock and fix whatever gets in the way. If the harness, editable install, local environment, tests, scripts, chain runner, target project, docs, or supporting code are broken, inspect the failure, fix the root cause, and continue.

* Do **not** change the models used in the profiles. Preserve existing profile model selections exactly. Do not upgrade, simplify, swap, normalize, or otherwise alter model choices while completing the epic.

* Use the Megaplan editable install that includes the publication-completion guard. A PR-backed milestone must not be considered complete unless the published PR/merge diff contains the semantic product work or a valid typed no-op waiver.

# Epic chain file

```text id="foundation-closure-chain"
/Users/peteromalley/Documents/.codex-worktrees/reigh-m5-readiness/.megaplan/briefs/reigh-foundation-closure/chain.yaml
```

# North Star anchor

```text id="foundation-closure-north-star"
/Users/peteromalley/Documents/.codex-worktrees/reigh-m5-readiness/.megaplan/briefs/reigh-foundation-closure/NORTHSTAR.md
```

# Plans referenced inside the chain

## M1 - Public Proposal Contract

```text id="foundation-closure-m1"
/Users/peteromalley/Documents/.codex-worktrees/reigh-m5-readiness/.megaplan/briefs/reigh-foundation-closure/m1-public-proposal-contract.md
```

## M2 - Agent Proposal Vertical Proof

```text id="foundation-closure-m2"
/Users/peteromalley/Documents/.codex-worktrees/reigh-m5-readiness/.megaplan/briefs/reigh-foundation-closure/m2-agent-proposal-vertical-proof.md
```

## M3 - Settings Runtime Write-Through

```text id="foundation-closure-m3"
/Users/peteromalley/Documents/.codex-worktrees/reigh-m5-readiness/.megaplan/briefs/reigh-foundation-closure/m3-settings-runtime-write-through.md
```

## M4 - Release Readiness Gate

```text id="foundation-closure-m4"
/Users/peteromalley/Documents/.codex-worktrees/reigh-m5-readiness/.megaplan/briefs/reigh-foundation-closure/m4-release-readiness-gate.md
```

# Execution

* Start from the chain file.
* Preserve and enforce the North Star anchor declared by `anchors.north_star`.
* Inspect the referenced milestone plans.
* Create a new git worktree for this epic.
* Launch the chain from that worktree.
* Use `/Users/peteromalley/Documents/megaplan` as needed to understand how to launch, run, debug, resume, and complete the chain.
* Use the subagent launcher instructions at `/Users/peteromalley/Documents/poms_skills/subagent-launcher/SKILL.md` whenever investigation, fixing, or validation would otherwise bloat the main context.
* If anything blocks the run, inspect the relevant files, docs, logs, tests, scripts, chain state, and editable install state. Fix the root cause and continue.
* Preserve all profile model selections in `chain.yaml`; every milestone is intentionally `partnered-5` with Codex.
* Do not stop until the epic is complete and validated.
