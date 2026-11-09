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
    assert "rest api" in result["missing_required_skills"]
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
    assert result["score"] == 0 or result["assessment_coverage"]["assessed_weight"] > 0


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
