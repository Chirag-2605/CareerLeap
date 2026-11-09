from io import BytesIO

from docx import Document

from app.parser_v2 import parse_resume_v2
from app.analysis_v2 import analyze_quality_v2, analyze_job_match_v2


def make_resume():
    doc = Document()
    for line in [
        "Alex Doe",
        "alex@example.com",
        "https://linkedin.com/in/alex",
        "Summary",
        "Backend engineer with experience building Python services.",
        "Skills",
        "Python, Java, PostgreSQL, AWS",
        "Experience",
        "Software Engineer | Example Corp | 2022 - 2024",
        "• Built Python APIs serving 2 million requests per month.",
        "• Optimized PostgreSQL query latency by 35%.",
        "Projects",
        "• Developed an AWS-backed job processing service.",
        "Education",
        "Bachelor of Technology, Example University, 2022",
    ]:
        doc.add_paragraph(line)
    buffer = BytesIO()
    doc.save(buffer)
    return parse_resume_v2("resume.docx", buffer.getvalue())


def test_quality_v2_has_weighted_explainable_score():
    result = analyze_quality_v2(make_resume())
    assert 0 <= result["score"] <= 100
    assert sum(item["possible"] for item in result["breakdown"]) == 100
    assert sum(item["earned"] for item in result["breakdown"]) == result["score"]
    assert result["version"] == "quality-v2"
    assert all("recommendation" in item for item in result["findings"])


def test_quality_v2_uses_evidence_for_findings():
    result = analyze_quality_v2(make_resume())
    assert result["strengths"]
    assert result["strengths"][0]["evidence_ids"]


def test_job_match_v2_distinguishes_matched_and_missing_skills():
    result = analyze_job_match_v2(
        make_resume(),
        "Required: Python, Java, AWS and Kubernetes. Preferred: Docker and Terraform. "
        "The engineer will build backend services and maintain production systems.",
    )
    assert "python" in result["matched_required_skills"]
    assert "kubernetes" in result["missing_required_skills"]
    assert "docker" in result["missing_preferred_skills"]
    assert result["version"] == "match-v2"
    assert sum(item["possible"] for item in result["breakdown"]) == 100



def test_every_quality_deduction_has_an_explanation_and_valid_evidence():
    resume = make_resume()
    result = analyze_quality_v2(resume)
    deducted = [item for item in result["breakdown"] if item["deducted"] > 0]
    assert deducted
    assert all(any(
        finding["code"].startswith(item["key"] + "_")
        or finding["code"] == "component_deduction_" + item["key"]
        for finding in result["findings"]
    ) for item in deducted)
    valid_ids = {item["id"] for item in resume["evidence"]}
    assert all(set(finding["evidence_ids"]).issubset(valid_ids) for finding in result["findings"])


def test_neutral_job_skills_are_not_assumed_required():
    result = analyze_job_match_v2(
        make_resume(),
        "The engineer will use Python and Java to build backend services and maintain systems.",
    )
    assert result["missing_required_skills"] == []
    assert "python" in result["not_assessed"]
    assert "java" in result["not_assessed"]
