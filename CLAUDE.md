# Arnold v2

IMPORTANT: Do NOT create a `megaplan/` directory in the project root. This name conflicts with the megaplan CLI tool. If you need a namespace wrapper package, name it `arnold_sdk/` instead.

The project structure is:
- agent_kit/ — core agent framework
- arnold/ — Arnold bot implementation and CLI
- arnold_sdk/ — thin re-export wrapper (optional)
- tests/ — test suite
