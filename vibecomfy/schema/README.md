# Schema

Schema providers, object-info adapters, and call-validation helpers live here.
Consumers should prefer the public exports from `vibecomfy.schema` rather than
reaching into implementation modules directly.

This package is structural validation only. Runtime readiness, model staging,
and queue execution belong in `vibecomfy.runtime` and command-layer checks.
