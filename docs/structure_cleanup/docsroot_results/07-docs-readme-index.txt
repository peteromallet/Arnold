Now I have the complete picture. Let me compile the audit results.

---

## Audit Results: `docs/README.md` vs remaining root docs

### Q1: Does `docs/README.md` link every root doc that should be discoverable?

**No.** All 23 currently linked paths resolve correctly (including the new `comparisons/comfyscript.md`), but **8 root-level docs and 1 subdirectory are missing** — several of which users/contributors need to find:

| Missing doc | Lines | Why it matters |
|---|---|---|
| `errors_and_doctor.md` | 34 | CLI error reference — every user hitting a failure needs this |
| `roadmap_agentic_comfyui.md` | 535 | Strategic v2 roadmap — foundational project context |
| `node_pack_reconciliation.md` | 259 | Porting-blocker resolution guide — core workflow doc |
| `comfy_version_support.md` | 69 | Version compatibility policy — answers "what's supported" |
| `structural_issues.md` | 385 | Active cross-cutting issues log — working context |
| `structural_audit_2026-05.md` | 215 | May 2026 audit results — important historical reference |
| `m4_resolution_context.md` | 248 | M4 divergence inventory — milestone-specific but operational |
| `megaplan-briefs/` | — | Internal & user testing excellence plans (A, B) |

(`local_agent_text_to_graph_e2e.md` is intentionally gitignored with an embedded API key — correctly omitted.)

### Q2: Does it point users to correct subfolders after recent moves?

**All linked paths resolve.** The new `[Comparisons](comparisons/comfyscript.md)` entry (line 26) is valid — the file exists at `docs/comparisons/comfyscript.md`. The `[Cookbook](cookbook/)` directory exists with 7 recipe `.py` files, though it lacks a `README.md`. No broken links found.

### Q3: What minimal edits should be made?

Add **4 high-priority links** to `docs/README.md`:

1. `errors_and_doctor.md` — in **Core Guides** (users need this before digging into subdirectories)
2. `roadmap_agentic_comfyui.md` — in **Core Guides** (strategic document, belongs with core reference)
3. `node_pack_reconciliation.md` — in **Core Guides** (porting workflow doc)
4. `comfy_version_support.md` — in **Core Guides** (version policy)

---

### Exact README changes

```diff
 ## Core Guides

 - [Authoring](authoring.md)
 - [VibeWorkflow](vibeworkflow.md)
 - [API](api/)
 - [API stability](api_stability.md)
 - [Custom nodes](custom_nodes.md)
+- [Doctor / error reference](errors_and_doctor.md)
+- [Node pack reconciliation](node_pack_reconciliation.md)
+- [ComfyUI version support](comfy_version_support.md)
 - [Testing](testing/)
 - [Release notes](release_notes.md)
+- [Roadmap](roadmap_agentic_comfyui.md)
```

**Rationale:**
- **Core Guides** is the right section — these are reference docs for everyone using/porting workflows, not "Main Area" subdirectory topics.
- `errors_and_doctor.md` is the #1 most-needed doc for any user hitting a CLI error.
- `roadmap_agentic_comfyui.md` gives strategic context early, before diving into areas.
- `node_pack_reconciliation.md` and `comfy_version_support.md` are practical porting references.
- The remaining 4 (`structural_issues.md`, `structural_audit_2026-05.md`, `m4_resolution_context.md`, `megaplan-briefs/`) are operational/internal enough that adding them is lower priority — the closing blurb ("Several large doc clusters are still being organized") already covers that.
- `megaplan-briefs/` is already implicitly covered by the `megaplan_chains/` note on lines 34-36.