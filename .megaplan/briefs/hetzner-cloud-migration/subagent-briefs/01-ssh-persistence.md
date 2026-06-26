Working directory: /Users/peteromalley/Documents/Arnold

Task: audit the current Megaplan cloud SSH provider and propose exact implementation changes to make Hetzner/SSH the native persistent-storage path.

Read these first:
- arnold/pipelines/megaplan/cloud/providers/ssh.py
- arnold/pipelines/megaplan/cloud/spec.py
- arnold/pipelines/megaplan/cloud/templates/cloud.yaml.tmpl
- arnold/pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl
- docs/cloud.md

Constraints:
- Do not edit files.
- Assume Railway will be removed entirely.
- The new approach should persist /workspace, auth seeds, plan state, cloned repos, .venv, node_modules, and useful caches across container redeploy.
- Keep config simple and native to SSH/Hetzner.

Return:
- A concise patch plan with exact fields, defaults, and command changes.
- Any hidden hazards in the current SSH provider.
- Tests that should be added or changed.
