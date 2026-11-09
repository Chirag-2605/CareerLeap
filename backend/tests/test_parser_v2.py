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
    assert result["candidate"]["email"] == "alex@example.com"
    section_types = [section["type"] for section in result["sections"]]
    assert "summary" in section_types
    assert "skills" in section_types
    assert "experience" in section_types
    assert "education" in section_types
    assert "python" in [skill["canonical_name"] for skill in result["skills"]]
    assert result["evidence"]
    evidence_ids = {item["id"] for item in result["evidence"]}
    for section in result["sections"]:
        assert set(section["evidence_ids"]).issubset(evidence_ids)
        for item in section["items"]:
            assert item["evidence_id"] in evidence_ids


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
