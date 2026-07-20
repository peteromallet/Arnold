Own the general operating-process design requested by the user, and serve as the synthesis/delivery owner for the whole request.

First, find and consume the completed result of the internal implementation contributor in synthesis group msg-7a89d97b4b53. Do not duplicate its ownership. If it is still running, use bounded resident status checks until its terminal result is available; do not babysit indefinitely.

Then investigate and define the default policy for user-requested execution work, grounded in the current resident delegation policy, git/worktree behavior, delivery mechanics, and actual failure modes. The proposed default should answer explicitly:
- When a request says to do something, should the delegated agent implement and deliver it rather than merely advise?
- When should it use an isolated worktree?
- What is the default target branch and integration method?
- When may it merge/push/restart automatically, and what requires approval?
- How should tentative, speculative, review-only, or ambiguous work differ?
- What verification and durable evidence are required before claiming completion?
- How do multiple agents avoid overlapping ownership and ensure one delivery owner?

Prefer a practical policy: implementation work normally happens in an isolated worktree and is integrated into the explicitly requested target branch once verified; however, do not assume authorization for literal `main`, remote push, deployment, destructive cleanup, or externally consequential actions when the request does not imply them. Distinguish local integration from remote/deployment authority precisely.

If there is a canonical resident policy/config/documentation location where this rule can safely and durably be encoded without conflicting with active unrelated work, implement the smallest well-tested change there in an isolated worktree and integrate it into the appropriate branch. If no such location is clearly authoritative, produce a concrete recommended policy and identify the exact follow-up needed rather than scattering prose into an arbitrary document. Search `.megaplan/initiatives` by rough title/description before creating any planning asset; never write planning docs under `.megaplan/briefs`.

Finally, deliver one concise user-facing completion consolidating both the implementation contributor's evidenced outcome and this general-process result. Clearly separate completed actions from recommendations and unknowns. Never claim launch, merge, push, restart, or delivery without durable evidence.
