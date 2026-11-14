from app.suggestion_design import design_suggestions


WEAK_SAMPLE = """JOHN DOE
Job Seeker
Email: johndoe@email.com | Phone: 9876543210
ABOUT ME
Hardworking person interested in technology.
EDUCATION
ABC Engineering College — B.Tech Computer Science (2022–2026)
MY SKILLS
Computer, Coding, Java (Basic), Python, HTML, CSS
WORK EXPERIENCE
Software Intern — ABC Company (2025)
• Worked on different projects.
• Helped seniors with coding.
• Did some frontend and backend work.
• Fixed bugs whenever required.
• Learned many new technologies.
• Attended meetings and discussed work.
PERSONAL PROJECTS
Project 1 — Management System
• Made a project using programming.
• It was useful for managing things.
Project 2 — Website
• Created a website.
• Added some features.
"""


def test_suggestion_design_prioritizes_weak_experience_and_projects():
    quality = {"findings": [{"code": "few_metrics"}], "actionable_suggestions": []}
    result = design_suggestions(WEAK_SAMPLE, quality)

    assert result["version"] == "suggestion-design-v1"
    assert result["items"]
    assert result["items"][0]["priority"] == "high"
    assert any(item["category"] == "experience_evidence" for item in result["items"])
    assert any(item["category"] == "project_evidence" for item in result["items"])


def test_suggestions_include_source_lines_questions_and_safe_rewrite_templates():
    result = design_suggestions(WEAK_SAMPLE, {"findings": [{"code": "few_metrics"}]})
    experience = next(item for item in result["items"] if item["category"] == "experience_evidence")

    assert experience["source_line"]["line"] == 12
    assert experience["questions_to_answer"]
    assert "[technology or method]" in experience["rewrite_template"]
    assert "[verified outcome or scope]" in experience["rewrite_template"]
    assert "20%" not in experience["rewrite_template"]
    assert "verify" in experience["safety_note"].lower()


def test_impact_guidance_does_not_require_or_invent_metrics():
    result = design_suggestions(WEAK_SAMPLE, {"findings": [{"code": "few_metrics"}]})
    impact = next(item for item in result["items"] if item["category"] == "impact")

    assert "metric is optional" in impact["impact_guidance"].lower() or "number only" in impact["impact_guidance"].lower()
    assert "qualitative" in impact["questions_to_answer"][-1].lower()


def test_listed_only_skills_are_described_as_evidence_gap_not_missing_ability():
    result = design_suggestions(WEAK_SAMPLE, {"findings": []})
    skills = next(item for item in result["items"] if item["category"] == "skills_evidence")

    assert "java" in skills["why_it_matters"].lower()
    assert "not proof" in skills["why_it_matters"].lower()


def test_optional_summary_and_profile_link_are_low_priority():
    resume = """Alex Doe
alex@example.com
Skills
Python
Experience
Software Intern
• Built an API using Python.
Education
B.Tech, Example College, 2025
"""
    result = design_suggestions(resume, {"findings": []})
    optional = [item for item in result["items"] if item["priority"] == "low"]

    assert {item["code"] for item in optional} == {
        "optional_targeted_summary", "optional_professional_profile_link"
    }


def test_job_match_gaps_become_contextual_prompts_not_keyword_stuffing():
    job_match = {
        "skill_gaps": [
            {
                "skill": "kotlin",
                "classification": "required",
                "status": "not_found",
            },
            {
                "skill": "docker",
                "classification": "preferred",
                "status": "not_found",
            },
        ]
    }
    result = design_suggestions("Alex Doe\nExperience\n• Built a dashboard.", {"findings": []}, job_match)
    job_items = [item for item in result["items"] if item["category"] == "job_match"]

    assert len(job_items) == 2
    assert any("genuinely used" in item["why_it_matters"] for item in job_items)
    assert next(item for item in job_items if "kotlin" in item["code"])["priority"] == "high"
    assert next(item for item in job_items if "docker" in item["code"])["priority"] == "medium"
    assert all(item["questions_to_answer"] for item in job_items)
    assert all("keyword list" not in item["rewrite_template"].lower() for item in job_items if item["rewrite_template"])
