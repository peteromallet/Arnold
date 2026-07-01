Working directory: /Users/peteromalley/Documents/Arnold

Task: identify the focused tests/docs updates needed after making SSH/Hetzner the native cloud path with persistent storage and removing Railway.

Read these first:
- tests/test_cloud_spec.py
- tests/test_cloud_template.py
- tests/cloud
- docs/cloud.md
- README.md
- arnold/pipelines/megaplan/cloud/templates/cloud.yaml.tmpl
- arnold/pipelines/megaplan/cloud/templates/docker-compose.yaml.tmpl

Constraints:
- Do not edit files.
- Avoid broad refactors. Keep the test set focused.
- The implementation should default to persistent storage for SSH/Hetzner.

Return:
- Specific tests to add/change/remove.
- Expected assertions.
- Any docs snippets that must change.
- A short recommended verification command list.
