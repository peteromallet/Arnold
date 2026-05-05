alter table public.tasks
  add column if not exists materialized_inputs jsonb;

comment on column public.tasks.materialized_inputs is
  'Per-task materializations of local-only generation inputs. Array of records with shape: { generation_id: uuid, kind: ''file'' | ''remote'', target: text }. ''file'' targets are absolute paths on the local worker host (cleaned up worker-side at job-end). ''remote'' targets are storage object paths uploaded on-demand (cleaned up by complete_task). Null when no inputs needed materialization.';
