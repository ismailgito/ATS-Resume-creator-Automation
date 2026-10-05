# 📖 ATS Resume Automation — Complete User Guide

> **For any profession, experience level, and use case.**
> This guide covers everything from initial setup to scheduled automation with Supabase tracking.

---

## Table of Contents

1. [How It Works](#1-how-it-works)
2. [Step 1 — Install & Setup](#2-step-1--install--setup)
3. [Step 2 — Configure Your Candidate Profile](#3-step-2--configure-your-candidate-profile)
4. [Step 3 — Configure Your Target Profile](#4-step-3--configure-your-target-profile)
5. [Step 4 — Connect Supabase Database](#5-step-4--connect-supabase-database)
6. [Step 5 — Add API Keys (Optional but Powerful)](#6-step-5--add-api-keys-optional-but-powerful)
7. [Step 6 — Ingest & Process Jobs](#7-step-6--ingest--process-jobs)
8. [Step 7 — Review & Decide](#8-step-7--review--decide)
9. [Step 8 — Schedule Automation](#9-step-8--schedule-automation)
10. [Scoring System Explained](#10-scoring-system-explained)
11. [Customize Scoring & Policy](#11-customize-scoring--policy)
12. [Real-World Use Case Examples](#12-real-world-use-case-examples)
13. [Profile Templates for Different Professions](#13-profile-templates-for-different-professions)
14. [Troubleshooting](#14-troubleshooting)
15. [CLI Quick-Reference Card](#15-cli-quick-reference-card)

---

## 1. How It Works

The automation runs a **6-stage pipeline** for every job you feed it:

```
Job Input (Text / File / URL / CSV)
    │
    ▼
📥 INGEST — Normalize & deduplicate raw job description
    │
    ▼
🔍 PARSE — Extract title, skills, tools, experience range, industry
    │
    ▼
📊 SCORE — 7-factor match against your Candidate Profile (0–100)
    │
    ▼  (score ≥ MIN_MATCH_SCORE threshold)
✍️  TAILOR — Adapt resume bullets & summary to job requirements
    │
    ▼
📄 RENDER — Generate .md, .docx, .pdf resume + cover note
    │
    ▼
✅ VALIDATE — Fact-check against your profile & policy rules
    │
    ▼
💾 TRACK — Save result to Supabase; await your human decision
```

> [!IMPORTANT]
> The system **never submits applications automatically**. Every application requires your explicit `decide` command (`apply`, `save`, or `reject`). You are always in control.

---

## 2. Step 1 — Install & Setup

### Prerequisites
- Python 3.10 or newer
- A Supabase account (free tier works perfectly)
- Git

### Install the project

```powershell
# 1. Clone the repository
git clone <your-repo-url>
cd ATS-Resume-creator-Automation

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1     # Windows PowerShell
# OR
source .venv/bin/activate       # macOS / Linux

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Verify the system is working
python -m src.cli check-env
```

Expected output:
```
=================================================================
       ATS RESUME AUTOMATION - SYSTEM & CREDENTIAL STATUS
=================================================================
Project Directory : C:\...\ATS-Resume-creator-Automation
Candidate Profile : data/candidate-profile.json (Found)
Supabase Database : Not configured (using memory)
Current LLM Mode  : OFFLINE
-----------------------------------------------------------------
CREDENTIALS STATUS:
  * Gemini Api            : [--] Not configured (Offline mode ready)
  ...
  * Supabase Database     : [--] Not configured (Offline mode ready)
>> Status: Running in DETERMINISTIC OFFLINE MODE.
```

> [!NOTE]
> The system works **fully offline in deterministic mode** without any API keys. You can generate tailored resumes right away. API keys only unlock LLM-powered smart generation as an upgrade.

---

## 3. Step 2 — Configure Your Candidate Profile

The **Candidate Profile** is the single source of truth about you — your skills, experience, achievements, and strict factual constraints the system will never violate.

**File location:** `data/candidate-profile.json`

### Full Schema Reference

```jsonc
{
  // ─── Identity ──────────────────────────────────────────────
  "candidate_id": "cand-001",         // Any unique ID for yourself
  "full_name": "Your Full Name",
  "headline": "Role Title | Specialization | Key Value Metric",

  // ─── Contact ───────────────────────────────────────────────
  "contact": {
    "email": "you@example.com",
    "phone": "+91 99999 88888",
    "location": "City, Country",
    "linkedin": "https://linkedin.com/in/your-profile",
    "portfolio": "https://yourportfolio.com"   // Optional
  },

  // ─── Target Roles ──────────────────────────────────────────
  // These are used for title-fit scoring. Include variations
  // and synonyms of the roles you are actively targeting.
  "target_roles": [
    "Product Manager",
    "Associate Product Manager",
    "Senior Product Manager"
  ],

  // ─── Experience ────────────────────────────────────────────
  "experience_years": 3.5,           // Your total years of work experience
  "location": "Bengaluru, India",
  "work_authorization": "Citizen / Authorized",
  "notice_period_days": 30,
  "current_ctc_lpa": 12.0,           // Optional, used for self-tracking only
  "expected_ctc_lpa": 18.0,

  // ─── Summary Facts ─────────────────────────────────────────
  // 3-5 factual statements that anchor your professional summary.
  // The AI uses these to construct your resume Summary section.
  "summary_facts": [
    "3.5 years in product management across B2B SaaS and fintech",
    "Led 0→1 launch of a mobile app with 50,000 MAUs in 6 months",
    "Cross-functional team leader coordinating engineering, design, and data"
  ],

  // ─── Skills ────────────────────────────────────────────────
  // Your actual skills. Only list skills you genuinely have.
  "skills": [
    "Product Roadmapping",
    "Agile / Scrum",
    "User Story Writing",
    "A/B Testing",
    "SQL & Data Analysis",
    "Stakeholder Management"
  ],

  // ─── Tools ─────────────────────────────────────────────────
  // Software tools, platforms, frameworks you have actually used.
  "tools": [
    "Jira",
    "Confluence",
    "Figma",
    "Mixpanel",
    "Amplitude",
    "Postman",
    "Looker"
  ],

  // ─── Achievements ──────────────────────────────────────────
  // Verified, quantified accomplishments with evidence.
  // This section is the most important for tailoring.
  "achievements": [
    {
      "id": "ach-01",
      "statement": "Launched redesigned onboarding flow that reduced time-to-value from 14 days to 3 days.",
      "metric": "78% reduction in time-to-value",
      "time_period": "Q3 2024",
      "evidence": "Amplitude retention funnel dashboard"
    },
    {
      "id": "ach-02",
      "statement": "Led cross-functional team of 8 to ship mobile payment feature on schedule, adding $500K ARR.",
      "metric": "$500K ARR contributed",
      "time_period": "Q1 2024",
      "evidence": "Product launch memo & revenue report"
    }
  ],

  // ─── Employment History ─────────────────────────────────────
  "employment": [
    {
      "company": "Acme SaaS",
      "title": "Product Manager",
      "location": "Bengaluru, India (Hybrid)",
      "start_date": "2022-06",
      "end_date": "Present",
      "is_current": true,
      "responsibilities": [
        "Define and prioritize the product roadmap for the B2B dashboard module.",
        "Write PRDs and user stories, coordinating delivery with a 6-person engineering squad.",
        "Track product health metrics using Amplitude and present findings to executive stakeholders."
      ]
    }
  ],

  // ─── Education ─────────────────────────────────────────────
  "education": [
    {
      "institution": "IIT Bombay",
      "degree": "B.Tech in Computer Science",
      "start_year": 2018,
      "end_year": 2022,
      "grade": "8.4 CGPA"
    }
  ],

  // ─── Certifications ────────────────────────────────────────
  "certifications": [
    {
      "name": "AWS Certified Solutions Architect – Associate",
      "issuer": "Amazon Web Services",
      "date": "2023-09",
      "url": "https://aws.amazon.com/certification/verify"
    }
  ],

  // ─── Links ─────────────────────────────────────────────────
  "links": [
    { "name": "LinkedIn", "url": "https://linkedin.com/in/you" },
    { "name": "GitHub", "url": "https://github.com/you" }
  ],

  // ─── Negative Constraints ──────────────────────────────────
  // CRITICAL: These rules are enforced strictly.
  // List any skills, tools, or claims the system must NEVER make.
  // If a job requires something on this list, it will be flagged.
  "negative_constraints": [
    "Do NOT claim AWS Certified DevOps Engineer (only have Associate level)",
    "Do NOT claim Kubernetes or Terraform experience (never used in production)",
    "Do NOT claim management of teams larger than 3 people",
    "Do NOT claim more than 4 years of experience"
  ]
}
```

> [!CAUTION]
> **Always fill `negative_constraints` carefully.** This is your safety net — it prevents the AI from hallucinating skills or experience you don't have. Every tool or certification you haven't used professionally should be listed here.

---

## 4. Step 3 — Configure Your Target Profile

The **Target Profile** tells the system what kinds of jobs you are looking for. This is used for filtering, scoring calibration, and location/compensation matching.

**File location:** `config/target-profile.yaml`

### Full Schema Reference

```yaml
# ─── Roles you are targeting ─────────────────────────────────
# These role names anchor the Title Fit scoring (20% of total score).
# Include common variations and synonyms.
target_roles:
  - "Software Engineer"
  - "Backend Engineer"
  - "Senior Software Engineer"
  - "SWE II"

# ─── Experience Range ────────────────────────────────────────
# Jobs outside this band will score lower on experience_fit.
experience_range:
  min_years: 2.0          # Skip roles requiring more than max_years
  max_years: 6.0
  preferred_years: 3.5    # Your actual years, for optimal scoring

# ─── Location Preferences ────────────────────────────────────
location_preferences:
  work_modes:
    - "Remote"
    - "Hybrid"
    - "On-site"
  preferred_cities:
    - "Bengaluru"
    - "Hyderabad"
    - "Pune"
    - "Remote"
  relocation_willing: true    # Set false to penalize non-preferred cities

# ─── Compensation Expectations ───────────────────────────────
compensation:
  currency: "INR"
  min_annual: 1200000       # 12 LPA minimum
  target_annual: 1800000    # 18 LPA target
  notice_period_days: 30

# ─── Industry / Domain Preferences ──────────────────────────
# Used for industry_fit scoring (10% of total score).
key_domains:
  - "B2B SaaS"
  - "Fintech"
  - "Developer Tools"
  - "Enterprise Software"

# ─── Core Skills / Channels ──────────────────────────────────
# Used for required_skills and platform_tools scoring.
core_channels:
  - "Python"
  - "Go / Golang"
  - "PostgreSQL"
  - "REST APIs"
  - "Microservices"
  - "Docker"
  - "AWS"
```

---

## 5. Step 4 — Connect Supabase Database

### One-Time Supabase Setup (5 minutes)

**Step 1: Create a Supabase Project**
1. Go to [supabase.com](https://supabase.com) → click **New project**
2. Set a name (e.g., `ats-tracker`) and a database password
3. Choose the region closest to you → click **Create new project**
4. Wait ~2 minutes for provisioning

**Step 2: Create the Database Tables**
1. In your Supabase project → click **SQL Editor** in the left sidebar
2. Click **New query**
3. Copy the entire content of [`supabase_schema.sql`](supabase_schema.sql) and paste it in
4. Click **Run** (green button) — you should see `Success. No rows returned.`

**Step 3: Get Your API Credentials**
1. Go to **Project Settings** → **API** in the left sidebar
2. Copy:
   - **Project URL** — looks like `https://abcdefghijkl.supabase.co`
   - **anon public** key — the long JWT token under "Project API keys"

**Step 4: Add to your `.env` file**
```env
SUPABASE_URL=https://abcdefghijkl.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Step 5: Verify connection**
```powershell
python -m src.cli check-env
```

You should now see:
```
  * Supabase Database     : [OK] Configured
```

> [!TIP]
> Use the **anon public** key for normal usage. Switch to the **service_role** key only if you are running the automation on a private server and have disabled Row Level Security. The anon key is safe for local use.

---

## 6. Step 5 — Add API Keys (Optional but Powerful)

The system works without any LLM keys in **Offline / Deterministic Mode**. Adding a key upgrades to **Live LLM Mode** for smarter resume language and tailoring.

In your `.env` file, set `LLM_PROVIDER` and the corresponding key:

| Provider | `.env` Setting | Best For |
|---|---|---|
| **Google Gemini** | `LLM_PROVIDER=gemini` + `GEMINI_API_KEY=...` | Free tier available, fast |
| **OpenAI** | `LLM_PROVIDER=openai` + `OPENAI_API_KEY=...` | Highest quality output |
| **Anthropic Claude** | `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY=...` | Best for long-form writing |
| **Offline (default)** | `LLM_PROVIDER=offline` | No key needed, instant |

```env
# Example: Activate Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...your-actual-key-here
GEMINI_MODEL=gemini-1.5-pro
```

---

## 7. Step 6 — Ingest & Process Jobs

This is your core daily workflow. You feed job descriptions in, and the pipeline processes them.

### Method A — Paste Raw Job Text (Most common)

Copy a job description from any website and paste it directly:

```powershell
python -m src.cli ingest `
  --text "Senior Software Engineer at Stripe. We are looking for a backend engineer with 3-5 years of experience in Python, Go, and distributed systems. Experience with PostgreSQL and AWS required. Remote friendly." `
  --title "Senior Software Engineer" `
  --company "Stripe"
```

To force resume generation regardless of score:
```powershell
python -m src.cli ingest --text "..." --title "..." --company "..." --force
```

### Method B — From a Text/Markdown File

Save a job description as a `.txt` or `.md` file and pass it in:

```powershell
# Save job description as a file first
"We are looking for a Data Scientist..." | Out-File -FilePath jobs\stripe-ds.txt

# Then ingest it
python -m src.cli ingest --file jobs\stripe-ds.txt --title "Data Scientist" --company "Stripe"
```

### Method C — From a JSON File

Create a structured JSON job file:

```json
{
  "job_id": "stripe-swe-001",
  "title": "Senior Software Engineer",
  "company": "Stripe",
  "location": "Remote",
  "source": "careers.stripe.com",
  "url": "https://stripe.com/jobs/listing/123",
  "employment_type": "full-time",
  "experience_min": 3,
  "experience_max": 6,
  "description_raw": "Full job description text goes here..."
}
```

```powershell
python -m src.cli ingest --file jobs\stripe-swe-001.json
```

### Method D — Batch Process a CSV File

Export jobs from Naukri, LinkedIn, or any job board as CSV:

```csv
title,company,location,url,description
"Senior PM","Razorpay","Bengaluru","https://...","We are looking for a Senior PM with 3+ years..."
"Product Manager","CRED","Bangalore","https://...","CRED is hiring a PM who can own product roadmap..."
```

```powershell
python -m src.cli ingest --file jobs\exported-jobs.csv
```

### Method E — Run Built-in Samples (Test the system)

```powershell
# Process a single sample job
python -m src.cli run-sample 01-perf-mktg-manager

# Process all 6 sample jobs at once
python -m src.cli run-sample all

# Force resume generation for all samples (ignores score threshold)
python -m src.cli run-sample all --force
```

### Understanding the Output

After ingestion, you'll see:
```
Ingesting and evaluating job: Senior Software Engineer at Stripe...

Match Score    : 87/100 (APPLY_REVIEW)
Reason         : Strong title, skill, and experience alignment. Minor gap: Kubernetes (not in profile).
Review Package Generated at: outputs\Stripe-20261005143022

PDF Resume  : outputs\Stripe-20261005143022\Stripe_Resume.pdf
DOCX Resume : outputs\Stripe-20261005143022\Stripe_Resume.docx

Next step: Run 'python -m src.cli review' to inspect or approve this application.
```

Your `outputs/` folder will contain:
```
outputs/
└── Stripe-20261005143022/
    ├── Stripe_Resume.md           ← Editable Markdown version
    ├── Stripe_Resume.docx         ← Word document (ATS-optimized)
    ├── Stripe_Resume.pdf          ← ATS-parseable PDF
    ├── Stripe_Cover-Note.md       ← Tailored cover letter
    ├── match-report.json          ← Score breakdown
    ├── validation-report.json     ← Quality gate results
    └── change-log.md              ← What was changed & why
```

---

## 8. Step 7 — Review & Decide

### See what's waiting for your review

```powershell
python -m src.cli review
```

Output:
```
======================================================================
                     APPLICATION REVIEW QUEUE
======================================================================
[1] App ID     : Stripe-20261005143022
    Job Title  : Senior Software Engineer
    Company    : Stripe
    Match Score: 87/100
    Status     : review_ready
    Decision   : pending
    Location   : outputs\Stripe-20261005143022
----------------------------------------------------------------------
[2] App ID     : Razorpay-20261005143555
    Job Title  : Senior Product Manager
    Company    : Razorpay
    Match Score: 62/100
    Status     : review_ready
    Decision   : pending
----------------------------------------------------------------------
```

### Record your decision

After reviewing the PDF/DOCX in the outputs folder:

```powershell
# Mark as ready to apply manually
python -m src.cli decide Stripe-20261005143022 apply --notes "Strong role, apply via careers portal today"

# Save for later without deciding yet
python -m src.cli decide Stripe-20261005143022 save --notes "Revisit after current interviews"

# Mark as applied (after you have manually submitted)
python -m src.cli decide Stripe-20261005143022 applied --notes "Submitted on Stripe careers portal"

# Reject
python -m src.cli decide Razorpay-20261005143555 reject --notes "Requires 5+ years, out of range"
```

| Decision | When to Use |
|---|---|
| `apply` | You have reviewed the resume and are ready to manually submit it |
| `applied` | You have already submitted the application manually |
| `save` | You want to review it later before deciding |
| `reject` | The job is not a fit or not worth pursuing |

### View Skill Gap Analytics

```powershell
python -m src.cli report
```

This shows your aggregate pipeline health and recurring skills that appeared in job descriptions but are missing from your profile — your **skill gap roadmap**.

---

## 9. Step 8 — Schedule Automation

### Option A — Windows Task Scheduler (No extra tools needed)

Create a batch file to run daily ingestion:

**`run_daily_jobs.bat`:**
```bat
@echo off
cd /d C:\Users\Lenovo\Documents\ATS-Resume-creator-Automation
call .venv\Scripts\activate.bat
python -m src.cli ingest --file jobs\daily-naukri-export.csv
python -m src.cli ingest --file jobs\daily-linkedin-export.csv
```

**Set up via Task Scheduler:**
1. Open **Task Scheduler** → **Create Basic Task**
2. Name: `ATS Resume Daily Run`
3. Trigger: **Daily** → set your preferred time (e.g., 8:00 AM)
4. Action: **Start a program** → Browse to `run_daily_jobs.bat`
5. Click **Finish**

### Option B — PowerShell Scheduled Job

```powershell
# Register a scheduled job to run every weekday at 8 AM
Register-ScheduledJob -Name "ATSResumeDaily" -ScriptBlock {
    Set-Location "C:\Users\Lenovo\Documents\ATS-Resume-creator-Automation"
    & .\.venv\Scripts\python.exe -m src.cli ingest --file jobs\daily-export.csv
} -Trigger (New-JobTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "8:00 AM")
```

### Option C — AGY `/schedule` Slash Command (Recommended)

Type `/schedule` in this chat to set a recurring automation reminder. This will prompt you daily to paste and process new jobs without leaving the chat interface.

### Option D — Batch Script for Multiple Job Sources

**`batch_process.ps1`:**
```powershell
# ATS Resume Automation - Daily Batch Processor
param (
    [string]$JobsFolder = ".\jobs\pending"
)

$python = ".\.venv\Scripts\python.exe"
$jobFiles = Get-ChildItem -Path $JobsFolder -Include "*.json","*.csv","*.txt" -File

Write-Host "=== ATS Automation Daily Run - $(Get-Date) ===" -ForegroundColor Cyan
Write-Host "Found $($jobFiles.Count) job file(s) to process"

foreach ($file in $jobFiles) {
    Write-Host "`nProcessing: $($file.Name)" -ForegroundColor Yellow
    & $python -m src.cli ingest --file $file.FullName

    # Move processed files to archive
    Move-Item $file.FullName ".\jobs\processed\" -Force
}

Write-Host "`n=== Processing Complete. Run 'review' to see queue ===" -ForegroundColor Green
& $python -m src.cli review
```

Run it:
```powershell
.\batch_process.ps1 -JobsFolder ".\jobs\pending"
```

---

## 10. Scoring System Explained

Each job is scored on **7 factors** (total = 100 points). You can see the breakdown in each `match-report.json`.

| Factor | Weight | What it checks |
|---|---|---|
| **Title / Role Fit** | 20% | How closely the job title matches your `target_roles` |
| **Required Skills** | 25% | Overlap between job's required skills and your `skills` list |
| **Platform & Tools** | 15% | Overlap between job's listed tools and your `tools` list |
| **Experience Fit** | 15% | Whether your `experience_years` is within the job's range |
| **Industry Fit** | 10% | Whether the company domain matches your `key_domains` |
| **Location Fit** | 5% | Whether work mode and city match your preferences |
| **Achievement Relevance** | 10% | Whether your achievements contain relevant keywords |

### Score Thresholds (configurable in `config/scoring.yaml`)

| Score Range | Recommendation | Action |
|---|---|---|
| **≥ 80** | `apply_review` | Resume generated automatically, lands in review queue |
| **65 – 79** | `medium_fit_review` | Resume generated with `--force`, manual consideration |
| **50 – 64** | `research_queue` | Score too low; use `--force` if you strongly want to apply |
| **< 50** | Rejected | No resume generated; likely a mismatch |

Change the auto-generate threshold in `.env`:
```env
MIN_MATCH_SCORE=70   # Default is 75. Lower to generate more, raise to be selective.
```

---

## 11. Customize Scoring & Policy

### Adjust Score Weights (`config/scoring.yaml`)

```yaml
weights:
  title_role_fit: 0.20        # Increase if title match is critical to you
  required_skills: 0.30       # Increase if skills are more important than title
  platform_tools: 0.15
  experience_fit: 0.10        # Decrease if you frequently apply outside your range
  industry_fit: 0.10
  location_fit: 0.05
  achievement_relevance: 0.10
```

> [!TIP]
> Weights must sum to 1.0. If you are switching careers (skills > title), increase `required_skills` and decrease `title_role_fit`.

### Add Tool Synonyms (`config/scoring.yaml`)

If you notice jobs using different names for the same tool, add synonyms:

```yaml
synonyms:
  python:
    - "python"
    - "python3"
    - "django"
    - "fastapi"
    - "flask"
  sql:
    - "sql"
    - "postgresql"
    - "mysql"
    - "postgres"
    - "database"
```

### Adjust Resume Policy (`config/policy.yaml`)

```yaml
ats_formatting:
  max_pages_junior_mid: 1     # 0-5 years → 1 page
  max_pages_senior: 2         # 5+ years → 2 pages
  allowed_sections:
    - "Professional Summary"
    - "Core Competencies & Skills"
    - "Professional Experience"
    - "Key Projects"          # Add or remove sections as needed
    - "Education & Certifications"
```

---

## 12. Real-World Use Case Examples

### Use Case 1: Software Engineer / Developer

**Profile focus:** Technical skills, open source, system design
```json
{
  "target_roles": ["Software Engineer", "Backend Engineer", "Full Stack Developer"],
  "skills": ["Python", "Go", "REST APIs", "Microservices", "SQL", "System Design"],
  "tools": ["PostgreSQL", "Docker", "Kubernetes", "AWS", "GitHub Actions", "Redis"],
  "negative_constraints": [
    "Do NOT claim iOS / Android mobile development experience",
    "Do NOT claim Kubernetes cluster management at scale (only developer usage)"
  ]
}
```

### Use Case 2: Data Analyst / Data Scientist

**Profile focus:** Statistical skills, visualization, ML frameworks
```json
{
  "target_roles": ["Data Analyst", "Data Scientist", "Business Intelligence Analyst"],
  "skills": ["Python", "SQL", "Statistics", "Machine Learning", "Data Visualization", "A/B Testing"],
  "tools": ["Pandas", "Scikit-learn", "Tableau", "Power BI", "BigQuery", "dbt"],
  "negative_constraints": [
    "Do NOT claim deep learning / neural network architecture experience",
    "Do NOT claim production MLOps pipeline deployment"
  ]
}
```

### Use Case 3: UX / Product Designer

**Profile focus:** Design systems, user research, prototyping
```json
{
  "target_roles": ["UX Designer", "Product Designer", "UI/UX Designer"],
  "skills": ["User Research", "Interaction Design", "Wireframing", "Usability Testing", "Design Systems"],
  "tools": ["Figma", "Miro", "Notion", "Maze", "Hotjar", "Zeplin"],
  "negative_constraints": [
    "Do NOT claim motion graphics / After Effects experience",
    "Do NOT claim front-end code development in React"
  ]
}
```

### Use Case 4: Finance / Investment Banking Analyst

**Profile focus:** Financial modeling, valuation, Excel expertise
```json
{
  "target_roles": ["Financial Analyst", "Investment Analyst", "Associate – Investment Banking"],
  "skills": ["Financial Modeling", "DCF Valuation", "Comparable Company Analysis", "Excel", "PowerPoint", "Credit Analysis"],
  "tools": ["Bloomberg Terminal", "Capital IQ", "Excel (Advanced)", "Argus", "MATLAB"],
  "negative_constraints": [
    "Do NOT claim CFA Charterholder status (only Level I passed)",
    "Do NOT claim experience managing more than $50M in assets"
  ]
}
```

### Use Case 5: Human Resources / Talent Acquisition

**Profile focus:** Recruiting, culture, HRBP
```json
{
  "target_roles": ["HR Business Partner", "Talent Acquisition Specialist", "Recruiter", "People Operations Manager"],
  "skills": ["Full-cycle Recruiting", "Behavioral Interviewing", "Employer Branding", "HRIS Management", "Onboarding Design"],
  "tools": ["Workday", "Greenhouse", "LinkedIn Recruiter", "BambooHR", "Lever"],
  "negative_constraints": [
    "Do NOT claim payroll processing expertise (handled by finance team)",
    "Do NOT claim international relocation management experience"
  ]
}
```

### Use Case 6: Digital / Performance Marketing

**Profile focus:** Paid channels, analytics, campaign ROI
```json
{
  "target_roles": ["Performance Marketing Manager", "Digital Marketing Specialist", "Growth Marketer"],
  "skills": ["Google Ads", "Meta Ads", "Campaign Optimization", "A/B Testing", "Attribution Modeling"],
  "tools": ["Google Ads", "Meta Ads Manager", "GA4", "GTM", "Looker Studio", "Klaviyo"],
  "negative_constraints": [
    "Do NOT claim programmatic buying via DV360 or The Trade Desk",
    "Do NOT claim management of budgets exceeding INR 50 Lakhs/month"
  ]
}
```

---

## 13. Profile Templates for Different Professions

### How to Adapt for Your Profession

1. **Open** `data/candidate-profile.json`
2. **Replace** the placeholder values with your actual information
3. **Be precise in `skills` and `tools`** — include only things you can speak to in an interview
4. **Be thorough in `negative_constraints`** — list every technology you'd fail an interview question about
5. **Update** `config/target-profile.yaml` with your desired roles, cities, and salary range
6. **Run** `python -m src.cli run-sample all` to test scoring against the 6 built-in sample jobs

### Target Profile for Different Seniority Levels

**Early Career (0–2 years):**
```yaml
experience_range:
  min_years: 0.0
  max_years: 2.0
  preferred_years: 1.0
compensation:
  min_annual: 400000      # 4 LPA
  target_annual: 700000   # 7 LPA
```

**Mid-Level (2–5 years):**
```yaml
experience_range:
  min_years: 2.0
  max_years: 5.0
  preferred_years: 3.5
compensation:
  min_annual: 800000      # 8 LPA
  target_annual: 1500000  # 15 LPA
```

**Senior / Lead (5+ years):**
```yaml
experience_range:
  min_years: 5.0
  max_years: 10.0
  preferred_years: 6.0
compensation:
  min_annual: 2000000     # 20 LPA
  target_annual: 3500000  # 35 LPA
```

---

## 14. Troubleshooting

### Problem: "Candidate profile not found"
```
FileNotFoundError: Candidate profile not found at data/candidate-profile.json
```
**Fix:** Copy the example and edit it:
```powershell
Copy-Item data\candidate-profile.example.json data\candidate-profile.json
# Then edit data\candidate-profile.json with your real information
```

### Problem: Score is always low
- Check that your `skills` and `tools` lists exactly match industry terminology
- Add synonyms to `config/scoring.yaml` for your field (e.g., `"machine learning"` → `"ml"`, `"ai"`)
- Ensure your `target_roles` list covers the actual job titles you are targeting
- Lower `MIN_MATCH_SCORE` in `.env` temporarily to see what score you do get

### Problem: Resume not being generated
The score likely didn't meet the threshold. Use `--force` to generate anyway:
```powershell
python -m src.cli ingest --file myjob.json --force
```

### Problem: "NEGATIVE FLAGS" appearing
```
NEGATIVE FLAGS  : ['Do NOT claim Kubernetes experience']
```
The job requires a skill you listed in `negative_constraints`. This is working correctly — the system flagged a mismatch. You can still `--force` generate but the validation report will mark this as a concern.

### Problem: Supabase connection not working
1. Confirm `SUPABASE_URL` has no trailing slash
2. Confirm `SUPABASE_KEY` is the full anon key (long JWT token, not just the prefix)
3. Confirm the tables exist — re-run `supabase_schema.sql` in the SQL Editor
4. Check RLS policies — ensure `Allow read/write access` policies were created
5. The system gracefully falls back to **in-memory mode** if connection fails, so your pipeline still works

### Problem: `.env` not loading
Make sure `.env` is in the project root (same folder as `pyproject.toml`), not in a subfolder. The `python-dotenv` library loads it from the project root automatically.

---

## 15. CLI Quick-Reference Card

```powershell
# ── SETUP & STATUS ─────────────────────────────────────────
python -m src.cli check-env                  # Check all credentials & config

# ── TESTING ────────────────────────────────────────────────
python -m src.cli run-sample all             # Test with all 6 built-in sample jobs
python -m src.cli run-sample all --force     # Force generate resumes for all samples

# ── INGEST JOBS ────────────────────────────────────────────
python -m src.cli ingest --text "..."  --title "Role" --company "Org"  # Paste text
python -m src.cli ingest --file path\to\job.json                       # From JSON
python -m src.cli ingest --file path\to\jobs.csv                       # From CSV batch
python -m src.cli ingest --url "https://naukri.com/job-listing/..."    # From URL
python -m src.cli ingest --file job.json --force                       # Force generate

# ── REVIEW & DECIDE ────────────────────────────────────────
python -m src.cli review                                               # See pending queue
python -m src.cli decide <APP_ID> apply  --notes "Apply via portal"   # Ready to apply
python -m src.cli decide <APP_ID> applied  --notes "Submitted"        # Already applied
python -m src.cli decide <APP_ID> save   --notes "Review next week"   # Save for later
python -m src.cli decide <APP_ID> reject --notes "Not a fit"          # Reject

# ── ANALYTICS ──────────────────────────────────────────────
python -m src.cli report                     # Skill gap report & pipeline stats
```

---

> [!NOTE]
> **This is a Human-in-the-Loop system.** The automation handles the time-consuming work — reading JDs, scoring fit, tailoring language, and generating documents. You remain in full control of which applications actually get submitted. The `decide` command is always the final step, and it always stays with you.

---

*Generated for ATS Resume Creator Automation — Supabase Edition.*
*Last updated: October 2026*
