import re
from io import BytesIO

from docx import Document

from app.parser_v2 import parse_resume_v2
from app.analysis_v4 import analyze_quality_v4, analyze_job_match_v4
from app.suggestion_design import design_suggestions


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
    # V4.3 groups explicit OR alternatives into one any-of requirement.
    assert {"programming_language", "sql", "database", "git", "rest api"} <= required
    assert {"spring boot", "aws", "build_tool", "distributed systems", "concurrency"} <= preferred
    programming_language = next(item for item in parsed if item["name"] == "programming_language")
    database = next(item for item in parsed if item["name"] == "database")
    build_tool = next(item for item in parsed if item["name"] == "build_tool")
    assert programming_language["alternatives"] == ["java", "kotlin"]
    assert database["alternatives"] == ["postgresql", "mysql"]
    assert build_tool["alternatives"] == ["gradle", "maven"]

    result = analyze_job_match_v4(strong_resume(), JOB_DESCRIPTION_V42)
    assert result["assessment_coverage"]["required_skills"] >= 7
    assert result["assessment_coverage"]["preferred_skills"] >= 5
    assert result["assessment_coverage"]["responsibility_statements"] >= 7
    assert result["score_status"] == "assessed"


def test_v42_handles_collapsed_markdown_jd_headings_and_bullets():
    from app.analysis_v4 import _extract_jd_skills

    collapsed = re.sub(r"\s+", " ", JOB_DESCRIPTION_V42)
    parsed = _extract_jd_skills(collapsed)
    required = {item["name"] for item in parsed if item["classification"] == "required"}
    preferred = {item["name"] for item in parsed if item["classification"] == "preferred"}
    # Collapsed Markdown must preserve the V4.3 OR-group contract as well.
    assert "programming_language" in required
    assert "spring boot" in preferred
    grouped = next(item for item in parsed if item["name"] == "programming_language")
    assert grouped["alternatives"] == ["java", "kotlin"]


def test_parser_recognizes_core_concepts_without_inflating_related_skills():
    parsed = parse_lines([
        "Alex Doe", "alex@example.com", "Skills",
        "Data Structures & Algorithms, Object-Oriented Design, Distributed Systems, API Development",
        "Experience", "Software Engineer Intern",
        "• Built REST APIs using Java for internal services.",
    ])
    by_name = {item["canonical_name"]: item for item in parsed["skills"]}
    assert "data structures and algorithms" in by_name
    assert "object-oriented programming" in by_name
    assert "distributed systems" in by_name
    assert "api development" in by_name
    assert by_name["data structures and algorithms"]["listed_evidence_ids"]
    assert by_name["api development"]["listed_evidence_ids"]
    assert "http" not in by_name


def test_explicit_or_requirements_are_grouped_and_any_alternative_satisfies():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills", "Java, PostgreSQL, Gradle",
        "Experience", "Software Engineer Intern",
        "• Built Java backend services using PostgreSQL and Gradle.",
    ])
    jd = (
        "Entry Level Software Engineer\nExperience: 0-2 Years\n"
        "Required Qualifications:\n- Java or Kotlin\n"
        "- PostgreSQL or MySQL\n- Gradle or Maven"
    )
    from app.analysis_v4 import _extract_jd_skills
    requirements = _extract_jd_skills(jd)
    groups = [item for item in requirements if item.get("alternatives")]
    assert {item["name"] for item in groups} == {"programming_language", "database", "build_tool"}
    assert len([item for item in requirements if item["classification"] == "required"]) == 3
    result = analyze_job_match_v4(resume, jd)
    assert result["missing_required_skills"] == []
    assert len(result["matched_required_skills"]) == 3
    assert all(item["status"] == "demonstrated" for item in result["skill_matches"])


def test_listed_only_alternative_skills_remain_listed_not_demonstrated():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills", "Java, PostgreSQL, Gradle",
        "Experience", "Software Engineer Intern",
        "• Built a responsive React interface for internal users.",
    ])
    result = analyze_job_match_v4(
        resume,
        "Required Qualifications:\n- Java or Kotlin\n- PostgreSQL or MySQL\n- Gradle or Maven",
    )
    assert len(result["matched_required_skills"]) == 3
    assert all(item["status"] == "listed" for item in result["skill_matches"])


