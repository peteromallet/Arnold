# Executor brief — B4 BEAUTY PASS (visual only — NO input-handling rewrites)
North Star: indistinguishable from stock wizard; UX structure already gated in B2.
Worktree /tmp/oh-my-pi-onboard-ui (branch onboard-ui). Commit NOTHING.

Scope (visual/copy only):
1. Copy sweep across both scenes: titles/subtitles/hints/error lines — match stock tone exactly
   (imperative title + next-step subtitle); kill any awkward phrasing; keep secrets-safe wording.
2. Visual params: spacing/indentation consistency with stock scenes; marker/description alignment;
   spinner cadence; outro copy adaptation ("Setup saved" context fits onboarding).
3. Intro: confirm splash → dissolve → scene 1 transition feels native in pty transcript (no
   code change unless a wiring nit shows).
4. Empty-state and verify-failure copy polish (calm, actionable, no blame).

Constraints:
- Do NOT touch input handling, key bindings, scene order, verify logic, persistence.
- Do NOT rename exported symbols used by tests.
- Run full onboarding suites + typecheck after; refresh pty transcript.
Report: every copy/visual diff (before -> after), verbatim suite tails.
