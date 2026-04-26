alter table public.generations
  add column if not exists storage_mode text not null default 'remote'
    check (storage_mode in ('remote', 'local', 'uploading')),
  add column if not exists local_handle_id uuid null,
  add column if not exists local_file_name text,
  add column if not exists local_file_size bigint,
  add column if not exists local_file_mime text;

create table if not exists public.local_media_handles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid null references public.projects(id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists local_media_handles_user_id_idx
  on public.local_media_handles (user_id);

create index if not exists local_media_handles_project_id_idx
  on public.local_media_handles (project_id);

alter table public.generations
  drop constraint if exists generations_local_handle_id_fkey;

alter table public.generations
  add constraint generations_local_handle_id_fkey
  foreign key (local_handle_id)
  references public.local_media_handles(id)
  on delete set null;

alter table public.local_media_handles enable row level security;

drop policy if exists "Users can view own local media handles" on public.local_media_handles;
create policy "Users can view own local media handles"
  on public.local_media_handles
  for select
  using (auth.uid() = user_id);

drop policy if exists "Users can insert own local media handles" on public.local_media_handles;
create policy "Users can insert own local media handles"
  on public.local_media_handles
  for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can delete own local media handles" on public.local_media_handles;
create policy "Users can delete own local media handles"
  on public.local_media_handles
  for delete
  using (auth.uid() = user_id);
