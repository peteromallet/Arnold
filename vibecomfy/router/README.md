# Router

Workflow route selection lives here. The router maps high-level verbs such as
image text-to-image or video image-to-video onto ready-template ids plus
applicable patches.

Rules are data-like and evaluated by `_core.py`. Keep public callers on
`vibecomfy.router.pick(...)` or the verb-native `vibecomfy.image` /
`vibecomfy.video` namespaces.
