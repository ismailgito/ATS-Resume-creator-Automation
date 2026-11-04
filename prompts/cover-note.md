SYSTEM:
Write a short cover note for a job application in Germany. Use only verified candidate facts. Do not exaggerate or claim experience not present. Keep it specific to the role and under 150 words.

USER:
CANDIDATE PROFILE:
{{candidate_profile_json}}

JOB:
{{parsed_job_json}}

MATCH REPORT:
{{match_report_json}}

Write the body only, in English, in the first person. The greeting ("Sehr geehrte Damen und Herren,") and the sign-off ("Mit freundlichen Grüßen") are added by the software.

HOW IT MUST READ:
- Three short paragraphs: why this role at this company, one or two concrete pieces of evidence from the profile (with their real numbers), and a one-line close.
- Plain and direct, like a real person writing to a recruiter. No flattery about the company, no list of qualities.
- Do not open with "I am writing to express" or "I am excited to apply". Open with the role and the fact that makes the candidate relevant.
- Do not use these words or phrases: results-driven, passionate, dynamic, motivated, proven track record, leverage, spearhead, synergy, cutting-edge, seamless, robust, innovative, scalable, thrive, fast-paced, team player, detail-oriented, strong interest, furthermore, moreover.
- No em dashes. Never claim fluent German; mention the work permit only if it is in the profile.

Return:
{
  "subject": "Bewerbung als <job title> - <company>",
  "body": "",
  "claims_used": []
}
