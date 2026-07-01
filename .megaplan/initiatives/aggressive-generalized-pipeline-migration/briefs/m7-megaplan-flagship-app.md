# M7: Megaplan As The Flagship Arnold App

## Outcome

Megaplan becomes a serious app on the Arnold substrate, not the privileged owner of the substrate.

## Scope

In scope:

- Add or finalize a Megaplan planning pipeline manifest.
- Expose `build_pipeline()` for the Megaplan planning flow.
- Bind Megaplan-specific gate recommendations, artifact classifiers, receipt builders, profile policy, and human override semantics as Megaplan package policy.
- Route bakeoff, chain, or supervisor paths through generic orchestration only where parity is proven.
- Delete deprecated compatibility shims after dual-green replay proves replacement.
- Update docs to show Megaplan as one Arnold pipeline package.

Out of scope:

- Removing every legacy path without oracle proof.
- Moving Git/PR lifecycle or `.megaplan/briefs` conventions into generic Arnold.

## Locked Decisions

- Generic Arnold executes graph nodes and records evidence.
- Megaplan owns planning workflow semantics and user-facing planning CLI behavior.
- Compatibility deletions require oracle-backed proof.

## Done Criteria

- Old and new Megaplan paths replay the same traces with matching artifacts/state transitions.
- No internal Megaplan code imports deprecated compatibility paths after deletion.
- Public docs describe the generic substrate and Megaplan package responsibilities accurately.
- Active Evidence-First authority/provenance semantics still pass their gates.

---

## Revision — vocabulary decontamination + successor epic (2026-06-09)

When deleting the deprecated shims, also do a **naming-as-coupling cleanup pass** on the
generic substrate (naming is coupling: a non-planning pipeline importing
`TrustTier.AUTO_EXEC` or `OperationKind.RUN_PHASE` is speaking megaplan's dialect):
- Rename planning-flavored generic identifiers: `TrustTier`→`TrustClass`
  (`arnold/pipeline/discovery/trust.py`), `OperationKind.RUN_PHASE`→`EXECUTE`
  (`arnold/runtime/operations.py`), `routing.py` "Tier N" comments→"Priority N".
- Audit `arnold/pipeline|runtime|control|supervisor` for `plan/chain/milestone/
  success_criteria/gate/profile/tier/critique/finalize/review/STATE_*` baked into
  generic type/field/enum names; rename or move to a megaplan-supplied vocab.
- Move evidence/planning-specific built-in content-types
  (`arnold/pipeline/types.py:_BUILTIN_CONTENT_TYPES`) out of the module constant into a
  megaplan `CONTENT_TYPES.register()` call at app init.
- Resolve `Pipeline.binding_map` (`arnold/pipeline/types.py:269,276`): the docstring says
  typed-port binding is a megaplan concern but the field is unconditionally derived for
  every pipeline — make it injectable so non-typed-port pipelines never see it.

### Designated SUCCESSOR EPIC (out of scope here — name it, don't do it)
The control-plane payloads crossing "generic" seams are still untyped megaplan dicts:
`OperationRequest.payload` / `StepContext.state` / `hook_extensions` carry 15+ planning
keys (`phase`, `plan_dir`, `tier_spec`, `success_criteria`, …) by convention, so a second
pipeline must construct megaplan-shaped dicts to drive the control plane. Typing this is
the **Typed Step-IO Envelope epic** (truth of DATA crossing seams — peer to Evidence-First's
truth of STATE), and it is too large to fold here. This migration makes the runtime
*mechanisms* generic; that epic makes the *data* generic. Leave a ticket; do not start it
in this chain.
