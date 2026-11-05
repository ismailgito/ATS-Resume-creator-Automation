# AGENTS.md — ATS Resume Creator Automation

> Single-file briefing for LLM coding agents. Read this first; open other files only when needed.

## 1. What this is

Python CLI + GitHub Actions automation that turns a job description into an **ATS-compliant, tailored resume package** for one candidate (built for Performance/Digital Marketing, configurable for any profession).

**Pipeline (per job):** `Ingest → Parse → Score → Tailor → Render → Validate → Track → Human decision`

- Works **fully offline/deterministic** with zero API keys. LLM (Gemini / OpenAI / Anthropic) is an optional upgrade with automatic fallback.
- **Human-in-the-loop:** the system NEVER submits applications. The user runs `decide` (apply / applied / save / reject).
- **Default output style:** German *Lebenslauf* (`de`) with English body content; `us` style is switchable.

## 2. Hard rules for agents (do not violate)

1. **Never auto-apply or add auto-submission.** `decide` stays manual.
2. **Never fabricate resume content.** Every employer, skill, tool, date, metric must trace to `data/candidate-profile.json`. Missing requirements go to `gap_list`, never into the resume.
3. **Respect `negative_constraints`** in the profile (e.g. "Do NOT claim Salesforce Marketing Cloud"). Scorer penalizes (−35 per flag, forces `reject`); validator fails the resume.
4. **Keep offline mode working.** Any LLM call must be wrapped with fallback to the deterministic path (`OfflineDeterministicLLMClient`).
5. **Scoring weights must sum to 1.0** (enforced by `tests/test_scoring.py`).
6. **Section headings come only from `src/resume/sections.py`.** Markdown, DOCX and PDF renderers share it, so never hard-code headings in a renderer.
7. **Never commit** `.env`, `data/candidate-profile.json` real PII, or `outputs/*` (only `outputs/.gitkeep`). See `.gitignore`.
8. **Tests must run offline** using `ApplicationTrackerDB(in_memory=True)` and `data/sample-jobs/*.json`. No real network or DB calls in tests.

