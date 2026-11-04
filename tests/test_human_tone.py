"""Unit tests for human-writing helpers: AI-tell detection and skill de-duplication."""

from src.resume.skill_utils import dedupe_skills
from src.validate.human_tone import dash_count, find_ai_tells, repeated_openers


def test_find_ai_tells_catches_stock_phrases_and_inflections():
    text = "Results-driven marketer who spearheaded a robust, scalable funnel."
    assert find_ai_tells(text) == ["results-driven", "spearhead", "robust", "scalable"]


def test_find_ai_tells_ignores_plain_text():
    assert find_ai_tells("Ran Meta Ads lead campaigns and tracked CPL in GA4.") == []


def test_repeated_openers():
    bullets = ["Executed ads.", "Executed tests.", "Executed reports.", "Built a tracker."]
    assert repeated_openers(bullets) == ["executed"]
    assert repeated_openers(bullets[:2]) == []


def test_dash_count():
    assert dash_count("Plain sentence, with commas.") == 0
    assert dash_count("Ran ads — then reported — weekly.") == 2


def test_dedupe_skills_drops_subsumed_entries():
    skills = ["Paid Social", "Google Ads", "Google Ads (SEA)", "SEA", "PPC", "ppc"]
    assert dedupe_skills(skills) == ["Paid Social", "Google Ads (SEA)", "PPC"]


def test_dedupe_skills_respects_tools_list():
    skills = ["Meta Ads", "Lead Generation", "Google Analytics 4 (GA4)"]
    tools = ["Meta Ads Manager", "Google Analytics 4 (GA4)"]
    assert dedupe_skills(skills, also_covered_by=tools) == ["Lead Generation"]
