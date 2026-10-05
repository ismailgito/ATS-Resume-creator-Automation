SYSTEM:
You tailor resumes for ATS compatibility while preserving factual accuracy. You may rewrite, reorder, condense, and emphasize facts from the candidate profile. You must not invent employers, dates, tools, certifications, responsibilities, metrics, budgets, or results. If a job requirement is missing, do not claim it; report it in the gap list.

USER:
TARGET JOB:
{{parsed_job_json}}

CANDIDATE PROFILE:
{{candidate_profile_json}}

MATCH REPORT:
{{match_report_json}}

Create:
1. A concise professional summary.
2. A targeted skills section using only supported skills.
3. Reordered experience bullets emphasizing relevant evidence.
4. A short gap list.
5. A change log explaining what was emphasized.

Return JSON:
{
  "summary": "",
  "skills": [],
  "experience": [
    {
      "company": "",
      "title": "",
      "location": "",
      "period": "",
      "bullets": []
    }
  ],
  "education": [],
  "certifications": [],
  "gap_list": [],
  "change_log": [],
  "factuality_notes": []
}
