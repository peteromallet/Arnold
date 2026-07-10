# IR

Canonical workflow data model types live here. This package owns the low-level
graph representation and diagnostics used below templates, patches, blocks, and
runtime execution.

Keep this layer small and dependency-light. IR modules should not reach upward
into CLI commands, runtime orchestration, porting emitters, blocks, patches, or
ops.
