-- M3: Add proposal_policy column to timeline_agent_sessions
-- Clients send proposal_policy: 'always' | 'immediate' in the invoke body.
-- The edge reads this and maps it to timelineMutationMode for the agent loop.
-- Persisting it allows session continuity — continuation invocations
-- (which omit user_message) can read back the active policy from the session row.

-- Column: proposal_policy (nullable text)
-- Values: 'always', 'immediate', or NULL (treated as 'immediate')
-- Default: NULL — absent policy is equivalent to 'immediate'

do $$
begin
  if not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'timeline_agent_sessions'
      and column_name = 'proposal_policy'
  ) then
    alter table public.timeline_agent_sessions
    add column proposal_policy text;

    -- Constraint: only allow known values when set
    alter table public.timeline_agent_sessions
    add constraint timeline_agent_sessions_proposal_policy_check
    check (
      proposal_policy is null
      or proposal_policy in ('always', 'immediate')
    );
  end if;
end
$$;

comment on column public.timeline_agent_sessions.proposal_policy is
  'Proposal mode policy for this session. ''always'' means the agent returns proposals instead of applying mutations directly. NULL or ''immediate'' means direct mutation (default).';
