from io import BytesIO

from docx import Document

from app.parser_v2 import parse_resume_v2
from app.analysis_v3 import analyze_quality_v3, analyze_job_match_v3


def make_resume():
    doc = Document()
    for line in [
        "Alex Doe",
        "alex@example.com",
        "Skills",
        "Python, Java, PostgreSQL, AWS, Docker",
        "Experience",
        "Software Engineer | Example Corp | 2022 - 2024",
        "• Built Python REST APIs serving 2 million requests per month.",
        "• Optimized PostgreSQL query latency by 35%.",
        "Projects",
        "• Developed an AWS-backed job processing service using Docker.",
        "Education",
        "Bachelor of Technology, Example University, 2022",
    ]:
        doc.add_paragraph(line)
    buffer = BytesIO()
    doc.save(buffer)
    return parse_resume_v2("resume.docx", buffer.getvalue())


def test_quality_v3_exposes_skill_provenance_and_keeps_score_contract():
    result = analyze_quality_v3(make_resume())
    assert 0 <= result["score"] <= 100
    assert result["version"] == "quality-v3"
    assert result["evidence_summary"]["recognized_skills"] >= 4
    assert result["evidence_summary"]["demonstrated_skills"] >= 3
    assert sum(item["possible"] for item in result["breakdown"]) == 100


def test_job_match_v3_extracts_requirement_priority_and_evidence():
    result = analyze_job_match_v3(
        make_resume(),
        "Required: Python and REST API development. "
        "Preferred: Docker. The engineer will build and maintain backend services.",
    )
    assert "python" in result["matched_required_skills"]
    assert "rest api" in result["matched_required_skills"]
    assert "docker" in result["matched_preferred_skills"]
    assert result["skill_matches"]
    assert any(item["status"] == "demonstrated" for item in result["skill_matches"])
    assert sum(item["possible"] for item in result["breakdown"]) == 100
    assert sum(item["earned"] for item in result["breakdown"]) == result["score"]


def test_neutral_skills_are_unassessed_and_not_scored_as_missing():
    result = analyze_job_match_v3(
        make_resume(),
        "The role uses Python and Java to build reliable backend applications.",
    )
    assert result["missing_required_skills"] == []
    assert "python" in result["not_assessed"]
    assert "java" in result["not_assessed"]


def test_listed_only_skill_gets_partial_credit_and_explanation():
    resume = make_resume()
    result = analyze_job_match_v3(
        resume,
        "Required: Java. The engineer will build reliable backend services.",
    )
    java = next(item for item in result["skill_matches"] if item["skill"] == "java")
    assert java["status"] == "listed"
    assert java["resume_evidence_ids"]
    assert any(item["code"] == "skills_listed_without_demonstration" for item in result["findings"])


def test_unknown_role_and_seniority_are_neutral_and_breakdown_is_100():
    result = analyze_job_match_v3(
        make_resume(),
        "Required: Python. Coordinate schedules and organize records for the team.",
    )
    assert result["role_alignment"]["assessment"] == "not_assessed"
    assert result["seniority_alignment"]["assessment"] == "not_assessed"
    assert sum(item["possible"] for item in result["breakdown"]) == 100
    assert sum(item["earned"] for item in result["breakdown"]) == result["score"]
