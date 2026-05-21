# Add `--no-color` to `megaplan status`

I want `megaplan status` to accept a `--no-color` flag that strips ANSI escape codes
from its output. This is a small, well-scoped change.

Please drive this through megaplan — pick whatever profile and robustness you think
fit. I trust your judgment on the dials. The change should include a test.

Done = the flag works, a test passes, and the megaplan run reaches state `done` or
`reviewed`.
