# 🛠️ Comprehensive Customization & Multi-Profile Guide: ATS Automation Resume Generator

This document provides a complete architectural analysis and step-by-step blueprint for adapting the **ATS Automation Resume Generator** from its default Performance Marketing configuration into a universal, multi-domain, and multi-experience resume automation platform.

Whether you are configuring the pipeline for a **Software Engineer**, a **Graphic / UI-UX Designer**, or a **Marketer** — across any seniority level (**Intern**, **Junior**, **Mid/Senior**, or **Lead/Manager**) — this guide details how to customize candidate facts, match scoring rules, domain synonyms, and output formatting policies.

---

## 📋 Table of Contents

1. [Architectural Overview & Core Analysis](#1-architectural-overview--core-analysis)
2. [Current Hardcoded Bottlenecks vs. Modular Target State](#2-current-hardcoded-bottlenecks-vs-modular-target-state)
3. [Multi-Domain Customization Blueprint](#3-multi-domain-customization-blueprint)
   - [Profile A: Software Engineer (Backend / Frontend / DevOps / AI)](#profile-a-software-engineer-backend--frontend--devops--ai)
   - [Profile B: Graphic Designer & UI/UX Specialist](#profile-b-graphic-designer--uiux-specialist)
   - [Profile C: Performance & Growth Marketer](#profile-c-performance--growth-marketer)
4. [Any-Level Experience Scaling Matrix (Intern to Director)](#4-any-level-experience-scaling-matrix-intern-to-director)
5. [Directory Architecture for Multi-Profile Routing](#5-directory-architecture-for-multi-profile-routing)
6. [Code Adaptations for Dynamic CLI Parameterization](#6-code-adaptations-for-dynamic-cli-parameterization)
7. [Step-by-Step Quickstart Walkthrough](#7-step-by-step-quickstart-walkthrough)
8. [Summary & Verification Checklist](#8-summary--verification-checklist)

---

## 1. 🏗️ Architectural Overview & Core Analysis

The **ATS Automation Resume Generator** is designed around a 6-stage deterministic and LLM-assisted pipeline:

```text
 ┌──────────────────────┐      ┌─────────────────────────┐      ┌───────────────────────────┐
 │ 1. INGESTION         │ ───► │ 2. PARSE & NORMALIZE    │ ───► │ 3. DETERMINISTIC SCORING  │
 │ URL / Text / Files   │      │ HTML Strip & Synonyms   │      │ 7-Factor Transparent Fit  │
 └──────────────────────┘      └─────────────────────────┘      └─────────────┬─────────────┘
                                                                              │
                               ┌──────────────────────────────────────────────┘
                               ▼
 ┌──────────────────────┐      ┌─────────────────────────┐      ┌───────────────────────────┐
 │ 4. RESUME TAILORING  │ ───► │ 5. ATS QUALITY GATE     │ ───► │ 6. HUMAN REVIEW QUEUE     │
 │ Markdown, DOCX, PDF  │      │ Strict Fact Audit       │      │ Review & Apply Package    │
 └──────────────────────┘      └─────────────────────────┘      └───────────────────────────┘
```

### Existing Codebase Inspection

| Core Module | File Location | Responsibility | Current State |
|---|---|---|---|
| **Configuration Loader** | [config.py](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/src/config.py) | Loads `.env`, profile JSON/YAML, scoring, and policy files | Hardcoded fallback paths to marketing profile |
| **Candidate Fact Registry** | [candidate-profile.json](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/data/candidate-profile.json) | Stores single source of truth for candidate facts | Configured for Performance Marketing Specialist (Aarav Sharma) |
| **Target Role Config** | [target-profile.yaml](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/config/target-profile.yaml) | Defines acceptable job titles, experience bounds, preferred locations, and tools | Contains marketing channels (Google Ads, Meta Ads, GA4) |
| **Scoring Engine** | [scoring.yaml](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/config/scoring.yaml) & [scorer.py](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/src/score/scorer.py) | Computes 7-Factor fit score (Title 20%, Skills 25%, Tools 15%, Experience 15%, Industry 10%, Location 5%, Achievement 10%) | Synonym dictionary is marketing-focused (`meta_ads`, `ga4`, `cro`) |
| **Policy Enforcement** | [policy.yaml](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/config/policy.yaml) | Controls ATS safety, maximum pages by seniority, permitted fonts/sections | Sets page limits based on junior/mid vs. senior bounds |
| **Resume Tailor Engine** | [tailor.py](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/src/resume/tailor.py) | Selects relevant achievements and orders bullets based on job requirements | Domain-agnostic algorithm |
| **Document Generators** | [generator.py](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/src/resume/generator.py), [docx_builder.py](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/src/resume/docx_builder.py), [pdf_builder.py](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/src/resume/pdf_builder.py) | Renders Markdown, DOCX, and PDF artifacts | Fully domain-agnostic Jinja2 templates |

---

## 2. ⚡ Current Hardcoded Bottlenecks vs. Modular Target State

To enable **Software Engineers**, **Graphic Designers**, and **Marketers** across **Any Experience Level**, three decoupling steps are required:

```
  [CURRENT STATE]                              [TARGET MODULAR STATE]
  Single profile files                         Profile-driven CLI routing

  data/candidate-profile.json      ──┐         data/candidates/
  config/target-profile.yaml       ──┼──►        ├── software_engineer.json
  config/scoring.yaml              ──┘         ├── graphic_designer.json
                                               └── marketer_intern.json

                                               config/profiles/
                                                 ├── software_engineer.yaml
                                                 ├── graphic_designer.yaml
                                                 └── marketer.yaml

                                               config/scoring/
                                                 ├── software_engineer_synonyms.yaml
                                                 ├── graphic_designer_synonyms.yaml
                                                 └── marketer_synonyms.yaml
```

---

## 3. 🎯 Multi-Domain Customization Blueprint

Below are the complete configuration specifications for the three example roles.

---

### Profile A: Software Engineer (Backend / Frontend / DevOps / AI)

#### 1. Candidate Fact Registry (`data/candidates/software_engineer.json`)

```json
{
  "candidate_id": "cand-swe-001",
  "full_name": "Rohan Verma",
  "headline": "Senior Full Stack Engineer | Python, React, AWS, Docker | Microservices & Distributed Systems",
  "contact": {
    "email": "rohan.verma.dev@example.com",
    "phone": "+91 98123 45678",
    "location": "Bengaluru, Karnataka, India",
    "linkedin": "https://linkedin.com/in/rohanverma-dev",
    "portfolio": "https://github.com/rohanverma-dev"
  },
  "target_roles": [
    "Senior Software Engineer",
    "Full Stack Developer",
    "Backend Engineer",
    "Python Developer",
    "Lead Engineer"
  ],
  "experience_years": 4.5,
  "location": "Bengaluru, Karnataka, India",
  "work_authorization": "Authorized to work in India",
  "notice_period_days": 30,
  "current_ctc_lpa": 18.0,
  "expected_ctc_lpa": 26.0,
  "summary_facts": [
    "4.5 years of experience building high-throughput microservices handling 10M+ daily API requests",
    "Proficient in Python (FastAPI/Django), TypeScript (React/Next.js), PostgreSQL, Redis, and Kafka",
    "Architected AWS cloud infrastructure using Terraform, Docker, and Kubernetes CI/CD pipelines",
    "Reduced API p99 latency by 42% through query optimization and distributed caching strategies"
  ],
  "skills": [
    "Python",
    "TypeScript",
    "JavaScript",
    "FastAPI",
    "Django",
    "React.js",
    "Node.js",
    "REST API Design",
    "Microservices",
    "PostgreSQL",
    "Redis",
    "Kafka",
    "System Design",
    "Unit Testing (PyTest/Jest)"
  ],
  "tools": [
    "AWS (EC2, S3, RDS, Lambda)",
    "Docker",
    "Kubernetes",
    "Terraform",
    "Git",
    "GitHub Actions",
    "Postman",
    "Grafana",
    "Datadog"
  ],
  "achievements": [
    {
      "id": "swe-ach-01",
      "statement": "Designed and deployed a event-driven payment processing microservice handling 500+ transactions per second with 99.99% uptime.",
      "metric": "500 TPS & 99.99% Uptime",
      "time_period": "2024",
      "evidence": "Datadog production uptime logs"
    },
    {
      "id": "swe-ach-02",
      "statement": "Reduced cloud infrastructure spending by 30% by transitioning monolithic EC2 instances to autoscaling Kubernetes pods on AWS EKS.",
      "metric": "30% AWS Cost Reduction",
      "time_period": "Q3 2024",
      "evidence": "AWS Cost Explorer invoice audit"
    }
  ],
  "employment": [
    {
      "company": "TechScalers Pvt Ltd",
      "title": "Senior Software Engineer",
      "location": "Bengaluru, India",
      "start_date": "2023-01",
      "end_date": "Present",
      "is_current": true,
      "responsibilities": [
        "Led backend architecture for high-concurrency SaaS platform using FastAPI and PostgreSQL",
        "Mentored 4 junior software engineers on code reviews, design patterns, and CI/CD best practices"
      ]
    }
  ],
  "education": [
    {
      "institution": "National Institute of Technology (NIT)",
      "degree": "B.Tech in Computer Science & Engineering",
      "start_year": 2017,
      "end_year": 2021
    }
  ],
  "certifications": [
    {
      "name": "AWS Certified Solutions Architect – Associate",
      "issuer": "Amazon Web Services",
      "date": "2023"
    }
  ],
  "negative_constraints": [
    "PHP",
    "Ruby on Rails",
    "Legacy COBOL"
  ]
}
```

#### 2. Target Profile & Scoring Rules (`config/profiles/software_engineer.yaml`)

```yaml
target_roles:
  - "Senior Software Engineer"
  - "Software Development Engineer II (SDE-2)"
  - "Backend Engineer"
  - "Full Stack Developer"
  - "Lead Backend Engineer"

experience_range:
  min_years: 3.0
  max_years: 6.0
  preferred_years: 4.5

key_domains:
  - "B2B SaaS"
  - "Fintech"
  - "High-Scale Distributed Systems"
  - "Cloud Infrastructure"

core_channels:
  - "Python / FastAPI / Django"
  - "TypeScript / React"
  - "PostgreSQL / Redis / Kafka"
  - "Docker / Kubernetes / AWS"

scoring_synonyms:
  python:
    - "python"
    - "python3"
    - "fastapi"
    - "django"
    - "flask"
  react:
    - "react"
    - "reactjs"
    - "react.js"
    - "nextjs"
    - "next.js"
  aws:
    - "aws"
    - "amazon web services"
    - "ec2"
    - "s3"
    - "eks"
    - "cloud"
  docker:
    - "docker"
    - "containerization"
    - "containers"
    - "kubernetes"
    - "k8s"
  sql:
    - "sql"
    - "postgresql"
    - "postgres"
    - "mysql"
    - "relational database"
```

---

### Profile B: Graphic Designer & UI/UX Specialist

#### 1. Candidate Fact Registry (`data/candidates/graphic_designer.json`)

```json
{
  "candidate_id": "cand-des-001",
  "full_name": "Priya Nair",
  "headline": "Senior UI/UX & Visual Designer | Figma, Adobe CC, Design Systems | Web & Mobile Product Design",
  "contact": {
    "email": "priya.nair.design@example.com",
    "phone": "+91 97654 32109",
    "location": "Mumbai, Maharashtra, India",
    "linkedin": "https://linkedin.com/in/priyanair-design",
    "portfolio": "https://behance.net/priyanair-design"
  },
  "target_roles": [
    "Senior UI/UX Designer",
    "Lead Visual Designer",
    "Product Designer",
    "Brand & Graphic Designer"
  ],
  "experience_years": 3.5,
  "location": "Mumbai, Maharashtra, India",
  "work_authorization": "Authorized to work in India",
  "notice_period_days": 15,
  "summary_facts": [
    "3.5 years designing responsive mobile apps, SaaS web portals, and enterprise design systems",
    "Created end-to-end design system in Figma used by 20+ engineers, improving UI component reusability by 65%",
    "Proficient in Figma, Adobe Illustrator, Photoshop, After Effects, Framer, and user research methodologies",
    "Increased app checkout conversion rate by 24% following comprehensive UX audit and wireframe overhaul"
  ],
  "skills": [
    "UI Design",
    "UX Design",
    "Wireframing",
    "Interactive Prototyping",
    "User Research & Testing",
    "Design Systems",
    "Information Architecture",
    "Typography & Layout",
    "Brand Identity Design",
    "Motion Graphics"
  ],
  "tools": [
    "Figma",
    "Adobe Illustrator",
    "Adobe Photoshop",
    "Adobe After Effects",
    "Framer",
    "Webflow",
    "Miro",
    "Zeplin",
    "LottieFiles"
  ],
  "achievements": [
    {
      "id": "des-ach-01",
      "statement": "Redesigned mobile app onboarding workflow in Figma, driving a 24% increase in user completion rate.",
      "metric": "24% UX Conversion Lift",
      "time_period": "2024",
      "evidence": "Mixpanel funnel analytics report"
    },
    {
      "id": "des-ach-02",
      "statement": "Built multi-brand UI design system with 150+ accessible components, cutting design-to-dev handoff time by 40%.",
      "metric": "40% Faster Handoff Time",
      "time_period": "Q2 2024",
      "evidence": "Figma design system library metrics"
    }
  ],
  "employment": [
    {
      "company": "Studio Creative UX",
      "title": "Senior UI/UX Designer",
      "location": "Mumbai, India",
      "start_date": "2022-06",
      "end_date": "Present",
      "is_current": true,
      "responsibilities": [
        "Lead UI/UX design for B2C mobile applications and web client projects",
        "Conduct usability testing sessions with target users to iterate on prototypes"
      ]
    }
  ],
  "education": [
    {
      "institution": "National Institute of Design (NID)",
      "degree": "B.Des in Communication Design",
      "start_year": 2017,
      "end_year": 2021
    }
  ],
  "certifications": [
    {
      "name": "Google UX Design Professional Certificate",
      "issuer": "Coursera / Google",
      "date": "2022"
    }
  ],
  "negative_constraints": [
    "3D Maya Animation",
    "C++ Programming"
  ]
}
```

#### 2. Target Profile & Scoring Rules (`config/profiles/graphic_designer.yaml`)

```yaml
target_roles:
  - "Senior UI/UX Designer"
  - "Product Designer"
  - "Visual Designer"
  - "Lead Graphic Designer"
  - "Brand Designer"

experience_range:
  min_years: 2.0
  max_years: 5.0
  preferred_years: 3.5

core_channels:
  - "Figma / Design Systems"
  - "User Research & Usability Testing"
  - "Wireframing & Prototyping"
  - "Adobe Creative Cloud (Illustrator/Photoshop/After Effects)"

scoring_synonyms:
  figma:
    - "figma"
    - "figma component"
    - "auto-layout"
    - "design system"
  ui_ux:
    - "ui/ux"
    - "ui design"
    - "ux design"
    - "user interface"
    - "user experience"
    - "product design"
  prototyping:
    - "prototyping"
    - "wireframing"
    - "interactive prototypes"
    - "framer"
    - "invision"
  adobe_cc:
    - "adobe illustrator"
    - "illustrator"
    - "photoshop"
    - "after effects"
    - "creative cloud"
```

---

### Profile C: Performance & Growth Marketer

#### 1. Candidate Fact Registry (`data/candidates/marketer.json`)

```json
{
  "candidate_id": "cand-mktg-001",
  "full_name": "Aarav Sharma",
  "headline": "Performance & Growth Marketing Specialist | Paid Search & Social | CAC & ROAS Optimization",
  "contact": {
    "email": "aarav.sharma.mktg@example.com",
    "phone": "+91 98765 43210",
    "location": "Bengaluru, Karnataka, India",
    "linkedin": "https://linkedin.com/in/aarav-sharma-marketing",
    "portfolio": "https://aaravsharma.marketing"
  },
  "target_roles": [
    "Performance Marketing Manager",
    "Digital Marketing Lead",
    "Growth Marketing Specialist",
    "Paid Media Manager"
  ],
  "experience_years": 2.5,
  "location": "Bengaluru, Karnataka, India",
  "work_authorization": "Authorized to work in India",
  "notice_period_days": 30,
  "summary_facts": [
    "2.5 years managing performance ad spend exceeding INR 2.5 Cr across Google & Meta Ads",
    "Scaled revenue by 140% while maintaining target blended ROAS of 3.8x for B2C & D2C brands",
    "Expert in GA4 event tracking, GTM server-side containers, Looker Studio, and CRO experimentation"
  ],
  "skills": [
    "Performance Marketing",
    "Paid Search (SEM)",
    "Paid Social (Meta Ads)",
    "PPC Strategy",
    "Conversion Rate Optimization (CRO)",
    "Funnel Analysis",
    "Attribution Modeling"
  ],
  "tools": [
    "Google Ads (Search, Display, PMax)",
    "Meta Ads Manager",
    "LinkedIn Campaign Manager",
    "Google Analytics 4 (GA4)",
    "Google Tag Manager (GTM)",
    "Looker Studio"
  ],
  "achievements": [
    {
      "id": "ach-01",
      "statement": "Scaled ad budgets from 8L/mo to 25L/mo while increasing ROAS from 2.6x to 3.8x.",
      "metric": "140% Spend Scale with 3.8x ROAS",
      "time_period": "2024",
      "evidence": "Google & Meta Ads audited reports"
    }
  ],
  "employment": [
    {
      "company": "Klarity Digital Media",
      "title": "Performance Marketing Lead",
      "location": "Bengaluru, India",
      "start_date": "2023-03",
      "end_date": "Present",
      "is_current": true,
      "responsibilities": [
        "Manage end-to-end media planning, ad account execution, and weekly creative sprints"
      ]
    }
  ],
  "education": [
    {
      "institution": "Delhi University",
      "degree": "B.Com (Hons)",
      "start_year": 2018,
      "end_year": 2021
    }
  ],
  "certifications": [
    {
      "name": "Google Ads Search Certification",
      "issuer": "Google",
      "date": "2024"
    }
  ],
  "negative_constraints": [
    "Salesforce Marketing Cloud",
    "Cold Calling"
  ]
}
```

---

## 4. 📊 Any-Level Experience Scaling Matrix (Intern to Director)

The pipeline dynamically adapts its scoring thresholds, resume page limits, section weighting, and fact enforcement based on candidate experience levels:

| Experience Level | Experience Bounds | Max Resume Pages | Match Threshold | Key Focus & Section Ordering | Policy Rules ([policy.yaml](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/config/policy.yaml)) |
|---|---|---|---|---|---|
| **Intern / Trainee** | `0.0` – `1.0` Yrs | **1 Page** strictly | `60.0%` (Permissive) | 1. Professional Summary<br>2. Education & Certifications<br>3. Technical Skills & Tools<br>4. Academic/Personal Projects<br>5. Internships | • `max_pages_junior_mid: 1`<br>• `allow_inferred_metrics: true`<br>• Low penalty for missing years |
| **Junior / Associate** | `1.0` – `3.0` Yrs | **1 Page** strictly | `70.0%` (Balanced) | 1. Professional Summary<br>2. Core Skills & Tools<br>3. Professional Experience<br>4. Key Projects & Impact<br>5. Education | • `max_pages_junior_mid: 1`<br>• Strict match on must-have tools<br>• Execution metrics prioritized |
| **Mid / Senior** | `3.0` – `7.0` Yrs | **1 to 2 Pages** | `75.0%` (Strict) | 1. Professional Summary<br>2. Core Competencies<br>3. Professional Experience & Metrics<br>4. Key Achievements<br>5. Education & Certifications | • `max_pages_senior: 2`<br>• `strict_candidate_facts_only: true`<br>• Architectural & ROI impact required |
| **Lead / Manager / Director** | `8.0+` Yrs | **2 Pages** max | `80.0%` (High Bar) | 1. Executive Summary<br>2. Leadership & Strategy<br>3. Career History & Team Scale<br>4. Strategic Achievements & P&L<br>5. Education | • `max_pages_senior: 2`<br>• Enforces team size and budget ownership metrics |

### Custom Policy Configuration (`config/policy.yaml`)

```yaml
system:
  mode: "human_in_the_loop"
  allow_automated_submission: false
  require_user_review_before_apply: true

factuality:
  strict_candidate_facts_only: true
  allow_inferred_metrics: false
  require_achievement_evidence: true
  reject_on_negative_constraints: true

ats_formatting:
  max_pages_junior_mid: 1
  max_pages_senior: 2
  allowed_sections:
    - "Professional Summary"
    - "Core Competencies & Skills"
    - "Professional Experience"
    - "Key Projects & Achievements"
    - "Education & Certifications"
  prohibited_elements:
    - "tables_with_nested_cells"
    - "multi_column_floaters"
    - "text_boxes"
    - "graphics_charts"
  standard_fonts:
    - "Helvetica"
    - "Arial"
    - "Calibri"
```

---

## 5. 📁 Directory Architecture for Multi-Profile Routing

To support multiple profiles cleanly without overwriting files, structure your codebase as follows:

```text
ATS-Automation-Resume-Generator/
├── config/
│   ├── policy.yaml                      # Global ATS formatting & safety policy
│   ├── profiles/
│   │   ├── software_engineer.yaml       # Target roles & criteria for SWE
│   │   ├── graphic_designer.yaml        # Target roles & criteria for Designer
│   │   └── marketer.yaml                # Target roles & criteria for Marketer
│   └── scoring/
│       ├── software_engineer_scoring.yaml # SWE weights & synonyms
│       ├── graphic_designer_scoring.yaml  # Designer weights & synonyms
│       └── marketer_scoring.yaml          # Marketer weights & synonyms
├── data/
│   ├── candidates/
│   │   ├── software_engineer_senior.json  # Rohan Verma profile
│   │   ├── graphic_designer_mid.json     # Priya Nair profile
│   │   └── marketer_intern.json          # Intern candidate profile
│   └── sample-jobs/                      # Test job postings for each domain
├── outputs/                             # Generated PDF, DOCX & MD review packages
└── src/                                 # Python source code
```

---

## 6. 💻 Code Adaptations for Dynamic CLI Parameterization

Modify [src/config.py](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/src/config.py) and [src/cli.py](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/src/cli.py) to accept custom profile paths dynamically.

### 1. Update [src/config.py](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/src/config.py)

```python
@dataclass
class AppSettings:
    # Existing fields...
    candidate_profile_path: Path = PROJECT_ROOT / os.getenv("CANDIDATE_PROFILE_PATH", "data/candidate-profile.json")
    scoring_config_path: Path = PROJECT_ROOT / os.getenv("SCORING_CONFIG_PATH", "config/scoring.yaml")
    policy_config_path: Path = PROJECT_ROOT / os.getenv("POLICY_CONFIG_PATH", "config/policy.yaml")
    target_profile_path: Path = PROJECT_ROOT / os.getenv("TARGET_PROFILE_PATH", "config/target-profile.yaml")

    def override_paths(
        self,
        candidate_path: Optional[str] = None,
        target_path: Optional[str] = None,
        scoring_path: Optional[str] = None
    ) -> None:
        """Dynamically override configuration paths at runtime."""
        if candidate_path:
            self.candidate_profile_path = Path(candidate_path)
        if target_path:
            self.target_profile_path = Path(target_path)
        if scoring_path:
            self.scoring_config_path = Path(scoring_path)
```

### 2. Update [src/cli.py](file:///C:/Users/Lenovo/Documents/ATS-Automation-Resume-Generator/src/cli.py)

Add optional CLI flags (`--candidate`, `--target`, `--scoring`) to the parser:

```python
parser.add_argument("--candidate", type=str, help="Path to candidate profile JSON")
parser.add_argument("--target", type=str, help="Path to target profile YAML")
parser.add_argument("--scoring", type=str, help="Path to scoring config YAML")
```

When initializing `ResumeAutomationPipeline(settings)` in `cmd_ingest` or `cmd_run_sample`, pass the customized `AppSettings` instance.

---

## 7. 🚀 Step-by-Step Quickstart Walkthrough

Follow these steps to run the customized pipeline for any role and experience level:

### Step 1: Create Candidate Profile JSON
Save your candidate facts to `data/candidates/<role>_<level>.json` using the schema from Section 3.

### Step 2: Create Target Profile & Scoring Rules
Save target role requirements to `config/profiles/<role>.yaml` and domain synonyms to `config/scoring/<role>_scoring.yaml`.

### Step 3: Run Diagnostics Command
Verify paths and credential availability:

```bash
python -m src.cli check-env
```

### Step 4: Run Automation Pipeline

#### Example A: Software Engineer (Senior)
```bash
python -m src.cli ingest --file data/sample-jobs/swe-backend-job.json \
  --candidate data/candidates/software_engineer_senior.json \
  --target config/profiles/software_engineer.yaml \
  --scoring config/scoring/software_engineer_scoring.yaml
```

#### Example B: Graphic / UI-UX Designer (Junior / Mid)
```bash
python -m src.cli ingest --file data/sample-jobs/uiux-designer-job.json \
  --candidate data/candidates/graphic_designer_mid.json \
  --target config/profiles/graphic_designer.yaml \
  --scoring config/scoring/graphic_designer_scoring.yaml
```

#### Example C: Marketer (Intern)
```bash
python -m src.cli ingest --file data/sample-jobs/marketing-intern-job.json \
  --candidate data/candidates/marketer_intern.json \
  --target config/profiles/marketer.yaml \
  --scoring config/scoring/marketer_scoring.yaml
```

---

## 8. ✅ Summary & Verification Checklist

To verify that your customization is working cleanly:

- [x] **Match Score Verification**: Check that target domain keywords match properly without false penalties.
- [x] **Negative Constraint Shield**: Ensure forbidden tools (e.g. `PHP` for SWE, `Salesforce` for Marketer) trigger immediate rejection flags.
- [x] **Factuality Audit**: Ensure 100% of skills, employment dates, and metrics in generated `.pdf`, `.docx`, and `.md` resumes strictly exist in the candidate JSON.
- [x] **Page Count Compliance**: Verify that Intern and Junior resumes render on **1 page**, while Senior resumes remain within **2 pages**.
- [x] **Human Review Queue**: Confirm that review packages are generated in `outputs/<Company-Name>/` with all 4 artifacts (`<Company-Name>_Resume.md`, `<Company-Name>_Resume.docx`, `<Company-Name>_Resume.pdf`, `<Company-Name>_Cover-Note.md`).

---
*Document Generated for ATS Automation Resume Generator — Multi-Profile & Multi-Experience Module.*
