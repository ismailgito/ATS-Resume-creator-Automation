SYSTEM:
Write a short professional cover note for a job application. Use only verified candidate facts. Do not exaggerate or claim experience not present. Keep it specific to the role and under 180 words.

USER:
CANDIDATE PROFILE:
{{candidate_profile_json}}

JOB:
{{parsed_job_json}}

MATCH REPORT:
{{match_report_json}}

Return:
{
  "subject": "",
  "body": "",
  "claims_used": []
}
