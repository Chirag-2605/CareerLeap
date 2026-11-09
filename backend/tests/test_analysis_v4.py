import re
from io import BytesIO

from docx import Document

from app.parser_v2 import parse_resume_v2
from app.analysis_v4 import analyze_quality_v4, analyze_job_match_v4


def parse_lines(lines):
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buffer = BytesIO()
    doc.save(buffer)
    return parse_resume_v2("resume.docx", buffer.getvalue())


def weak_resume():
    return parse_lines([
        "Alex Doe", "alex@example.com", "Skills", "Python, Java",
        "Experience", "Intern", "Worked on backend tasks.",
        "Education", "College",
    ])


def strong_resume():
    return parse_lines([
        "Alex Doe", "alex@example.com", "https://linkedin.com/in/alex",
        "Summary", "Software engineer building reliable backend services.",
        "Skills", "Python, Java, PostgreSQL, AWS, Docker",
        "Experience", "Software Engineer | Example Corp | 2022 - 2024",
        "• Built Python REST APIs serving 2 million requests per month.",
        "• Reduced PostgreSQL query latency by 35% through indexing and query optimization.",
        "• Automated AWS deployment workflows, cutting release time by 40%.",
        "Projects", "• Developed a Docker-based job processing service handling 10k tasks daily.",
        "• Designed monitoring dashboards that reduced incident triage time by 25%.",
        "Education", "Bachelor of Technology, Example University, 2022",
    ])


def test_quality_v4_is_independent_and_scores_strong_resume_higher():
    weak = analyze_quality_v4(weak_resume())
    strong = analyze_quality_v4(strong_resume())
    assert weak["version"] == "quality-v4"
    assert strong["version"] == "quality-v4"
    assert 0 <= weak["score"] < strong["score"] <= 100
    assert sum(item["possible"] for item in strong["breakdown"]) == 100
    assert sum(item["earned"] for item in strong["breakdown"]) == strong["score"]


def test_quality_v4_rewards_measurable_evidence_not_just_sections():
    result = analyze_quality_v4(strong_resume())
    assert result["evidence_summary"]["measurable_bullets"] >= 3
    assert result["evidence_summary"]["experience_bullets"] >= 2
    assert result["breakdown"][0]["earned"] > 0


def test_jd_heading_context_classifies_bullets_as_required_and_preferred():
    result = analyze_job_match_v4(
        strong_resume(),
        "Backend Engineer\nRequired Qualifications:\n- Python\n- REST API\n"
        "Preferred Qualifications:\n- Docker\nResponsibilities:\n"
        "- Build and maintain backend services using Python and PostgreSQL.",
    )
    assert "python" in result["matched_required_skills"]
    assert "rest api" in result["matched_required_skills"]
    assert "docker" in result["matched_preferred_skills"]
    assert result["assessment_coverage"]["required_skills"] == 2
    assert result["breakdown"][0]["assessed"] is True


def test_unassessed_job_dimensions_do_not_receive_free_points():
    result = analyze_job_match_v4(
        strong_resume(),
        "The role involves supporting internal stakeholders and coordinating team schedules.",
    )
    assert result["assessment_coverage"]["required_skills"] == 0
    assert result["assessment_coverage"]["preferred_skills"] == 0
    assert result["breakdown"][0]["assessed"] is False
    assert result["breakdown"][0]["earned"] is None
    assert result["score"] is None
    assert result["score_status"] == "insufficient_data"


def test_responsibility_matching_keeps_lines_that_mention_technical_skills():
    result = analyze_job_match_v4(
        strong_resume(),
        "Backend Engineer\nResponsibilities:\n"
        "- Build Python APIs and maintain PostgreSQL-backed services for production users.",
    )
    assert result["assessment_coverage"]["responsibility_statements"] >= 1
    assert result["breakdown"][2]["assessed"] is True


def test_breakdown_score_is_normalized_over_assessed_dimensions():
    result = analyze_job_match_v4(
        strong_resume(),
        "Backend Engineer\nRequired Qualifications:\n- Python\n"
        "Responsibilities:\n- Build and maintain backend services.",
    )
    active = [item for item in result["breakdown"] if item["assessed"]]
    numerator = sum(item["earned"] for item in active)
    denominator = sum(item["possible"] for item in active)
    assert denominator == result["assessment_coverage"]["assessed_weight"]
    assert result["score"] == round(100.0 * numerator / denominator)



def test_metric_detection_handles_percentages_and_scale_nouns():
    from app.analysis_v4 import METRIC_RE

    examples = [
        "achieving 95% detection accuracy across 15+ restricted classes",
        "improve model precision by 9%",
        "auto-generate 30+ Athena SQL queries",
        "add 10+ datasets without frontend code changes",
        "increased task completion rates by 20%",
    ]
    assert all(METRIC_RE.search(value) for value in examples)


