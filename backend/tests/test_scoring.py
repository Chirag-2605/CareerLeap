from app.scoring import analyze_quality, analyze_job_match

SAMPLE = '''
Alex Doe
alex@example.com | +1 415 555 0199 | https://linkedin.com/in/alex
Professional Summary
Software engineer with experience building scalable backend systems.
Skills
Python, Java, SQL, AWS, Docker, PostgreSQL, React, Git
Experience
Software Engineer, Acme Corp, 2022 - 2024
- Built APIs serving 2 million requests per month.
- Optimized query latency by 35%.
- Automated deployments and reduced release time by 4 hours.
Education
Bachelor of Technology, Example University, 2022
Projects
Created a distributed job processing platform.
'''

def test_quality_score_is_bounded_and_explainable():
    result = analyze_quality(SAMPLE)
    assert 0 <= result["score"] <= 100
    assert sum(x["possible"] for x in result["breakdown"]) == 100
    assert sum(x["earned"] for x in result["breakdown"]) == result["score"]
    assert result["version"] == "quality-v2"

def test_job_match_returns_separate_score():
    result = analyze_job_match(SAMPLE, "We need a Python Java backend engineer with AWS, SQL, Docker and Kubernetes.")
    assert 0 <= result["score"] <= 100
    assert "python" in result["matched_skills"]
    assert "kubernetes" in result["missing_skills"]
    assert result["version"] == "match-v2"

def test_quality_deductions_have_recommendations():
    result = analyze_quality("A short resume without sections or contact information.")
    assert result["findings"]
    assert all(f["recommendation"] for f in result["findings"])


def test_job_match_includes_specific_edit_guidance_for_missing_skill():
    resume = """
Alex Doe
alex@example.com
Skills
JavaScript, Python, SQL
Experience
Backend Developer
- Built REST APIs using Python and PostgreSQL for internal tools.
Education
Bachelor of Technology, Example University, 2024
"""
    result = analyze_job_match(
        resume,
        "Required skills: Java and Python. Responsibilities include designing backend APIs and troubleshooting production issues.",
    )
    java = next(item for item in result["actionable_suggestions"] if item["code"] == "add_missing_skill_java")
    assert java["where_to_edit"] == "Skills section"
    assert java["target_line"]["text"] == "Skills"
    assert "only if accurate" in java["safe_wording"]


def test_job_match_guidance_avoids_generic_jd_fillers():
    resume = "Skills\nJavaScript\nExperience\n- Built frontend components for an internal dashboard."
    result = analyze_job_match(
        resume,
        "We require strong knowledge and experience designing, troubleshooting, analyzing and writing software.",
    )
    suggestions = result["actionable_suggestions"]
    assert all("knowledge" not in item.get("what_is_missing", "").lower() for item in suggestions)
    assert all("requirements" not in item.get("what_is_missing", "").lower() for item in suggestions)


def test_quality_suggestions_point_to_edit_location_and_template():
    result = analyze_quality(SAMPLE.replace("Professional Summary\nSoftware engineer with experience building scalable backend systems.\n", ""))
    summary = next(item for item in result["actionable_suggestions"] if item["code"] == "add_summary_section")
    assert summary["where_to_edit"] == "Below your contact details and before Experience"
    assert "optional" in summary["what_is_missing"].lower()
    assert "Replace every bracket" in summary["safe_wording"]


def test_my_skills_heading_is_detected_and_credited():
    resume = """
Alex Doe
alex@example.com
MY SKILLS
Java (Basic), Python, HTML, CSS
WORK EXPERIENCE
Software Intern — ABC Company (2025)
- Worked on different projects.
EDUCATION
B.Tech Computer Science, ABC College, 2026
"""
    result = analyze_quality(resume)
    structure = next(item for item in result["breakdown"] if item["key"] == "structure")
    assert structure["earned"] >= 13  # Experience + education + skills; summary remains optional.
    assert not any(item["code"] == "missing_skills_section" for item in result["findings"])


