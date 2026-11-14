"""Regression tests built from anonymized evidence in three real resume scans.

The source PDFs are intentionally not committed. These fixtures preserve only
resume facts needed to test parser provenance, skill evidence and job matching.
"""
from io import BytesIO
import argparse
import json
from pathlib import Path

from docx import Document

from app.analysis_v4 import analyze_job_match_v4, analyze_quality_v4
from app.parser_v2 import parse_resume_v2
from app.services.evidence_service import collect_evidence
from app.services.responsibility_matching_service import match_responsibilities


FULL_STACK_JD = """Role: Full Stack Developer
Level: Entry-Level / 0–3 years
Role overview:
Deliver complete product features across frontend, backend, and data layers.
Key responsibilities:
- Build responsive interfaces and reusable components using a modern frontend framework.
- Implement backend endpoints, business logic, validation, and authentication flows.
- Design database schemas and integrate relational or NoSQL storage.
- Connect frontend experiences to APIs and handle loading, empty, success, and error states.
- Test features, debug issues across the stack, review code, and support deployments.
Required qualifications:
- JavaScript or TypeScript, React, HTML, CSS, and responsive UI development.
- Backend development using Node.js, Java, Python, or a comparable language.
- REST API design and integration, HTTP, JSON, and asynchronous programming.
- SQL and database fundamentals; familiarity with at least one relational or NoSQL database.
- Git, debugging, testing, data structures, and object-oriented programming fundamentals.
Preferred qualifications:
- Express.js, Next.js, Spring Boot, or similar frameworks.
- PostgreSQL, MySQL, MongoDB, Redis, or cloud-hosted databases.
- JWT, OAuth, role-based access control, WebSockets, or third-party integrations.
- Docker, AWS, CI/CD, automated testing, and end-to-end deployment experience.
"""


def parse_lines(lines):
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buffer = BytesIO()
    doc.save(buffer)
    return parse_resume_v2("resume.docx", buffer.getvalue())


def strong_engineering_resume():
    return parse_lines([
        "Candidate", "candidate@example.com", "Summary",
        "Software engineer with experience building full-stack products.",
        "Education", "Bachelor of Technology in Computer Science, Example Institute, 2026",
        "Skills", "React, TypeScript, Python, AWS, REST API, WebSockets, SQL, Git, MongoDB",
        "Experience", "Software Development Intern — Product Company | 2025",
        "• Built responsive React interfaces and reusable components for a dashboard used across 10+ datasets.",
        "• Implemented backend API endpoints with request validation and JWT authentication.",
        "• Designed PostgreSQL database schemas and integrated MongoDB storage.",
        "• Implemented browser-based SSH sessions using WebSockets and AWS Systems Manager.",
        "• Developed backend endpoints and automated AWS workflows using Python.",
        "• Reduced manual monitoring from several hours to under 5 minutes.",
        "Projects", "NovaChat — Full Stack Application",
        "• Built a MERN application using React, Node.js, Express.js, MongoDB and JWT authentication.",
        "• Integrated WebRTC and Socket.io for real-time communication.",
    ])


def fresh_data_analyst_resume():
    return parse_lines([
        "Candidate", "candidate@example.com", "Professional Summary",
        "Recent Statistics graduate with hands-on experience in data analysis and reporting.",
        "Education", "B.Sc. Statistics, Example University, 2022–2025, CGPA 8.6/10",
        "Experience", "Business Analytics Intern — Retail Company | January 2025 – June 2025",
        "• Analyzed approximately 50,000 monthly retail transactions using Python and SQL.",
        "• Developed Power BI dashboards tracking sales across 12 business regions.",
        "• Identified a 14% decline in repeat purchases and presented findings to marketing.",
        "• Automated weekly reporting using Python and Excel, reducing work from 5 hours to 45 minutes.",
        "Projects", "Customer Churn Analysis",
        "• Analyzed 10,000 customer records using Python, Pandas, NumPy, Matplotlib and Seaborn.",
        "• Applied logistic regression to identify high-risk segments, achieving 81% test accuracy.",
        "Skills", "Python, R, Pandas, NumPy, SQL, MySQL, Power BI, Excel, Statistics, Git, GitHub",
    ])


def bad_generic_resume():
    return parse_lines([
        "Candidate", "candidate@example.com", "About Me",
        "I am hardworking, passionate, a quick learner and team player.",
        "Education", "B.Tech Computer Science, Example College, 2022–2026",
        "My Skills", "Computer, Coding, Java Basic, Python, HTML, CSS, Communication, Teamwork",
        "Work Experience", "Software Intern — Example Company | 2025",
        "• Worked on different projects.",
        "• Helped seniors with coding.",
        "• Did some frontend and backend work.",
        "• Fixed bugs whenever required.",
        "• Learned many new technologies.",
        "Personal Projects", "Project 1 — Management System",
        "• Made a project using programming.",
        "• It was useful for managing things.",
        "• Used database and frontend.",
    ])


