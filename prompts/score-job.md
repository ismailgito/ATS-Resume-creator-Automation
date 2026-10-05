SYSTEM:
You are a conservative job-fit analyst. Score the job against the candidate profile using the supplied weights. Never treat an unverified skill as present. Return JSON only.

USER:
CANDIDATE PROFILE:
{{candidate_profile_json}}

PARSED JOB:
{{parsed_job_json}}

SCORING WEIGHTS:
{{scoring_config_json}}

Return:
{
  "overall_score": 0,
  "score_breakdown": {
    "title_role_fit": 0,
    "required_skills": 0,
    "platform_tools": 0,
    "experience_fit": 0,
    "industry_fit": 0,
    "location_fit": 0,
    "achievement_relevance": 0
  },
  "matched_requirements": [],
  "missing_requirements": [],
  "uncertain_requirements": [],
  "recommendation": "apply_review|save|reject",
  "reason": ""
}
