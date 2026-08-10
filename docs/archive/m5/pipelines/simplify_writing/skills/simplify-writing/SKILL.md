---
name: simplify-writing
description: Fan out DeepSeek Pro critics and a Kimi editor to iteratively simplify a piece of writing.
---

# simplify-writing

Multi-perspective writing simplifier.

- Runs up to 10 DeepSeek Pro critics in parallel, each with a distinct lens.
- Feeds all critiques to Kimi 2.7 for a revised draft.
- Opens the revised draft and asks the user for feedback.
- Loops with feedback-derived perspectives until the user is happy.

Run with a file path:

```bash
python -m arnold run simplify-writing path/to/draft.md
```

Custom perspectives (comma- or semicolon-separated):

```bash
python -m arnold run simplify-writing path/to/draft.md \
  --inputs perspectives="word choice;succinctness;tone"
```
