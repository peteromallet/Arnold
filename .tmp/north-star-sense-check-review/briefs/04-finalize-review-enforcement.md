You are a DeepSeek subagent doing an evidence-cited sense-check in `/Users/peteromalley/Documents/Arnold`.

Review `docs/arnold/megaplan-north-star-sense-checks-revise-design.md`, focusing only on finalize and review enforcement.

Inspect finalize prompt/handler/schema, review prompt/handler/schema, how task sense checks/user actions are represented, and how review returns needs_rework/blocked/done.

Questions:
1. Is it correct that finalize should lower North Star actions into tasks/sense_checks/user_actions where needed?
2. Can review currently block on missing evidence for closeout-critical actions, or does new schema/logic need to be added?
3. How should `reject_closeout` be enforced after execution?
4. Any issue with overloading existing `sense_checks`?
5. What tests would prove this is not narrative-only?

Return under 900 words. Lead with Verdict: sound / mostly sound with amendments / flawed. Cite file:line evidence.
