Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit `workflow_corpus/` layout.

Use:
- `find workflow_corpus -maxdepth 4 -type f | sort`
- `rg -n "workflow_corpus|external_workflow_index|workflow_index|sources sync" README.md docs tests vibecomfy scripts tools pyproject.toml`

Do not edit files.

Questions:
1. Is corpus layout deliberate and loader/index backed?
2. Is a README missing?
3. Are any generated indexes or converted artifacts misplaced inside corpus?
4. What changes are safe without affecting indexed workflow IDs?

Return exact recommendations and risks.
