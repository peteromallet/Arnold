# Native Platform Security Posture

Security production coverage is broker-first. The agent process asks for
decisions and scoped proxy credentials; the broker owns covered secrets and
returns sanitized results.

## Coverage Matrix

| Area | Production-covered behavior | Local-only behavior | Production bypass rule |
| --- | --- | --- | --- |
| Brokered git actions | Protected branch pushes are denied; force operations, branch deletes, PR merges, and credential escalation require approval. | Tests may call `BrokerService.handle_payload()` directly. | Do not call git/gh helpers for protected actions without broker evaluation. |
| Provider proxy | Covered API-key providers use broker-issued proxy credentials in broker production mode. | Local unbrokered provider keys are development-only. | Do not expose upstream provider keys to agent-visible env or audit payloads. |
| Credential non-exposure | Broker status reports configured secret names/counts, never values; request/response payloads are redacted. | Fake tokens may be present only in test-local mappings and must be asserted absent from outputs. | Do not log, echo, or persist raw credentials. |
| Audit refs | Broker audit entries are keyed by run ID and step path and store sanitized effect refs, prompt refs, completion refs, and metadata. | In-memory audit helpers are acceptable for deterministic tests. | Do not store raw prompts, completions, tokens, or command secrets in audit metadata. |
| Approval gates | Approval-required verdicts suspend or route to operator controls before the side effect executes. | Fixtures may synthesize approval grants. | Do not convert approval-required verdicts into allow in production code. |
| Cancellation | Cancellation is a terminal security and execution control; subsequent protected actions must be denied or ignored. | Local tests may model cancellation as a lease state. | Do not resume broker-covered effects after cancellation without a new run/lease. |
| Audit lookup | Operators can look up sanitized refs by run/step; lookup proves existence and redaction, not secret content. | Tests may claim entries from the in-memory audit map. | Do not make secret recovery an audit feature. |

## Production Notes

Fail-closed behavior is part of the security contract. If broker mode is
configured and the broker is unavailable, covered actions are denied. If LLM
proxy production mode is enabled and no proxy credential can be issued, covered
provider access is unavailable rather than downgraded to raw-key mode.
