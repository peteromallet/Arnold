# Package Layer Audit 05: Templates And Nodes

Audit `vibecomfy/templates.py`, `vibecomfy/nodes/`, `vibecomfy/comfy_nodes/`,
wrappers, generated node surfaces, and template authoring helpers.

Questions:
- Which files are generated or public import surfaces?
- Are generated node wrappers clearly documented?
- Are ComfyUI custom-node extension files separated from Python authoring helpers?
- What must not move due to ready template imports?

Return safe docs/index cleanup only unless a stale file is certain.
