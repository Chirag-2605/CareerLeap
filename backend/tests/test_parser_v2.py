from io import BytesIO

from docx import Document

from app.parser_v2 import parse_resume_v2


def make_docx(paragraphs):
    doc = Document()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_parse_docx_builds_sections_and_evidence():
    content = make_docx([
        "Alex Doe",
        "alex@example.com",
        "Professional Summary",
        "Software developer with experience building Python services.",
        "Skills",
        "Python, Java, PostgreSQL, React",
        "Experience",
        "Software Engineer | Example Corp | 2022 - 2024",
        "• Built Python APIs and improved response time by 30%.",
        "Education",
        "Bachelor of Technology, Example University, 2022",
    ])

    result = parse_resume_v2("resume.docx", content)

    assert result["schema_version"] == "resume-v2"
    assert result["candidate"]["name"] == "Alex Doe"
    assert result["candidate"]["email"] == "alex@example.com"
    section_types = [section["type"] for section in result["sections"]]
    assert "summary" in section_types
    assert "skills" in section_types
    assert "experience" in section_types
    assert "education" in section_types
    assert {"python", "java", "postgresql", "react"}.issubset(
        {skill["canonical_name"] for skill in result["skills"]}
    )
    assert result["evidence"]
    evidence_ids = {item["id"] for item in result["evidence"]}
    for section in result["sections"]:
        assert set(section["evidence_ids"]).issubset(evidence_ids)
        for item in section["items"]:
            assert item["evidence_id"] in evidence_ids
            assert set(item["evidence_ids"]).issubset(evidence_ids)


def test_parse_docx_preserves_table_rows_as_evidence():
    doc = Document()
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Education"
    table.cell(0, 1).text = "Bachelor of Engineering"
    doc.add_paragraph("Contact alex@example.com and additional resume details for parser validation.")
    buffer = BytesIO()
    doc.save(buffer)

    result = parse_resume_v2("resume.docx", buffer.getvalue())

    table_evidence = [item for item in result["evidence"] if item["source"] == "docx_table"]
    assert table_evidence
    assert table_evidence[0]["table_index"] == 0
    assert table_evidence[0]["row_index"] == 0


def test_detects_additional_section_aliases_as_separate_sections():
    content = make_docx([
        "Alex Doe",
        "alex@example.com",
        "Technical Highlights",
        "Java, Kotlin, AWS Athena, IAM, S3, Terraform",
        "Projects",
        "Built a distributed service using Java.",
        "Achievements",
        "Finalist in a design event.",
        "Positions of Responsibility",
        "Mentored 20 students.",
    ])

    result = parse_resume_v2("resume.docx", content)
    sections = {section["type"]: section for section in result["sections"]}

    assert "skills" in sections
    assert "projects" in sections
    assert "awards" in sections
    assert "leadership" in sections
    assert "Technical Highlights" == sections["skills"]["heading"]
    assert "Positions of Responsibility" == sections["leadership"]["heading"]


def test_joins_wrapped_bullet_lines_and_preserves_all_evidence_ids():
    content = make_docx([
        "Alex Doe",
        "alex@example.com",
        "Experience",
        "• Built a dynamic UI using React and TypeScript, enabling 10+ datasets",
        "without any frontend code changes.",
        "• Integrated Mon-",
        "goDB for persistence.",
    ])

    result = parse_resume_v2("resume.docx", content)
    experience = next(section for section in result["sections"] if section["type"] == "experience")
    bullets = [item for item in experience["items"] if item["kind"] == "bullet"]

    assert len(bullets) == 2
    assert bullets[0]["text"].endswith("without any frontend code changes.")
    assert "MongoDB" in bullets[1]["text"]
    assert len(bullets[0]["evidence_ids"]) == 2
    assert len(bullets[1]["evidence_ids"]) == 2


def test_extracts_multiple_profile_urls_and_deduplicates_skill_aliases():
    content = make_docx([
        "Alex Doe",
        "github.com/alex | linkedin.com/in/alex",
        "Skills",
        "Node.js, Node, JavaScript, JS, React.js, React",
        "Additional resume content with enough text to pass the minimum extraction threshold.",
    ])

    result = parse_resume_v2("resume.docx", content)
    skills = [skill["canonical_name"] for skill in result["skills"]]

    assert result["candidate"]["profile_urls"] == [
        "https://github.com/alex", "https://linkedin.com/in/alex"
    ]
    assert skills.count("node.js") == 1
    assert skills.count("javascript") == 1
    assert skills.count("react") == 1


def test_rejects_unsupported_file_type():
    try:
        parse_resume_v2("resume.txt", b"Some content")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Unsupported file type" in str(exc)


def test_rejects_too_little_extracted_text():
    content = make_docx(["Short text"])
    try:
        parse_resume_v2("resume.docx", content)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Very little text" in str(exc)



def test_skill_provenance_separates_listed_from_demonstrated():
    content = make_docx([
        "Alex Doe",
        "alex@example.com",
        "Skills",
        "Python, Java, Kotlin",
        "Experience",
        "Software Engineer | Example Corp | 2022 - 2024",
        "• Built Python services for internal users.",
    ])
    result = parse_resume_v2("resume.docx", content)
    skills = {item["canonical_name"]: item for item in result["skills"]}
    assert skills["python"]["listed_evidence_ids"]
    assert skills["python"]["demonstrated_evidence_ids"]
    assert skills["java"]["listed_evidence_ids"]
    assert not skills["java"]["demonstrated_evidence_ids"]
    assert skills["java"]["inferred_evidence_ids"] == []


def test_warns_when_bullet_ends_with_suspicious_incomplete_metric():
    content = make_docx([
        "Alex Doe",
        "alex@example.com",
        "Experience",
        "• Improved user engagement by 25",
        "Additional resume content to ensure extraction has sufficient text.",
    ])
    result = parse_resume_v2("resume.docx", content)
    assert any("truncated numeric outcomes" in warning for warning in result["warnings"])
