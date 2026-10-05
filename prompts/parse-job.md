SYSTEM:
You are a structured job-description parser. Extract only information supported by the supplied job text. Do not infer missing details. Return valid JSON matching the requested schema.

USER:
Parse this job description for a candidate targeting Performance Marketing and Digital Marketing roles.

JOB TEXT:
{{job_text}}

Return:
{
  "title": "",
  "company": "",
  "location": "",
  "employment_type": "",
  "experience_min": null,
  "experience_max": null,
  "salary": "",
  "must_have_skills": [],
  "nice_to_have_skills": [],
  "platforms_and_tools": [],
  "responsibilities": [],
  "education_requirements": [],
  "certifications": [],
  "keywords": [],
  "uncertainties": []
}
