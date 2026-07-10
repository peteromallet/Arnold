# Intent fixture JSON schema

Each intent fixture is a JSON object with the following fields. All fields are
required unless marked optional.

```jsonc
{
  // Unique string identifier for the fixture (e.g. "image_01_swap_color").
  "id": "string",

  // Path (relative to the fixtures directory or absolute) to the pre-edit
  // ComfyUI workflow JSON that will be loaded before applying the edit.
  "pre_workflow_path": "string",

  // Natural-language description of the intended edit, e.g.
  // "Swap the red dress for a blue one."
  "nl_intent": "string",

  // An IR-level patch (structural diff) that captures what the edit *should*
  // do to the workflow. Format is TBD (e.g. JSON-patch, semantic-patch, or
  // node-level diff).
  "post_edit_ir_patch": "object",

  // Human-readable description of *how* this fixture is wrong (i.e. what the
  // model actually did that deviates from the intent). Used to ground truth
  // judge evaluations.
  "wrongness_description": "string",

  // The fixture family: "image", "edit", or "video".
  "family": "string (enum: image | edit | video)",

  // The expected automated refusal-spine probe verdict.
  // "refuse" = spine should block execution.
  // "allow"  = spine should permit execution.
  "expected_refusal_spine_verdict": "string (enum: refuse | allow)",

  // Semantic description of what changed between pre- and post-edit IR.
  // Used by render_diff.py for structural diff assertions.
  "intended_delta": "object",

  // The expected verdict from the text-based judge (LLM-driven).
  // "wrong_but_faithful" = the model faithfully executed the edit but the
  //   edit itself was wrong (i.e. correct execution of incorrect intent).
  // "wrong_and_unfaithful" = the model failed to execute even the wrong edit.
  "expected_text_judge_verdict": "string (enum: wrong_but_faithful | wrong_and_unfaithful)"
}
```

## Machine-checkable invariants

1. `family` MUST be one of `image`, `edit`, `video`.
2. `expected_refusal_spine_verdict` MUST be one of `refuse`, `allow`.
3. `expected_text_judge_verdict` MUST be one of `wrong_but_faithful`, `wrong_and_unfaithful`.
4. `id` MUST be unique across all fixtures in a test run.
5. `pre_workflow_path` MUST resolve to an existing file.
