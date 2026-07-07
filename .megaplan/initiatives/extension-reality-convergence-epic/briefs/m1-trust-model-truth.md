# M1: Trust Model Truth

## Outcome

Make the extension trust model true across code, contracts, docs, examples, and manager UI. The system should clearly present extensions as trusted local code with non-enforcing access disclosures, not as sandboxed or permission-enforced code.

## Execution Posture

Be strict about language. This milestone is not allowed to implement partial permission checks and call them enforcement. The elegance comes from a truthful boundary, not from declarative theater.

## Scope

IN:
- Audit `ExtensionManifest.permissions`, SDK permission/access types, JSON schema, examples, docs, and manager UI copy.
- Fix SDK/schema drift for permission-like declarations.
- Rename, deprecate, or explicitly reframe permission declarations as non-enforcing access disclosures.
- Surface access disclosures in the Extension Manager beside the trusted-code warning.
- Add tests or quality gates that fail if docs/UI/schema imply sandboxing, runtime permission enforcement, marketplace safety, or untrusted third-party support.
- Preserve current trusted-extension runtime behavior.

OUT:
- iframe, Worker, process, SES-like, or brokered API isolation.
- Runtime permission enforcement.
- Marketplace install/discovery/update/delete flows.
- Code signing, dependency resolution, or remote package trust.

## Constraints

- Do not remove manifest compatibility without a migration or compatibility shim.
- Do not weaken existing manifest validation.
- Do not make access disclosure optional in places where UI or docs present sensitive capabilities.
- Do not introduce security claims that cannot be backed by runtime enforcement.

## Done Criteria

- SDK, JSON schema, docs, examples, and manager UI describe the same trusted-code/access-disclosure model.
- The manager exposes declared access/disclosure information without implying enforcement.
- A regression gate catches forbidden terms or claims unless they are paired with explicit deferred/non-enforced language.
- Existing extension tests pass, with added tests covering the contract shape and UI disclosure behavior.
- Documentation explicitly defers true untrusted-extension enforcement to a future isolation/broker epic.

## Touchpoints

- `src/sdk/index.ts`
- `config/contracts/reigh-extension.schema.json`
- `src/tools/video-editor/components/ExtensionManager*`
- `src/tools/video-editor/runtime/extensionLoader.ts`
- `docs/extensions/**`
- `examples/**`
- `scripts/**` quality/doc checks, if present

