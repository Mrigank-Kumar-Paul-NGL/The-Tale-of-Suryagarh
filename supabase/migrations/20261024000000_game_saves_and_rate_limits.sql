-- One save per anonymous player. The game server is the only client (secret key); browsers never touch tables.
create table public.player_saves (
  player_hash text primary key check (char_length(player_hash) = 64),
  state jsonb not null,
  updated_at timestamptz not null default now()
);

-- Fixed-window request counters used to cap LLM calls per player and per IP.
create table public.rate_limits (
  bucket text not null,
  window_start timestamptz not null,
  hits integer not null default 0,
  primary key (bucket, window_start)
);
create index rate_limits_window_idx on public.rate_limits (window_start);

alter table public.player_saves enable row level security;
alter table public.rate_limits enable row level security;
revoke all on public.player_saves from anon, authenticated;
revoke all on public.rate_limits from anon, authenticated;

create or replace function public.hit_rate_limit(p_bucket text, p_window_seconds integer, p_limit integer)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  w timestamptz := to_timestamp(floor(extract(epoch from now()) / p_window_seconds) * p_window_seconds);
  n integer;
begin
  insert into public.rate_limits as r (bucket, window_start, hits)
  values (p_bucket, w, 1)
  on conflict (bucket, window_start) do update set hits = r.hits + 1
  returning hits into n;
  delete from public.rate_limits where window_start < now() - interval '2 days';
  return n <= p_limit;
end;
$$;
revoke execute on function public.hit_rate_limit(text, integer, integer) from public, anon, authenticated;
grant execute on function public.hit_rate_limit(text, integer, integer) to service_role;
