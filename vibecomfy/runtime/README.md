# Runtime

Runtime execution, embedded/server session management, watchdog handling, and
model policy checks live here.

Public callers should prefer the package-level runtime helpers such as
`run_sync`, `run_embedded_sync`, and `vibecomfy run`. Direct imports from this
package are for runtime internals, focused tests, and command implementations.
