Working directory: /Users/peteromalley/Documents/Arnold

You are an independent Codex reviewer. Review whether any parts of the
canonical unified agent surface plan could be better achieved by using an
existing Pi extension/plugin/package.

Read these local files:

- .megaplan/pi-absolute-replacement-plan/FINAL_UNIFIED_AGENT_SURFACE_PLAN.md
- .megaplan/pi-absolute-replacement-plan/LONGSHOT_SWARM_REVIEW.md
- .megaplan/pi-absolute-replacement-plan/GAP_SWARM_REVIEW.md

Relevant current Pi package/catalog facts gathered from pi.dev:

- Pi packages can execute code and influence agent behavior; third-party source
  should be reviewed before installation.
- Pi supports extensions, skills, prompt templates, themes, and npm/git
  packages.
- Pi ships without sub-agents/plan mode by default, but packages can add them.
- Candidate packages:
  - `pi-subagents`: delegates work to focused child agents; supports code
    review, scouting, implementation, parallel audits, saved workflows, and
    background jobs.
  - `@tintinweb/pi-subagents`: Claude-Code-style autonomous subagents for Pi.
  - `pi-sub-agent`: a `subagent` tool for specialized Pi subprocesses with
    isolated context windows.
  - `pi-agents-team`: background RPC worker agents / multi-agent team.
  - `pi-web-access`: web search, content extraction, GitHub repo cloning, PDF
    extraction, YouTube/video understanding; multiple provider options.
  - `pi-web-providers`: configurable web access with per-tool provider routing
    and option schemas for search/content/answers/research.
  - `@hypabolic/pi-hypa`: compresses noisy shell/tool output and provides
    context-aware file tools/recoverable evidence.
  - `context-mode`: context-saving package with FTS5 knowledge base,
    sandboxed code execution, intent-driven search; described as MCP-oriented.
  - `pi-mcp-adapter`: MCP adapter for Pi. The human explicitly doubts that we
    should use MCP. Treat "do not use MCP" as the default constraint unless a
    very strong counterargument exists.
  - `pi-chat`: Pi chat/resident-style package relevant only if it helps cloud
    or resident Discord/Telegram-like surfaces.

Core constraints:

- The Arnold facade must remain the route/policy/run-record/credential owner.
- Do not recommend replacing the facade with a Pi package.
- Do not recommend MCP unless it is clearly superior after considering the
  user's skepticism.
- Any package adoption should be "fork", "wrap", "vendor small pieces", "use as
  spike/reference only", or "do not use".
- Prioritize robustness, long-term control, deletion gates, security, and
  maintaining Arnold's existing profile/fanout/skill surfaces.

Output:

1. Ranked package-by-package verdicts.
2. Which plan epics should change, if any.
3. A clear answer on MCP.
4. A concise final recommendation: fork/wrap/build for each candidate.
5. Keep under 1200 words.
