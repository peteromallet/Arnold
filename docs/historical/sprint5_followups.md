# Sprint 5 Follow-Ups

**Status:** Historical follow-up plan. Sprint 5 delivery is complete; this doc is kept for context.

This sprint improves type visibility, schema-backed validation, and generated-template reference safety. It does not close the broader roundtrip or positional-output cleanup work.

## Out Of Scope For Sprint 5

- Full bidirectional workflow roundtrip remains Sprint 5 work. `VibeWorkflow.export_to_json(format='api')` and `port export --to json` expose the API dict that already comes from `compile('api')`; they do not implement UI JSON reconstruction, AST-based subgraph reconstruction, or a broad import/export equivalence harness.
- Broad positional-output replacement remains Sprint 5 work. Schema-derived `Handle.output_type`, generated stubs, and strict connection warnings reduce risk for new authoring, but they do not rewrite every positional `.out(0)` in existing generated or curated templates.

## Related Ticket Context

- `01KRNDP7S3BW6DMNKAWPNVVYMB` is related context only. Typed handles and schema warnings reduce positional-output ambiguity, but this sprint does not resolve the ticket because broad positional-output replacement is intentionally out of scope.
- `01KRKQGP81Z5XR0FAK19T5CAC8` is related context only. The sprint improves local API contracts and export access, but it is not the full cross-repo runtime-contract or bidirectional roundtrip effort.

Do not mark either ticket resolved from the Sprint 4 changes alone.