def test_same_full_stack_jd_ranks_engineering_evidence_above_unrelated_or_generic_resumes():
    strong = analyze_job_match_v4(strong_engineering_resume(), FULL_STACK_JD)
    fresh = analyze_job_match_v4(fresh_data_analyst_resume(), FULL_STACK_JD)
    bad = analyze_job_match_v4(bad_generic_resume(), FULL_STACK_JD)

    assert strong["score"] > fresh["score"]
    assert strong["score"] > bad["score"]
    # The analytics resume demonstrates transferable SQL/Python/data evidence;
    # the generic resume should not tie or outrank it on responsibilities.
    assert fresh["dimension_assessments"]["skill_matching"]["required"] > (
        bad["dimension_assessments"]["skill_matching"]["required"]
    )


def test_numpy_in_project_bullet_is_demonstrated_not_listed_only():
    parsed = fresh_data_analyst_resume()
    numpy = next(skill for skill in parsed["skills"] if skill["canonical_name"] == "numpy")
    assert numpy["demonstrated_evidence_ids"]
    assert not numpy["listed_evidence_ids"] or len(numpy["demonstrated_evidence_ids"]) > 0
    project_evidence = collect_evidence(parsed, sections=("projects",))
    assert any("NumPy" in item["text"] for item in project_evidence)


def test_skills_section_only_evidence_remains_listed_not_demonstrated():
    parsed = bad_generic_resume()
    java = next(skill for skill in parsed["skills"] if skill["canonical_name"] == "java")
    assert java["listed_evidence_ids"]
    assert java["demonstrated_evidence_ids"] == []


def test_generic_resume_bullets_do_not_match_specific_full_stack_responsibilities():
    parsed = bad_generic_resume()
    bullets = [
        {"text": item["text"], "evidence_ids": item["evidence_ids"]}
        for item in collect_evidence(parsed, sections=("experience", "projects"))
        if item["kind"] == "bullet"
    ]
    responsibilities = [
        "Build responsive interfaces and reusable components using a modern frontend framework.",
        "Implement backend endpoints, business logic, validation, and authentication flows.",
        "Design database schemas and integrate relational or NoSQL storage.",
        "Test features, debug issues across the stack, review code, and support deployments.",
    ]
    matches, score = match_responsibilities(responsibilities, bullets)
    assert matches == []
    assert score == 0


def test_engineering_bullets_match_responsibilities_with_traceable_source_ids():
    parsed = strong_engineering_resume()
    bullets = [
        {"text": item["text"], "evidence_ids": item["evidence_ids"]}
        for item in collect_evidence(parsed, sections=("experience", "projects"))
        if item["kind"] == "bullet"
    ]
    matches, score = match_responsibilities(
        [
            "Build responsive interfaces and reusable components using a modern frontend framework.",
            "Implement backend endpoints, business logic, validation, and authentication flows.",
            "Connect frontend experiences to APIs and handle loading, empty, success, and error states.",
        ],
        bullets,
    )
    assert matches
    assert score is not None and score > 0
    assert all(match["evidence_ids"] for match in matches)


def test_resume_quality_order_is_consistent_with_three_anonymized_profiles():
    scores = [
        analyze_quality_v4(strong_engineering_resume())["score"],
        analyze_quality_v4(fresh_data_analyst_resume())["score"],
        analyze_quality_v4(bad_generic_resume())["score"],
    ]
    assert scores[0] > scores[1] > scores[2]



def build_regression_report():
    """Return comparable quality and job-match output for all three fixtures."""
    profiles = (
        ("strong_engineering", strong_engineering_resume()),
        ("fresh_data_analyst", fresh_data_analyst_resume()),
        ("bad_generic", bad_generic_resume()),
    )
    report = {"job_description": "Full Stack Developer — Entry-Level / 0–3 years", "profiles": []}
    for name, resume in profiles:
        quality = analyze_quality_v4(resume)
        match = analyze_job_match_v4(resume, FULL_STACK_JD)
        report["profiles"].append({
            "profile": name,
            "resume_quality": quality["score"],
            "quality_breakdown": quality["breakdown"],
            "job_match": match["score"],
            "job_match_status": match["score_status"],
            "job_match_breakdown": match["breakdown"],
            "required_skill_matches": match["skill_matches"],
            "missing_required_skills": match["missing_required_skills"],
            "missing_preferred_skills": match["missing_preferred_skills"],
            "responsibility_matches": match["responsibility_matches"],
            "role_alignment": match["role_alignment"],
            "seniority_alignment": match["seniority_alignment"],
        })
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a local, comparable CareerLeap analyzer regression report."
    )
    parser.add_argument(
        "--output", default="artifacts/analyzer-regression-report.json",
        help="JSON output path (default: artifacts/analyzer-regression-report.json)",
    )
    args = parser.parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = build_regression_report()
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Wrote analyzer regression report to {0}".format(output_path))
    for item in result["profiles"]:
        print(
            "{0}: quality={1}/100, job_match={2}".format(
                item["profile"], item["resume_quality"],
                str(item["job_match"]) + "/100" if item["job_match"] is not None else "not assessed",
            )
        )
