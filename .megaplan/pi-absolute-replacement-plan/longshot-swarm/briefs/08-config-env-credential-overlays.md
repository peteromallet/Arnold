Working directory: /Users/peteromalley/Documents/Arnold

Task: Find configuration, env var, credential, and override surfaces not fully captured by current plan.

Focus areas:
- env var reads (MEGAPLAN_*, ARNOLD_*, HERMES_*, CLAUDE*, CODEX*, provider keys)
- config files and config resolver code
- credential/key pool behavior
- profile override flags such as vendor/critic/phase-model/depth
- tests around routing degraded, credential detection, writable roots

Output:
- Missing inventory docs/gates or plan edits.
- Specific file/path evidence.
- Keep under 900 words.