def test_responsibility_matching_uses_related_artifact_and_action_concepts():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills", "React, TypeScript, SQL",
        "Experience", "Software Engineer Intern",
        "• Built a dynamic scalable UI using React and TypeScript, enabling 10+ datasets.",
        "• Designed backend modules using Mustache templating to generate 30+ Athena SQL queries.",
        "• Automated IAM roles, policies and S3 provisioning using Terraform.",
    ])
    result = analyze_job_match_v4(
        resume,
        "Backend Engineer\nResponsibilities:\n"
        "- Design, develop, test, and maintain reliable and scalable software applications.",
    )
    assert result["responsibility_matches"]
    match = result["responsibility_matches"][0]
    assert match["evidence_type"] in ("direct", "supporting")
    assert len(match["evidence_ids"]) >= 1


def test_internship_is_aligned_with_entry_role_when_jd_accepts_zero_to_two_years():
    result = analyze_job_match_v4(
        weak_resume(),
        "Entry Level Software Engineer\nExperience: 0-2 Years\n"
        "Required Qualifications:\n- Java",
    )
    assert result["seniority_alignment"]["assessment"] == "aligned"


def test_v4_matches_added_core_skills_but_does_not_infer_http_from_api_development():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills",
        "Data Structures & Algorithms, Object-Oriented Design, Distributed Systems, API Development",
        "Experience", "Software Engineer Intern",
        "• Built a React dashboard for internal users.",
    ])
    result = analyze_job_match_v4(
        resume,
        "Required Qualifications:\n- Data Structures and Algorithms\n"
        "- Object-Oriented Programming\n- Distributed Systems\n"
        "- API Development\n- HTTP protocols",
    )
    assert set(result["matched_required_skills"]) == {
        "data structures and algorithms", "object-oriented programming",
        "distributed systems", "api development",
    }
    assert result["missing_required_skills"] == ["http"]
    assert all(item["status"] == "listed" for item in result["skill_matches"])



def test_single_v4_pipeline_feeds_post_analysis_suggestion_design():
    parsed = weak_resume()
    quality = analyze_quality_v4(parsed)
    job_match = analyze_job_match_v4(
        parsed,
        "Required Qualifications:\n- Python\n- Kotlin\n"
        "Responsibilities:\n- Build and maintain backend services using Python.",
    )
    resume_text = "\n".join(item["text"] for item in parsed["evidence"])
    plan = design_suggestions(resume_text, quality, job_match)

    assert quality["version"] == "quality-v4"
    assert job_match["version"] == "match-v4"
    assert plan["version"] == "suggestion-design-v1"
    assert any(item["category"] == "job_match" for item in plan["items"])
    assert all("verif" in item["safety_note"].lower() for item in plan["items"])



def test_one_of_programming_languages_is_counted_as_one_required_group():
    result = analyze_job_match_v4(
        strong_resume(),
        "Software Engineer\nRequired Qualifications:\n"
        "- Strong proficiency in at least one of Java, Python, C++, JavaScript, or TypeScript.\n"
        "Responsibilities:\n- Build and maintain reliable software services.",
    )
    assert result["assessment_coverage"]["required_skills"] == 1
    assert "programming_language" in result["matched_required_skills"]


def test_sdet_tooling_is_recognized_as_job_and_resume_skill_evidence():
    resume = parse_lines([
        "Alex Doe", "Skills", "Python, Playwright, pytest, SQL",
        "Experience", "QA Automation Intern",
        "• Built API regression tests using Python, Playwright, and pytest.",
        "Education", "Example University",
    ])
    result = analyze_job_match_v4(
        resume,
        "SDET\nRequired Qualifications:\n- Python\n- Playwright\n- pytest\n"
        "Responsibilities:\n- Build and maintain API regression tests.",
    )
    assert "playwright" in result["matched_required_skills"]
    assert "pytest" in result["matched_required_skills"]
