-- TechPulse TW — PostgreSQL Schema
-- Run once to initialise the database:
--   psql -U techpulse -d techpulse_db -f scripts/setup_db.sql

-- ── Raw job listings ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    job_id          TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    company         TEXT,
    company_size    TEXT,
    location        TEXT,
    industry        TEXT,
    salary_min      INTEGER DEFAULT 0,   -- Monthly TWD; 0 = undisclosed
    salary_max      INTEGER DEFAULT 0,
    salary_type     TEXT,
    experience      TEXT,
    education       TEXT,
    posted_date     DATE,
    scraped_at      TIMESTAMPTZ DEFAULT NOW(),
    raw_json        JSONB                -- Full original record for reprocessing
);

CREATE INDEX IF NOT EXISTS idx_jobs_industry  ON jobs (industry);
CREATE INDEX IF NOT EXISTS idx_jobs_posted    ON jobs (posted_date DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_company   ON jobs (company);

-- ── Skills extracted per job ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_skills (
    id      SERIAL PRIMARY KEY,
    job_id  TEXT REFERENCES jobs(job_id) ON DELETE CASCADE,
    skill   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_skills_skill  ON job_skills (skill);
CREATE INDEX IF NOT EXISTS idx_job_skills_job_id ON job_skills (job_id);

-- ── Aggregated skill demand snapshots (written by pipeline daily) ───────────
CREATE TABLE IF NOT EXISTS skill_demand_snapshot (
    snapshot_date   DATE NOT NULL,
    skill           TEXT NOT NULL,
    job_count       INTEGER NOT NULL,
    share_pct       NUMERIC(5,2),
    PRIMARY KEY (snapshot_date, skill)
);

-- ── Aggregated salary distribution snapshots ────────────────────────────────
CREATE TABLE IF NOT EXISTS salary_dist_snapshot (
    snapshot_date   DATE NOT NULL,
    bucket          TEXT NOT NULL,
    count           INTEGER NOT NULL,
    PRIMARY KEY (snapshot_date, bucket)
);

-- ── Pipeline run log ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id          SERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    jobs_scraped    INTEGER,
    jobs_inserted   INTEGER,
    status          TEXT DEFAULT 'running',   -- running | success | failed
    error_message   TEXT
);
