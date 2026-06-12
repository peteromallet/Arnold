Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: inspect `.megaplan/tickets/` and classify tracked versus ignored ticket files.

Use:
- `git ls-files .megaplan/tickets`
- `find .megaplan/tickets -maxdepth 1 -type f | sort`
- `sed -n '1,160p' .megaplan/tickets/01KRKQGP81Z5XR0FAK19T5CAC8-first-class-workflow-runtime-contracts-for-vibecomfyreighastrid.md`
- `sed -n '1,160p' .megaplan/tickets/01KRNDP7S3BW6DMNKAWPNVVYMB-systematically-replace-positional-workflow-outputs-with-named-handles.md`

Do not edit files.

Questions:
1. Are the two tracked tickets backlog source-of-truth or stale ticket artifacts?
2. Do the ignored ticket files look valuable enough to document as local backlog, or should they remain ignored runtime/user state?
3. Should `.megaplan/tickets/` be documented in a README?

Return exact recommendations and deletion risks.
