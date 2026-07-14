# Using the Grok (xAI) API Directly

This document captures how to use your Grok API key and the public endpoint **outside of the `grok` CLI/TUI tool**.

## Endpoint & Auth (the values to share/copy)

- **Base URL**: `https://api.x.ai/v1`
- **Auth**: `Authorization: Bearer $XAI_API_KEY` (raw HTTP)
  or `api_key=os.getenv("XAI_API_KEY")` (SDK)
- **Primary model**: `grok-4.5` (current flagship per xAI; great for code + general tasks)
- **Get key**: https://console.x.ai/team/default/api-keys

## Quick Python (using the openai package already in this repo)

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

# Preferred Responses path (shown in xAI docs for grok-4.5)
resp = client.responses.create(model="grok-4.5", input="Hello from direct API")
print(getattr(resp, "output_text", resp))

# Or classic:
resp = client.chat.completions.create(
    model="grok-4.5",
    messages=[{"role": "user", "content": "Hello"}]
)
print(resp.choices[0].message.content)
```

## curl

```bash
curl https://api.x.ai/v1/responses \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "grok-4.5", "input": "short test"}'
```

(Also supports `/v1/chat/completions`.)

## Running the test/demo script in this repo

```bash
python scripts/test_grok_api_endpoint.py
```

See `scripts/test_grok_api_endpoint.py` (and its tests) for a minimal, importable, runnable example that always emits the endpoint details above.

## Notes

- The API is intentionally OpenAI-compatible for easy migration.
- No changes to the `grok` tool itself are needed or performed.
- For full reference: https://docs.x.ai/developers/quickstart

This was added to enable direct use of the endpoint/key without going through the TUI.
