Working directory: /Users/peteromalley/Documents/Arnold

Task: Find pipeline/workflow runtime surfaces that launch or configure agents outside the obvious megaplan worker routes.

Focus areas:
- arnold/pipeline/**
- tests/pipeline/**
- arnold_pipelines/* pipeline packages
- workflow manifests, scenario runners, generated pipeline APIs
- any "agent" pipeline step, fanout step, model profile step, or workflow authoring validation

Question: Does the final plan need a separate pipeline-runtime compatibility contract, or are these covered by profile/consumer migration?

Output:
- Ranked findings with paths and recommended plan changes.
- Include whether each should be Epic 1 inventory, Epic 2 facade, Epic 7 migration, or a new epic.
- Keep under 800 words.
