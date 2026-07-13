# Investigate false subagent launch claims

Determine exactly what happened when the Discord resident claimed it launched these two investigations:

- `subagent-20260713-170458-80af9232`
- `subagent-20260713-170549-309d39b1`

The originating Discord conversation is `rconv_85a1c2bfd5f1`; the current inbound message asks whether those agents actually launched and requests a log-backed root cause.

Inspect the canonical resident-managed agent run root, manifests, logs, results, resident message records, lifecycle/outbox records, and any relevant runtime logs. Establish for each claimed run ID whether:

1. a launch command/tool call actually occurred;
2. a durable manifest was committed;
3. a worker process was started;
4. it completed, failed, was superseded, or never existed;
5. terminal Discord delivery was attempted or occurred.

Then explain how the assistant produced a concrete run ID if no durable launch happened. Identify the precise control-flow, persistence, tool-call, validation, or response-generation defect, with code/log evidence. Check whether the run IDs appear anywhere outside the user-visible assistant messages. Do not infer success from the text alone.

This is diagnosis only: do not edit code, restart services, launch replacements, or alter chain state. Produce a concise verified summary suitable for automatic reply to the exact originating Discord message, and retain detailed evidence in the durable run log/result.
