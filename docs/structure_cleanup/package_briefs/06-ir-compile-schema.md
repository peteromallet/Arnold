# Package Layer Audit 06: IR, Compile, Schema

Audit core graph/IR and compilation modules: `ir/`, `_compile/`, `schema/`,
contracts, handles, validation, and related root files.

Questions:
- Which modules are core architecture boundaries?
- Are imports layered correctly from a structure standpoint?
- Are there small misplaced files or missing READMEs?
- What path moves would violate `.importlinter` or public APIs?

Focus on documentation/indexing and stale artifacts.
