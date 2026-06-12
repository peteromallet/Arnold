# Dead Module Audit 10: Safe First Batch

Synthesize the conservative dead-module cleanup batch.

Only recommend deletion when:
- no code/test/tool import remains
- docs/artifacts either do not reference it or exact reference repair is included
- public compatibility risk is low

Return exact delete/edit/defer list and verification commands.
