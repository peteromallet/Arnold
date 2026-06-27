# Cloud Watchdog Repair Principles

These principles are mandatory for watchdog-triggered repair agents.

1. Repair root causes, not symptoms. A restart is only a validation step after the underlying routing, state, source, credentials, or process issue has been understood.
2. Keep the editable install separate from the active workflow checkout. Source fixes belong in `/workspace/arnold` on `editible-install`; workflow-output or milestone changes belong in the active run workspace.
3. Respect declared routing. Use the chain spec, profile, vendor, and explicit phase overrides as the source of truth; do not silently invent a different provider because a fallback happens to be available.
4. Codex phases must run through the Codex plan/CLI path. Do not convert Codex phases to generic OpenAI/OpenRouter API calls unless the chain explicitly asks for that.
5. DeepSeek phases must run through the direct DeepSeek API credentials. Do not route DeepSeek through OpenRouter unless the chain explicitly asks for OpenRouter and the required key is present.
6. Provider dependency errors are usually routing/config bugs. Do not install unrelated provider tooling to paper over a phase being sent to the wrong backend.
7. Repair agents are supervisors, not replacement profiles. Do not pin every workflow phase to the repair model unless the chain explicitly requests that model for those phases.
8. Stale runtime pins that shadow the intended profile should be cleared or replaced through the supported profile/vendor/phase-model path.
9. Deep investigations and source repairs must use the `$subagent-launcher` skill. The supervisor should collect evidence, then dispatch the proper implementer/reviewer through that skill instead of doing all repair work in its own context.
10. When source changes are needed, brief Codex through `$subagent-launcher` with the core issue, evidence, constraints, and plausible hypotheses. Point Codex in the right direction without prescribing the implementation; let Codex determine the solution.
11. Validate narrowly, then persist. Run focused checks for the changed layer, commit and push source changes to `editible-install`, refresh the editable install, and then relaunch.
12. Finish with evidence: root cause, fix, validation commands, pushed commit if any, relaunch result, current health, and remaining blockers.