def test_vague_experience_does_not_receive_full_experience_score():
    resume = """
Alex Doe
alex@example.com
MY SKILLS
Java (Basic), Python, HTML, CSS
WORK EXPERIENCE
Software Intern — ABC Company (2025)
- Worked on different projects.
- Helped seniors with coding.
- Did some frontend and backend work.
- Fixed bugs whenever required.
EDUCATION
B.Tech Computer Science, ABC College, 2026
PROJECTS
- Built a website using React and PostgreSQL.
"""
    result = analyze_quality(resume)
    experience = next(item for item in result["breakdown"] if item["key"] == "experience")
    assert experience["earned"] < 25
    assert experience["earned"] < 20


def test_job_match_explains_when_jd_has_no_recognized_skills():
    resume = "Skills\nPython\nExperience\n- Built backend tools."
    result = analyze_job_match(
        resume,
        "We are looking for a reliable software engineer to work with a team and test code."
    )
    assert result["missing_skills"] == []
    assert "No recognized technical skills" in result["summary"]
    suggestions = result["actionable_suggestions"]
    assert all("looking" not in item.get("what_is_missing", "").lower() for item in suggestions)
    assert all("reliable" not in item.get("what_is_missing", "").lower() for item in suggestions)



def test_ats_readability_measures_extraction_not_resume_length():
    clean_short_resume = """Alex Doe
alex@example.com
Skills
Python, HTML, CSS
Experience
Software Intern
- Built a small web interface using HTML and CSS.
Education
B.Tech Computer Science, Example College, 2026
"""
    result = analyze_quality(clean_short_resume)
    readability = next(item for item in result["breakdown"] if item["key"] == "readability")
    assert readability["earned"] == 10


def test_ats_readability_penalizes_flattened_unstructured_extraction():
    flattened = "Alex Doe alex@example.com Python HTML CSS Software Intern built a web interface B.Tech Example College 2026"
    result = analyze_quality(flattened)
    readability = next(item for item in result["breakdown"] if item["key"] == "readability")
    assert readability["earned"] < 10
    assert any(item["code"] == "low_line_structure" for item in result["findings"])


def test_generic_software_intern_title_does_not_get_full_frontend_alignment():
    resume = """JOHN DOE
Job Seeker
Email: johndoe@email.com | Phone: 9876543210
EDUCATION
ABC Engineering College — B.Tech Computer Science (2022–2026)
MY SKILLS
Computer, Coding, Java (Basic), Python, HTML, CSS
WORK EXPERIENCE
Software Intern — ABC Company (2025)
- Worked on different projects.
- Helped seniors with coding.
- Did some frontend and backend work.
- Fixed bugs whenever required.
PERSONAL PROJECTS
Project 1 — Management System
- Made a project using programming.
"""
    result = analyze_job_match(
        resume,
        "Frontend Engineer. Build responsive web applications using JavaScript, HTML, CSS, React, TypeScript and Git.",
    )
    role = next(item for item in result["breakdown"] if item["key"] == "role_alignment")
    assert role["earned"] < role["possible"]
    assert result["role_alignment"]["candidate_family"] == "software_engineering"
    assert result["role_alignment"]["target_family"] == "frontend"
    assert result["role_alignment"]["assessment"] == "broadly_related"


def test_explicit_frontend_title_gets_full_frontend_alignment():
    resume = """Alex Doe
Skills
React, TypeScript
Experience
Frontend Engineer
- Built reusable React components for a customer dashboard.
Education
B.Tech Computer Science, Example University, 2026
"""
    result = analyze_job_match(
        resume,
        "Frontend Engineer. Build responsive web applications using React and TypeScript.",
    )
    role = next(item for item in result["breakdown"] if item["key"] == "role_alignment")
    assert role["earned"] == role["possible"] == 15
    assert result["role_alignment"]["assessment"] == "aligned"
