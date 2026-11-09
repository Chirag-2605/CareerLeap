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
    metric_finding = next(item for item in result["findings"] if item["code"] == "impact_metrics_limited")
    assert metric_finding["evidence_ids"]


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
