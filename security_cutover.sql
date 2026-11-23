-- Midnight Sun — staged security cutover (DO NOT RUN BEFORE BACKUP AND SECRETS).
-- Does not delete character data, chat data or existing image objects.
-- Once applied, all apps must use server-side SUPABASE_SERVICE_ROLE_KEY.
-- Reversible separately by restoring the old policies (but DO NOT leave public
-- access enabled after enabling the new protected apps).

begin;

alter table public.characters enable row level security;
alter table public.app_state enable row level security;
alter table public.chat_messages enable row level security;

drop policy if exists "public read characters" on public.characters;
drop policy if exists "public write characters" on public.characters;
drop policy if exists "public read app_state" on public.app_state;
drop policy if exists "public write app_state" on public.app_state;
drop policy if exists "public read chat" on public.chat_messages;
drop policy if exists "public insert chat" on public.chat_messages;
drop policy if exists "public delete chat" on public.chat_messages;

-- Harden any future direct access through the anon key.
revoke all on public.characters from anon, authenticated;
revoke all on public.app_state from anon, authenticated;
revoke all on public.chat_messages from anon, authenticated;

drop policy if exists "public read rpg assets" on storage.objects;
drop policy if exists "public upload rpg assets" on storage.objects;
drop policy if exists "public update rpg assets" on storage.objects;

-- NOTE: rpg-assets is still a PUBLIC bucket so old image URLs keep rendering.
-- This prevents anonymous uploads but does not make previously published images
-- private. A future signed URL migration is needed to protect image content.

commit;
