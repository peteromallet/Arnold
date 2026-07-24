#!/usr/bin/env python
"""
scripts/test_grok_api_endpoint.py

Standalone demo + helpers for using Grok (xAI) API key/endpoint *outside* the
grok CLI/TUI tool.

This exercises the public xAI endpoint using the project's existing 'openai'
dependency. It is runnable directly and importable for testing.

SHARED ENDPOINT DETAILS (always printed):
- Endpoint base: https://api.x.ai/v1
- Auth: XAI_API_KEY environment variable (used as api_key= in SDK,
  or Authorization: Bearer $XAI_API_KEY in raw HTTP)
- Primary model: grok-4.5 (flagship for code/general use per xAI docs)
- Compatible with: OpenAI SDK (Python/JS), curl, Cursor custom providers,
  LangChain (openai compat), etc.

Usage (from project root):
  python scripts/test_grok_api_endpoint.py

To test live:
  export XAI_API_KEY="xai-..."
  python scripts/test_grok_api_endpoint.py

See also: official docs at https://docs.x.ai/developers/quickstart
"""

import os
from typing import Optional

from openai import OpenAI

# === Shared constants for users copying this pattern ===
ENDPOINT = "https://api.x.ai/v1"
MODEL = "grok-4.5"
AUTH_ENV = "XAI_API_KEY"


def make_grok_client(api_key: Optional[str] = None) -> OpenAI:
    """Return a configured OpenAI client pointed at the xAI Grok endpoint.

    - If api_key is None, falls back to os.getenv("XAI_API_KEY").
    - Raises clear error if no key is available (for explicit live use).
    - Accepts a dummy key (e.g. 'dummy') for unit tests of construction.
    - This is the shipped function exercised by tests.
    """
    if api_key is None:
        api_key = os.getenv(AUTH_ENV)

    if not api_key:
        raise ValueError(
            f"No API key provided and ${AUTH_ENV} not set in environment. "
            f"Set export {AUTH_ENV}='xai-...' to make live calls."
        )

    client = OpenAI(
        api_key=api_key,
        base_url=ENDPOINT,
    )
    return client


def call_model(client: OpenAI, prompt: str) -> str:
    """Call the model with a prompt and return the text response.

    Prefers the Responses API (shown in current xAI quickstart for grok-4.5)
    and falls back to classic chat.completions for broad compatibility.

    This is the shipped network-calling function. Non-network parts
    (construction, arg handling) are directly testable without a live key.
    """
    # Try Responses API first (per https://docs.x.ai/developers/quickstart examples)
    try:
        resp = client.responses.create(
            model=MODEL,
            input=prompt,
        )
        # Docs examples use response.output_text; be defensive
        if hasattr(resp, "output_text") and resp.output_text:
            return str(resp.output_text).strip()
        # Some shapes return choices or output list
        if hasattr(resp, "output") and resp.output:
            # crude extraction for possible list of content
            return str(resp.output).strip()
        return str(resp)
    except Exception:
        # Fallback to standard Chat Completions (widely supported)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.choices[0].message.content
        return (content or str(resp)).strip()


def print_endpoint_info() -> None:
    """Always emit the shareable endpoint/auth/model details."""
    print("=== Using Grok (xAI) API directly (outside the grok tool) ===")
    print(f"Endpoint: {ENDPOINT}")
    print(f"Model: {MODEL}")
    print(f"Auth (SDK): api_key=os.getenv('{AUTH_ENV}')")
    print(f"Auth (HTTP): Authorization: Bearer ${AUTH_ENV}")
    print("SDK pattern: OpenAI(api_key=..., base_url=ENDPOINT)")
    print("curl example:")
    print(f'  curl {ENDPOINT}/responses \\')
    print(f'    -H "Authorization: Bearer ${AUTH_ENV}" \\')
    print('    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"model": "{MODEL}", "input": "hello"}}\'')
    print("Also works with: /chat/completions (classic), JS SDKs, Cursor, etc.")
    print("Docs: https://docs.x.ai/developers/quickstart and https://docs.x.ai/developers/models")
    print()


if __name__ == "__main__":
    print_endpoint_info()

    key = os.getenv(AUTH_ENV)
    if not key:
        print("XAI_API_KEY not set in this environment.")
        print("To get a live response:")
        print(f"  export {AUTH_ENV}='xai-your-key-here'")
        print("  python scripts/test_grok_api_endpoint.py")
        print()
        print("The endpoint, model, and auth details above can be copied")
        print("directly into any OpenAI-compatible client or tool.")
        print()
        print("In Arnold/Hermes (via prefix like claude: or hermes:xxx:):")
        print("  hermes:xai:grok-4.5   or   --phase-model foo=hermes:xai:grok-4.5")
        print("  (XAI_API_KEY added to .env + ~/.hermes/.env)")
        # Exit 0 with guidance (per acceptance criteria graceful path)
    else:
        print(f"{AUTH_ENV} detected (value hidden for safety).")
        try:
            client = make_grok_client()  # will use env
            result = call_model(client, "Reply with a short confirmation that you are reachable via the direct Grok xAI API endpoint at https://api.x.ai/v1 using model grok-4.5. One sentence.")
            print("Live model response:")
            print(result)
            print()
            print("SUCCESS: direct endpoint call completed.")
        except Exception as exc:
            print(f"Live call encountered an error: {exc}")
            print("Endpoint details (above) are still valid for configuration.")
            # Do not fail the script; it still shared the info
