# Notification authority consolidation

The cloud notification admission database is now admission/projection-only.
Its former local authority and provider-attempt tables are retired on open;
legacy occurrence rows are copied without the authority JSON column and old
provider/transition rows are discarded as non-authoritative evidence.

The cloud `notification:discord` outbox destination remains only as an
explicit, non-dispatchable migration record. The resident completion effect
`resident-subagent-completion:<run_id>` is the sole current delivery identity
and is consumed through `EffectProtocol`/`DeliveryEffects` when that adapter
is configured. A configured effect rejection cannot fall through to a direct
provider call.

Resident escalation authorization requires a canonical delivery receipt bound
to the resident effect identity, reservation, outbox record, and completed
provider outcome. Legacy sidecar `delivered` records remain read-only evidence.

The shell wrapper direct `DISCORD_DM_BIN` path and its sidecar lifecycle writes
are intentionally not changed in this migration. They remain a residual
dependency for the separately tracked wrapper migration.
