-- Sprint 8 (SD-027 + SD-034): render-output bucket for `banodoco_render_timeline`.
--
-- The banodoco-worker uploads themed-timeline MP4s to
-- `<user_id>/<timeline_id>/<task_id>.mp4` in this bucket. The user-first
-- folder convention matches `timeline-assets` (see
-- 20260325090001_create_timeline_assets_bucket.sql) so the same RLS
-- shape carries over. Service-role uploads do not go through these
-- policies; they exist so a signed-in user can read their own renders
-- back through the regular Supabase client.
--
-- We do NOT make the bucket public — render outputs are user-private.
-- The editor builds signed URLs via the standard storage SDK when it
-- needs to surface a download link.

insert into storage.buckets (id, name, public)
values ('render-outputs', 'render-outputs', false)
on conflict (id) do update
set public = excluded.public;

drop policy if exists "render_outputs_select" on storage.objects;
create policy "render_outputs_select"
  on storage.objects
  for select
  using (
    bucket_id = 'render-outputs'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

drop policy if exists "render_outputs_insert" on storage.objects;
create policy "render_outputs_insert"
  on storage.objects
  for insert
  with check (
    bucket_id = 'render-outputs'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

drop policy if exists "render_outputs_update" on storage.objects;
create policy "render_outputs_update"
  on storage.objects
  for update
  using (
    bucket_id = 'render-outputs'
    and auth.uid()::text = (storage.foldername(name))[1]
  )
  with check (
    bucket_id = 'render-outputs'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

drop policy if exists "render_outputs_delete" on storage.objects;
create policy "render_outputs_delete"
  on storage.objects
  for delete
  using (
    bucket_id = 'render-outputs'
    and auth.uid()::text = (storage.foldername(name))[1]
  );
