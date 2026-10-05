-- ==============================================================================
-- ATS RESUME CREATOR AUTOMATION - SUPABASE DATABASE SCHEMA
-- ==============================================================================
-- Instructions:
-- Copy and paste this entire script into your Supabase Dashboard:
-- SQL Editor -> New Query -> Run
-- ==============================================================================

-- 1. Jobs Table
CREATE TABLE IF NOT EXISTS public.jobs (
    job_id TEXT PRIMARY KEY,
    source TEXT,
    url TEXT,
    title TEXT,
    company TEXT,
    location TEXT,
    employment_type TEXT,
    experience_min NUMERIC,
    experience_max NUMERIC,
    salary TEXT,
    description_raw TEXT,
    content_hash TEXT,
    discovered_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Match Reports Table
CREATE TABLE IF NOT EXISTS public.match_reports (
    job_id TEXT PRIMARY KEY REFERENCES public.jobs(job_id) ON DELETE CASCADE,
    overall_score NUMERIC,
    score_breakdown_json JSONB,
    matched_reqs_json JSONB,
    missing_reqs_json JSONB,
    recommendation TEXT,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Applications Table
CREATE TABLE IF NOT EXISTS public.applications (
    application_id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES public.jobs(job_id) ON DELETE CASCADE,
    resume_version TEXT,
    match_score NUMERIC,
    status TEXT,
    user_decision TEXT DEFAULT 'pending',
    output_directory TEXT,
    notes TEXT,
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    outcome TEXT
);

-- Row Level Security (RLS) Policies Configuration
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.match_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;

-- Allow all operations for authenticated, anon, and service_role API keys
CREATE POLICY "Allow read/write access to jobs" ON public.jobs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow read/write access to match_reports" ON public.match_reports FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow read/write access to applications" ON public.applications FOR ALL USING (true) WITH CHECK (true);