## 3. Quick start

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt                       # Python >= 3.10
cp data/candidate-profile.example.json data/candidate-profile.json   # edit with real data
cp .env.example .env                                  # optional keys
python -m src.cli check-env                           # verify setup
python -m src.cli run-sample all                      # smoke test on 6 fixtures
pytest                                                # testpaths=tests
```

Console entry point: `ats-resume` → `src.cli:main` (declared in `pyproject.toml`).

## 4. CLI reference (`src/cli.py`)

| Command | Purpose |
|---|---|
| `check-env` | Show credential status, LLM mode, DB backend, resume style |
| `run-sample [name\|all] [--force]` | Run fixtures in `data/sample-jobs/` |
| `ingest --text "..." --title T --company C` | Paste a JD |
| `ingest --file path.{json,txt,md,csv} [--force]` | File or CSV batch |
| `ingest --url URL [--force]` | Fetch public job page (login-walled pages return a placeholder; paste text instead) |
| `review` | List pending review queue |
| `decide <APP_ID> {apply\|applied\|save\|reject} [--notes ".."]` | Record human decision |
| `report` | Analytics: score distribution, status/decision breakdown, top missing skills |

`--force` bypasses the score threshold and generates the package anyway.

## 5. Repository map

```
.
├── AGENTS.md                      # this file
├── README.md                      # 16-section user guide (setup, scoring, scheduling, troubleshooting, de/us style)
├── pyproject.toml / requirements.txt
├── supabase_schema.sql            # tables: jobs, match_reports, applications (+ permissive RLS)
├── .env.example                   # all env vars, documented
├── config/
│   ├── scoring.yaml               # weights, thresholds, synonyms (also scoring.json copy)
│   ├── policy.yaml                # ATS formatting policy, resume_style, allowed sections, page limits
│   └── target-profile.yaml        # target roles/preferences used by scorer
├── data/
│   ├── candidate-profile.json     # SOURCE OF TRUTH about the candidate (gitignore real copy)
│   ├── candidate-profile.example.json
│   └── sample-jobs/*.json         # 6 fixtures (01-perf-mktg-manager, 04-irrelevant-role, 06-conflicting-role, ...)
├── prompts/                       # {{var}} templates: tailor-resume.md, validate-resume.md, score-job.md
├── src/
│   ├── cli.py                     # argparse entry
│   ├── config.py                  # AppSettings (env), PROJECT_ROOT, load_yaml_config, load_candidate_profile
│   ├── pipeline.py                # ResumeAutomationPipeline.process_job() — orchestrator
│   ├── notifications.py           # send_notification(): Telegram / webhook / SMTP
│   ├── ingest/                    # job_sources.py (IngestionManager), normalizer.py (clean HTML, hash, dedupe)
│   ├── parse/job_parser.py        # JobRecord → ParsedJob (title, must_have_skills, tools, exp range, industry)
│   ├── score/scorer.py            # MatchScorer — deterministic 7-factor score
│   ├── resume/                    # tailor.py, generator.py (md + cover note), docx_builder.py, pdf_builder.py, sections.py
│   ├── llm/                       # client.py (Gemini/OpenAI/Anthropic/Offline + get_llm_client), prompts.py
│   ├── validate/                  # validator.py (quality gate), fact_checker.py
│   ├── tracker/                   # db.py (ApplicationTrackerDB), analytics.py
│   └── models/                    # job.py, profile.py, resume.py, score.py (dataclasses)
├── tests/                         # test_ingest, test_scoring, test_resume_gen, test_validator, test_tracker, test_notifications
├── outputs/                       # generated packages (gitignored)
├── jobs/                          # CSVs for batch runs (e.g. jobs/daily-jobs.csv)
├── assets/                        # README SVG animations (workflow-animation.svg, scoring-animation.svg)
└── .github/workflows/
    ├── daily-automation.yml       # cron CSV → pipeline → artifact → Telegram
    └── scheduled-discovery.yml    # cron `run-sample all` + report
```

## 6. Pipeline detail

`ResumeAutomationPipeline.process_job(job_record, candidate=None, force_generate=False)` in `src/pipeline.py`:

1. **Ingest** (`IngestionManager`): from text / JSON / TXT / MD / CSV / URL → `JobRecord`. Text is HTML-stripped and whitespace-normalized; `content_hash` used for dedupe.
   - CSV columns: `title, company, location, url, description` (aliases: `job_title`, `company_name`, `job_url`, `job_description`).
2. **Parse** (`JobParser`) → `ParsedJob`.
3. **Score** (`MatchScorer`): see §7. Saved to tracker.
4. **Gate:** generate only if score ≥ `MIN_MATCH_SCORE` (default 75) or `--force`; rejected jobs (negative flags or <50) produce no package unless forced.
5. **Tailor** (`ResumeTailor`): deterministic baseline built from profile facts, then optionally enriched by LLM using `prompts/tailor-resume.md`. LLM output is merged; any failure falls back to baseline. Produces `TailoredResume` + cover note + `gap_list` + `change_log`.
6. **Render:** Markdown, DOCX (`python-docx`), PDF (`fpdf2`), cover note — style `de`/`us`.
7. **Validate** (`ResumeValidator` + `FactChecker`): see §8. Writes `validation-report.json`.
8. **Track:** `ReviewPackage` saved via `ApplicationTrackerDB`. Status `review_ready` (validation passed) or `needs_attention`.
9. **Daily limit:** `DAILY_LIMIT` (default 10) counted per UTC day via `db.increment_completion()`; notification fires on limit and on mid-run exceptions.

Each package folder in `outputs/` contains: resume `.md`/`.docx`/`.pdf`, cover note, `match-report.json`, `validation-report.json`, `change-log`.

## 7. Scoring (`src/score/scorer.py`, `config/scoring.yaml`)

Deterministic, reproducible, no LLM calls.

| Factor | Weight |
|---|---|
| title_role_fit | 0.20 |
| required_skills | 0.25 |
| platform_tools | 0.15 |
| experience_fit | 0.15 |
| industry_fit | 0.10 |
| location_fit | 0.05 |
| achievement_relevance | 0.10 |

- Synonym groups in `scoring.yaml` (e.g. `google_ads` ⇄ sem/ppc/pmax; `meta_ads` ⇄ paid social; `ga4`, `gtm`, `cro`, `marketing_automation` ⇄ n8n/zapier) drive matching.
- Thresholds: `auto_generate_resume 80`, `medium_fit_review 65`, `research_queue/rejection_cutoff 50`.
- Recommendations emitted by code: `apply_review` (≥80), `save` (50–79), `reject` (<50 or any negative-constraint flag). (README mentions `medium_fit_review`/`research_queue` labels; code emits `save` for both.)
- Two knobs exist: `MIN_MATCH_SCORE` (env, generation gate, default 75) and `thresholds` in YAML (recommendation labels). Don't conflate them.
- Both `scoring.yaml` and `scoring.json` exist; the loader path is `SCORING_CONFIG_PATH` (default `config/scoring.yaml`). Keep them in sync if you edit one.

## 8. Validation (`src/validate/`)

Hard errors (fail the package):
- Employer in resume not in profile `employment`.
- Negative-constraint tool/keyword appears in summary/skills/bullets.
- Unresolved `{{placeholder}}` in output.

Warnings/fixes: skill not in verified skills/tools, missing/short summary (<50 chars), <3 skills, empty experience, missing education, invalid email/phone, bullets <15 or >400 chars, keyword stuffing, ATS structure issues.

`prompts/validate-resume.md` and `prompts/score-job.md` exist as LLM prompt templates, but the current validator and scorer are rule-based.

## 9. Candidate profile (`data/candidate-profile.json`)

Key fields: `candidate_id`, `full_name`, `headline`, `contact{email,phone,location,linkedin,portfolio}`, `target_roles`, `skills`, `tools`, `experience_years`, `key_domains`, `employment[]`, `education[]`, `certifications[]`, `achievements`, `negative_constraints[]`; optional German fields `date_of_birth`, `address`, `photo` (rendered only if present).
`CandidateProfile.to_fact_registry()` is the object handed to LLMs and the fact checker — treat it as the only allowed source of claims.

## 10. Resume style

- `RESUME_STYLE=de|us` env wins; if blank, `config/policy.yaml → ats_formatting.resume_style`; default `de`.
- `de`: `Lebenslauf` title, sections *Persönliche Daten, Kurzprofil, Kenntnisse & Fähigkeiten, Berufserfahrung, Erfolge & Wirkung, Ausbildung & Zertifikate*, `MM/YYYY` dates, `Seite 1/2` footer, cover note wrapped as *Anschreiben* (German salutation/closing, English body).
- `us`: classic English headings and `Mon YYYY` dates.
- Tests assert `de` headings by default; update tests if you change section names.

## 11. Tracker / database (`src/tracker/db.py`)

Backend auto-selected: **Supabase REST** (`SUPABASE_URL` + `SUPABASE_KEY`) → **direct Postgres** (`DATABASE_URL`) → **in-memory SQLite** fallback (also used when credentials start with `your_`).
Tables (`supabase_schema.sql`): `jobs`, `match_reports`, `applications` (`status`, `user_decision`, `output_directory`, `submitted_at`, `outcome`).
Decision → status map: `apply→approved_for_manual_apply`, `applied→applied_manually` (sets `submitted_at`), `save→saved_in_queue`, `reject→rejected_by_user`. Duplicate jobs are ignored (`save_job` returns False).

## 12. Environment variables (`.env.example`)

| Group | Vars |
|---|---|
| LLM | `LLM_PROVIDER` (`offline`\|`gemini`\|`openai`\|`anthropic`), `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `*_MODEL`, `LLM_API_BASE_URL` |
| DB | `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL` |
| Notify | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `NOTIFY_WEBHOOK_URL`, `SMTP_*`, `NOTIFICATION_EMAIL_TO`, `DAILY_LIMIT` |
| Paths | `CANDIDATE_PROFILE_PATH`, `SCORING_CONFIG_PATH`, `POLICY_CONFIG_PATH`, `OUTPUT_DIR` |
| Behavior | `MIN_MATCH_SCORE`, `RESUME_STYLE` |
| Job sources | `NAUKRI_API_TOKEN`, `NAUKRI_CLIENT_ID`, `APIFY_API_TOKEN` (placeholders, not fully wired) |

`.env` lives in project root (loaded via `python-dotenv`). Auto-detects a valid Gemini/OpenAI key if `LLM_PROVIDER` is unset.

## 13. GitHub Actions

- **`daily-automation.yml`** — cron `0 8 * * *` (08:00 UTC = 13:30 IST) + manual dispatch (`csv_url`, `min_score`, `daily_limit`, `force_generate`). Downloads CSV from secret `JOBS_CSV_URL` → `python -m src.cli ingest --file jobs/daily-jobs.csv` (`LLM_PROVIDER=gemini`, `RESUME_STYLE=de`) → `report` → uploads `outputs/` as artifact (30 days) → Telegram summary.
- **`scheduled-discovery.yml`** — same cron, runs `run-sample all` + `report`, artifact 14 days.
- Secrets: `JOBS_CSV_URL`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## 14. Common tasks → where to edit

| Task | Edit |
|---|---|
| Change scoring weights / synonyms / thresholds | `config/scoring.yaml` (+ `.json`) |
| Add a new scoring factor | `src/score/scorer.py` + weights in YAML + `ScoreBreakdown` in `src/models/score.py` + `test_scoring.py` |
| Add a job source | New classmethod in `src/ingest/job_sources.py`, wire flag in `src/cli.py` |
| Change resume sections/headings | `src/resume/sections.py` only; update tests |
| Add a new LLM provider | New `BaseLLMClient` subclass + branch in `get_llm_client()` (`src/llm/client.py`) + env in `config.py` |
| Change ATS rules / page limits | `config/policy.yaml`, `src/validate/validator.py` |
| Add a notification channel | `src/notifications.py` |
| Change DB schema | `supabase_schema.sql` + `src/tracker/db.py` (all 3 backends: REST, Postgres, in-memory) |
| Change tailoring prompt | `prompts/tailor-resume.md` (keep `{{parsed_job_json}}`, `{{candidate_profile_json}}`, `{{match_report_json}}`) |

## 15. Conventions

- Python ≥3.10, `from __future__ import annotations`, type hints, dataclass models with `to_dict()/from_dict()`.
- Paths via `PROJECT_ROOT` (`src/config.py`), never relative to cwd.
- Optional deps (`yaml`, `dotenv`, `psycopg2`) are imported defensively; keep that pattern.
- Prompts use `{{var}}` replacement (`render_prompt`), not Jinja.
- Dev on Windows/PowerShell is common; keep commands cross-platform.

## 16. Gotchas

- Score looks low → check `skills`/`tools` terminology and `target_roles`; add synonyms; try lowering `MIN_MATCH_SCORE`.
- No resume generated → score below gate; use `--force`.
- "NEGATIVE FLAGS" is working as intended; `--force` still yields a package, flagged by validation.
- Supabase unreachable or misconfigured → silently falls back to in-memory (data lost on exit).
- `ingest --url` often can't read login-gated boards (Naukri/LinkedIn); paste text instead.
- LLM output must be JSON; `_extract_json_from_text` strips markdown fences and regex-extracts `{...}`.

## 17. Definition of done for changes

1. `pytest` passes offline.
2. `python -m src.cli run-sample all` runs clean in offline mode.
3. No new hard-coded secrets, no PII committed, `outputs/` untouched in git.
4. README/AGENTS.md updated if CLI, env vars, config keys, or pipeline stages changed.