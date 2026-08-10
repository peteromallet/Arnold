# Luna explorer 5 — provider route, credentials, and bootstrap authority

You are GPT-5.6 Luna, read-only, high reasoning. Do not edit files, launch
cloud commands, or use collaboration tools. Never print or inspect secret
values. Return under 1200 words.

Read `sol-p2-framing-result-20260804.md`, `sol-final-plan-20260804.md`, and
`current-provider-preflight-20260804.md`. Known symptom: resume omitted
`/workspace/.cloud-hot-env`; metadata and active-step labels could disagree
with batch receipts; several provider/alias registries exist.

Audit `runtime/key_pool.py`, provider/adapter resolution, Hermes launch paths,
cloud preflight/bootstrap, phase routing, batch receipt creation, and any
provider registry or alias maps. Trace requested role/model → resolved provider,
endpoint/auth rule → actual batch receipt without exposing secrets.

Recommend one role-scoped provider authority record and a bounded remote
preflight before leasing. Distinguish legitimate orchestration-model versus
task-model differences from accidental drift. Provide acceptance tests for
missing env sourcing, bad auth, unsupported alias, endpoint mismatch, timeout,
and a valid GLM route; prove failed preflight cannot publish `executing`.
