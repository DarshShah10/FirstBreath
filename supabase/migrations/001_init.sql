-- FirstBreath initial schema
-- Applied automatically by backend/scripts/apply_migrations.py via DATABASE_URL.

-- Simulations: a scenario context that can hold multiple cases and runs
create table if not exists simulations (
    id text primary key,
    status text not null default 'created',
    meta jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Emergency cases submitted to a simulation
create table if not exists cases (
    id text primary key,
    simulation_id text references simulations(id) on delete cascade,
    distress_signal jsonb not null,
    status text not null default 'pending',   -- pending | simulating | completed | failed
    outcome jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_cases_simulation on cases(simulation_id);

-- A single execution of the engine over a simulation's cases
create table if not exists runs (
    id text primary key,
    simulation_id text references simulations(id) on delete cascade,
    status text not null default 'running',   -- running | completed | failed | stopped
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    results jsonb,
    metrics jsonb
);
create index if not exists idx_runs_simulation on runs(simulation_id);

-- Append-only event log: every action, message, state-change (agent transcript in Phase 2+)
create table if not exists events (
    id bigint generated always as identity primary key,
    run_id text references runs(id) on delete cascade,
    sim_time double precision,               -- simulated clock position (minutes)
    agent_id text,
    agent_type text,                          -- dispatcher | ambulance | hospital | world | system
    event_type text not null,                 -- dispatch | reroute | pre_alert | ot_ready | radio | step ...
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create index if not exists idx_events_run on events(run_id, id);

-- Generated mission briefings / debrief artifacts for a run
create table if not exists reports (
    id text primary key,
    run_id text references runs(id) on delete cascade,
    case_id text,
    content jsonb,                            -- structured sections / interventions
    markdown text,                            -- rendered briefing
    created_at timestamptz not null default now()
);
create index if not exists idx_reports_run on reports(run_id);
