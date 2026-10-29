-- Run this ONCE in Supabase: Dashboard -> SQL Editor -> New query -> paste -> Run

create table if not exists jobs (
  job_id      text primary key,
  title       text,
  company     text,
  location    text,
  city        text,
  job_type    text,
  salary      text,
  description text,
  skills      text[],
  url         text,
  source      text,
  posted_date timestamptz,
  created_at  timestamptz default now()
);

create table if not exists users (
  email      text primary key,
  name       text,
  skills     text[],
  keywords   text,
  location   text,
  watchlist  text[],
  created_at timestamptz default now()
);

create table if not exists alerts (
  id          bigint generated always as identity primary key,
  user_email  text,
  job_id      text,
  match_score numeric,
  sent_at     timestamptz default now(),
  unique (user_email, job_id)
);

-- College demo only: turn off row-level security so the app can read/write.
-- (Future scope: enable RLS + proper authentication.)
alter table jobs   disable row level security;
alter table users  disable row level security;
alter table alerts disable row level security;