def test_bachelors_degree_variant_receives_degree_credit():
    parsed = parse_lines([
        "Alex Doe", "alex@example.com", "Education",
        "Bachelors of Technology in Computer Science and Engineering",
        "Example Institute 2022 - 2026",
    ])
    result = analyze_quality_v4(parsed)
    education = next(item for item in result["breakdown"] if item["key"] == "education")
    assert education["earned"] == 8


def test_role_only_job_match_is_insufficient_data_not_a_final_score():
    result = analyze_job_match_v4(
        strong_resume(),
        "Entry Level Software Engineer opportunity for the product engineering team.",
    )
    assert result["score"] is None
    assert result["score_status"] == "insufficient_data"
    assert result["provisional_score"] is not None
    assert result["assessment_coverage"]["assessed_weight"] < result["minimum_assessed_weight"]


def test_incomplete_numeric_claim_is_flagged_from_joined_bullet_text():
    parsed = parse_lines([
        "Alex Doe", "alex@example.com", "Experience",
        "Software Developer Intern",
        "• Integrated a chatbot for real-time support, enhancing user engagement by 25",
        "Education", "Bachelor of Technology, Example University, 2022",
    ])
    result = analyze_quality_v4(parsed)
    assert any(item["code"] == "incomplete_numeric_claim" for item in result["findings"])
    assert result["evidence_summary"]["incomplete_numeric_claims"] == 1


def test_long_skills_inventory_does_not_automatically_max_skill_component():
    parsed = parse_lines([
        "Alex Doe", "alex@example.com", "Skills",
        "Python, Java, JavaScript, TypeScript, React, Node.js, Express, SQL, "
        "PostgreSQL, MongoDB, AWS, Docker, Kubernetes, Git, Terraform",
        "Education", "Bachelor of Technology, Example University, 2022",
    ])
    result = analyze_quality_v4(parsed)
    skills = next(item for item in result["breakdown"] if item["key"] == "skills_evidence")
    assert skills["earned"] < skills["possible"]


JOB_DESCRIPTION_V42 = """# Software Engineer – Entry Level
Experience: 0–2 Years
### Job Description
We are looking for a motivated and talented Entry-Level Software Engineer to join our engineering team.
### Key Responsibilities
- Design, develop, test, and maintain reliable and scalable software applications.
- Write clean, efficient, and maintainable code using Java and Kotlin.
- Develop backend services, RESTful APIs, and application components.
- Work with relational databases and write optimized SQL queries.
- Participate in code reviews, debugging, and troubleshooting.
- Collaborate with product managers, QA engineers, and other developers.
- Follow software engineering best practices, including version control, testing, and documentation.
- Continuously learn new technologies and contribute to improving engineering processes.
### Required Skills and Qualifications
- Bachelor's degree in Computer Science, Information Technology, or a related field.
- Strong programming fundamentals and understanding of Data Structures and Algorithms.
- Proficiency in at least one programming language, preferably Java or Kotlin.
- Good understanding of Object-Oriented Programming (OOP) concepts.
- Working knowledge of SQL and relational databases such as PostgreSQL or MySQL.
- Understanding of database design, indexing, joins, and query optimization.
- Familiarity with REST APIs, HTTP protocols, and backend development concepts.
- Knowledge of Git and basic software development workflows.
- Strong analytical, problem-solving, and communication skills.
### Preferred Qualifications
- Familiarity with Kotlin, Java, Spring Boot, or similar backend frameworks.
- Understanding of multithreading, concurrency, and distributed systems.
- Exposure to cloud platforms such as AWS.
- Familiarity with build tools such as Gradle or Maven.
- Experience with unit testing and integration testing.
### What We Offer
- Opportunity to work on large-scale, high-performance software systems.
- Mentorship and opportunities for professional development.
"""


def test_v42_extracts_requirements_and_responsibilities_from_full_markdown_jd():
    from app.analysis_v4 import _extract_jd_skills

    parsed = _extract_jd_skills(JOB_DESCRIPTION_V42)
    required = {item["name"] for item in parsed if item["classification"] == "required"}
    preferred = {item["name"] for item in parsed if item["classification"] == "preferred"}
    assert {"java", "kotlin", "sql", "postgresql", "mysql", "git", "rest api"} <= required
    assert {"spring boot", "aws", "gradle", "maven", "distributed systems", "concurrency"} <= preferred

    result = analyze_job_match_v4(strong_resume(), JOB_DESCRIPTION_V42)
    assert result["assessment_coverage"]["required_skills"] >= 7
    assert result["assessment_coverage"]["preferred_skills"] >= 5
    assert result["assessment_coverage"]["responsibility_statements"] >= 7
    assert result["score_status"] == "assessed"


def test_v42_handles_collapsed_markdown_jd_headings_and_bullets():
    from app.analysis_v4 import _extract_jd_skills

    collapsed = re.sub(r"\\s+", " ", JOB_DESCRIPTION_V42)
    parsed = _extract_jd_skills(collapsed)
    required = {item["name"] for item in parsed if item["classification"] == "required"}
    preferred = {item["name"] for item in parsed if item["classification"] == "preferred"}
    assert "java" in required
    assert "spring boot" in preferred
