-- Apply only after backing up your tables and storage.
-- The unified Streamlit server uses a server-only service_role key;
-- browser/anon client operations must no longer have public access.
begin;

drop policy if exists "public read characters" on public.characters;
drop policy if exists "public write characters" on public.characters;
drop policy if exists "public read app_state" on public.app_state;
drop policy if exists "public write app_state" on public.app_state;
drop policy if exists "public read chat" on public.chat_messages;
drop policy if exists "public insert chat" on public.chat_messages;
drop policy if exists "public delete chat" on public.chat_messages;

alter table public.characters enable row level security;
alter table public.app_state enable row level security;
alter table public.chat_messages enable row level security;

drop policy if exists "public read rpg assets" on storage.objects;
drop policy if exists "public upload rpg assets" on storage.objects;
drop policy if exists "public update rpg assets" on storage.objects;

-- Existing image URLs remain public because the bucket itself is public.
-- Public clients cannot upload/update via RLS without an appropriate policy.
update storage.buckets
set allowed_mime_types = array['image/png','image/jpeg','image/webp','image/gif']
where id = 'rpg-assets';

commit;
