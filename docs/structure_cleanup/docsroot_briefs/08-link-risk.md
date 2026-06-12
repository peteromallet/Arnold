Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: quantify link-update risk for moving remaining root docs.

Use:
- `find docs -maxdepth 1 -type f -name '*.md' | sort`
- `rg -n "docs/(authoring|vibeworkflow|api_stability|custom_nodes|errors_and_doctor|comfy_version_support|node_pack_reconciliation|local_agent_text_to_graph_blockers|local_agent_text_to_graph_e2e|roadmap_agentic_comfyui|structural_audit_2026-05|structural_issues|m4_resolution_context|release_notes)\\.md|\\((authoring|vibeworkflow|api_stability|custom_nodes|errors_and_doctor|comfy_version_support|node_pack_reconciliation|local_agent_text_to_graph_blockers|local_agent_text_to_graph_e2e|roadmap_agentic_comfyui|structural_audit_2026-05|structural_issues|m4_resolution_context|release_notes)\\.md\\)" . 2>/dev/null`

Do not edit files.

Return:
- per-file reference count
- highest-risk moves
- moves with near-zero references
- recommended stale-path scan after edits
