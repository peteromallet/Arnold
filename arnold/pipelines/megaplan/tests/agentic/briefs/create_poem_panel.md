# New megaplan pipeline: poem-panel

Create a new built-in megaplan pipeline named `poem-panel` that:

1. Takes a topic string as input.
2. Generates a draft poem.
3. Sends the draft to three critics with distinct perspectives:
   formalist, emotional reader, contrarian.
4. Synthesizes their feedback.
5. Revises the poem.
6. Loops back to step 3 until either a quality gate passes or 5 iterations elapse.

Constraints:
- Use ONLY existing pipeline primitive kinds. Read the schema to find them.
- Do NOT add new step kinds or modify `megaplan/cli.py`.
- Land the pipeline under `megaplan/pipelines/poem-panel/`.
- After creating it, smoke-run: `megaplan run poem-panel --topic "tide pools"`.

Done = `megaplan run --list` shows `poem-panel`; `load_pipeline("poem-panel")`
succeeds; the smoke run produces a final poem.
