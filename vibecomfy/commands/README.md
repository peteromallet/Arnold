# Commands

CLI command implementations live here. The console entrypoint is
`vibecomfy.cli:main`, and top-level command registration is explicit in this
package.

Each command module should expose `register(subparsers)` and keep command
execution in private `_cmd_*` helpers. Internal shared command helpers are
prefixed with `_`.
