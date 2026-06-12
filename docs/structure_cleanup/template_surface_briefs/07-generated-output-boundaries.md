Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit generated output boundaries around templates and corpus.

Use:
- `find out artifacts ready_templates recipes workflow_corpus -maxdepth 3 -type f | sort | sed -n '1,260p'`
- `git status --short --ignored out artifacts ready_templates recipes workflow_corpus | sed -n '1,260p'`
- `rg -n "out/scratchpads|out/runs|artifacts/|snapshot|generated" README.md docs ready_templates recipes workflow_corpus tests vibecomfy`

Do not edit files.

Questions:
1. Are generated artifacts clearly separated from source templates/corpus/recipes?
2. Are any ignored generated files inside source dirs that should be cleaned?
3. What should remain untouched without user approval?

Return safe cleanup candidates and keep list.
