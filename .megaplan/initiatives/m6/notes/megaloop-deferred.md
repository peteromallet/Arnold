# M6 MegaLoop Deferral

MegaLoop remains outside the M6 strangler swap.

The M6 retirement authority is limited to the Arnold planning pipeline and its
manifest-first discovery path. MegaLoop still has its own `plan` and `execute`
literals and keeps its separate two-phase loop until a dedicated MegaLoop
migration can preserve its operational semantics, artifacts, and recovery
behavior.

This is an explicit scope boundary, not a hidden fallback. M6 must not route
MegaLoop through the new discovered planning package, and M6 review should only
verify that MegaLoop was not silently changed while planning moved behind the
manifest-discovered Arnold path.
