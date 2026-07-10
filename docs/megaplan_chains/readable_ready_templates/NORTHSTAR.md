# Readable Ready Templates North Star

The chain should make VibeComfy ready templates read like maintainable Python
workflow builders rather than Comfy JSON translated into Python syntax.

The durable outcome is generator-led: future imports should emit readable,
schema-backed, public-input-aware templates by default, and existing checked-in
workflows should be regenerable or repairable without losing parity with their
source graphs.

The source roadmap is `docs/templates/readable_ready_template_cleanup_plan.md`.
Preserve its contract across every milestone: named outputs where schema data
exists, named inputs/widgets instead of `widget_N`, real registered user
controls, semantic variable names, provenance without raw-id driven reading
surfaces, and strict gates that prevent opaque generated templates from
silently becoming the default.
