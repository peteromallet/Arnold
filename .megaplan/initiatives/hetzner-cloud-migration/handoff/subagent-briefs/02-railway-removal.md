Working directory: /Users/peteromalley/Documents/Arnold

Task: audit what must change to delete the Railway provider path entirely from Megaplan cloud.

Read these first:
- arnold/pipelines/megaplan/cloud/providers/railway.py
- arnold/pipelines/megaplan/cloud/providers/base.py
- arnold/pipelines/megaplan/cloud/spec.py
- arnold/pipelines/megaplan/cloud/cli.py
- arnold/pipelines/megaplan/cloud/templates/*
- docs/cloud.md
- tests/cloud
- tests/characterization/test_import_surface.py

Constraints:
- Do not edit files.
- Assume "delete Railway path entirely" means no provider=railway support, no Railway provider class/import, no Railway docs as active workflow.
- Preserve local and SSH/Hetzner providers.

Return:
- File-by-file removal checklist.
- Likely breaking tests/import surfaces.
- Any compatibility shims worth keeping or explicitly not keeping.
- Focus on actionable changes, under 700 words.
