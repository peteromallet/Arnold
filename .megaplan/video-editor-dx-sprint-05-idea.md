Video editor developer platform Sprint 5: command bus, transactions, dry-run, and undo/redo.

Depends on Sprints 1-4:
Build on the command facade, canonical validation, and capability manifest.

Goal:
Make timeline mutation a first-class, typed, agent-safe transaction system.

Primary outcomes:
- Introduce command descriptors with apply, invert, validate, dryRun, and structured errors.
- Route existing editor mutations through the command bus where practical.
- Make undo/redo command-based.
- Support transaction batches: { transactionId, commands: [...] }.
- Expose public useTimelineCommands() and headless command runner APIs.
- Let clip-type plugins register commands.

Important constraints:
- Preserve current editor interaction behavior.
- Do not require every obscure mutation to migrate if it would explode scope; document remaining direct mutation paths.
- Tests should cover validation failure, dry-run, apply, invert/undo, and batch behavior.

Success criteria:
- Agents can safely propose, validate, dry-run, and apply batches of timeline edits through a portable JSON-like transaction format.
- Direct rows/meta/clipOrder mutation is no longer needed for common editor and agent workflows.
