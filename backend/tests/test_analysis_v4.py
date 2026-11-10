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
    assert weak["version"] == "quality-v4.5"
    assert strong["version"] == "quality-v4.5"
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
    # V4.4 separates the baseline language requirement from preferred examples.
    assert {"programming_language", "sql", "relational databases", "git", "rest api"} <= required
    assert {"preferred_programming_language", "spring boot", "aws", "build_tool", "distributed systems", "concurrency"} <= preferred
    programming_language = next(item for item in parsed if item["name"] == "programming_language")
    preferred_language = next(item for item in parsed if item["name"] == "preferred_programming_language")
    database = next(item for item in parsed if item["name"] == "relational databases")
    build_tool = next(item for item in parsed if item["name"] == "build_tool")
    assert programming_language["match_rule"] == "any_language"
    assert preferred_language["alternatives"] == ["java", "kotlin"]
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
    # Collapsed Markdown must preserve the generic-language / preferred-example split.
    assert "programming_language" in required
    assert "preferred_programming_language" in preferred
    assert "spring boot" in preferred
    grouped = next(item for item in parsed if item["name"] == "programming_language")
    assert grouped["match_rule"] == "any_language"


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


def dakshta_resume():
    return parse_lines([
        "Sample Candidate", "candidate@example.com", "Education",
        "Motilal Nehru National Institute of Technology, Allahabad",
        "Bachelor of Technology, Computer Science and Engineering, CPI 8.46 / 10",
        "Experience", "Example Corp | Jan 2026 - June 2026",
        "Software Development Engineer in Test (SDET) Intern",
        "Project 1: Centralized Server Management Dashboard",
        "• Engineered and deployed a centralized server management dashboard using React, Python, and AWS to monitor 22 lab servers across 6 QA sub-teams, eliminating 3-4 hours/week of manual status checks.",
        "• Enabled browser-based SSH access using WebSocket and AWS SSM, allowing remote server interaction and reboot operations directly from the dashboard, with 105 SSH sessions in 9 days.",
        "• Streamlined server compliance monitoring and remediation, including safe reboot handling, while reducing offline-server detection from hours/days to under 5 minutes through automated Slack notifications.",
        "• Simplified server onboarding using AWS SSM Parameter Store, enabling registration without code changes or application redeployment and reducing engineer intervention for new server setup.",
        "Project 2: AI-Powered Log Analyzer and Root Cause Analyzer",
        "• Engineered an automated log collection and failure diagnosis system using Python, Amazon Bedrock, and LLM workflows, eliminating manual reproduction and log collection for test failures.",
        "• Designed a two-pass LLM-based failure analysis workflow to classify failures and identify root causes with evidence, confidence scores, and visual observations, validating 9/9 P0 scenarios.",
        "• Reduced failure diagnosis time from 1-2 hours to 2-3 minutes through automated log analysis and root-cause identification, significantly streamlining failure investigation.",
        "• Optimized device log storage and transfer using gzip compression, achieving approximately 80% reduction in log size before S3 upload.",
        "Example Corp | June 2024 - July 2024",
        "Software Development Engineer in Test (SDET) Intern",
        "• Automated crash tracking across 100-200 weekly Kibana records, creating Jira tickets for new crashes and updating existing tickets with crash metrics, eliminating 1-2 days of manual QA effort per week.",
        "• Built a scheduled reporting workflow that updated Jira tickets every 7 days and generated HTML email reports for stakeholders, processing approximately 20-25 new Jira tickets per week.",
        "Projects", "NovaChat", "MERN stack application for real-time chat, voice, and video communication",
        "• Developed a real-time communication platform using React, Node.js, Express.js, and MongoDB, implementing JWT authentication with OTP verification and persistent message history.",
        "• Implemented real-time messaging with Socket.io and peer-to-peer voice/video communication using WebRTC, supporting individual and group conversations.",
        "Blog-zone", "MERN stack blogging platform for content creation, management, and sharing",
        "• Built secure user authentication and registration using Google OAuth, with role-based access for managing platform content.",
        "• Developed an admin dashboard for content moderation and post management, implementing like/dislike functionality and Dark Mode for improved user experience.",
        "Technical Skills",
        "Languages: C++, C, Python, SQL",
        "Frontend: ReactJS, HTML, CSS, Bootstrap, Tailwind CSS",
        "Backend: Node.js, Express.js, REST APIs, WebSockets",
        "Databases: MySQL, MongoDB, DynamoDB",
        "Cloud & AWS: AWS Lambda, AWS SSM, Amazon S3, Amazon Bedrock",
        "Tools: Git, GitHub, VS Code, Jira, Kibana",
        "Engineering Practices: SDLC, Agile, CI/CD, Code Reviews, Automated Testing, Technical Documentation, Code Quality",
        "Core: Data Structures and Algorithms, Object-Oriented Programming, DBMS, Operating Systems, System Design, Test Automation",
    ])


def test_quality_v44_does_not_score_role_titles_or_project_headings_as_weak_bullets():
    parsed = dakshta_resume()
    result = analyze_quality_v4(parsed)
    actual_bullet_ids = {
        evidence_id
        for section in parsed["sections"]
        for item in section["items"]
        if item.get("kind") == "bullet"
        for evidence_id in item.get("evidence_ids", [])
    }
    non_bullet_ids = {
        evidence_id
        for section in parsed["sections"]
        for item in section["items"]
        if item.get("kind") != "bullet"
        for evidence_id in item.get("evidence_ids", [])
    }
    weak = next((item for item in result["findings"] if item["code"] == "evidence_quality_weak_bullets"), None)
    weak_ids = set(weak["evidence_ids"]) if weak else set()
    assert result["evidence_summary"]["achievement_bullets"] == len(actual_bullet_ids)
    assert weak_ids <= actual_bullet_ids
    assert not (weak_ids & non_bullet_ids)


def test_v44_dakshta_regression_language_relational_db_sdet_and_real_responsibilities():
    resume = dakshta_resume()
    result = analyze_job_match_v4(resume, JOB_DESCRIPTION_V42)
    matches = {item["skill"]: item for item in result["skill_matches"]}

    # The generic requirement is satisfied by demonstrated Python, while
    # Java/Kotlin remain preferred examples and are not fabricated.
    assert matches["programming_language"]["status"] == "demonstrated"
    assert "python" in matches["programming_language"]["matched_alternatives"]
    assert "preferred_programming_language" in result["missing_preferred_skills"]

    # MySQL is a relational database, but it does not prove schema design,
    # indexing, joins, or query optimization.
    assert matches["relational databases"]["status"] == "listed"
    assert "mysql" in matches["relational databases"]["matched_alternatives"]
    assert "sql" in result["matched_required_skills"]
    assert {"database design", "indexing", "query optimization", "http"} <= set(result["missing_required_skills"])

    # SDET is a software-engineering family specialization, not an unrelated role.
    assert result["role_alignment"]["candidate_family"] == "software_engineering"
    assert result["role_alignment"]["assessment"] == "aligned"
    assert result["role_alignment"]["candidate_specialization"] == "quality_engineering"
    assert result["seniority_alignment"]["assessment"] == "aligned"

    # Duties must retrieve evidence from actual experience/project bullets.
    assert result["assessment_coverage"]["responsibility_statements"] == 8
    assert result["assessment_coverage"]["responsibility_matches"] >= 3
    assert result["breakdown"][2]["earned"] > 0
    assert all(item["evidence_ids"] for item in result["responsibility_matches"])
    assert all(item["evidence_status"] == "demonstrated" for item in result["responsibility_matches"])
    assert result["responsibility_listed_evidence"]


def test_v44_does_not_treat_related_frameworks_or_api_terms_as_equivalent_skills():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills",
        "Python, Node.js, Express.js, REST APIs",
        "Experience", "Software Development Engineer in Test Intern",
        "• Developed backend services using Node.js and Express.js.",
    ])
    result = analyze_job_match_v4(
        resume,
        "Required Qualifications:\n- HTTP protocols\n"
        "Preferred Qualifications:\n- Spring Boot",
    )
    assert result["missing_required_skills"] == ["http"]
    assert result["missing_preferred_skills"] == ["spring boot"]


def test_v44_generic_language_requirement_respects_preferred_section_context():
    from app.analysis_v4 import _extract_jd_skills

    parsed = _extract_jd_skills(
        "Preferred Qualifications:\n"
        "- Proficiency in at least one programming language, preferably Java or Kotlin."
    )
    generic = next(item for item in parsed if item["name"] == "programming_language")
    examples = next(item for item in parsed if item["name"] == "preferred_programming_language")
    assert generic["classification"] == "preferred"
    assert examples["classification"] == "preferred"


# ---------------------------------------------------------------------------
# V4.5 diagnostic regression matrix.
# These tests intentionally cover both positive evidence and hard negatives.
# A retrieved excerpt is not a match unless it supports the actual JD concept.
# ---------------------------------------------------------------------------

def _responsibility_result(resume, duty):
    return analyze_job_match_v4(
        resume,
        "Entry Level Software Engineer\nResponsibilities:\n- " + duty,
    )


def test_v45_gzip_and_object_storage_do_not_prove_sql_query_optimization():
    from app.analysis_v4 import _responsibility_similarity

    duty = "Work with relational databases and write optimized SQL queries."
    evidence = (
        "Optimized device log storage and transfer using gzip compression, "
        "achieving 80% reduction in log size before S3 upload."
    )
    assert _responsibility_similarity(duty, evidence) == 0.0


def test_v45_server_monitoring_dashboard_is_not_automatically_backend_development():
    from app.analysis_v4 import _responsibility_concepts

    evidence = (
        "Engineered a centralized server management dashboard using React, "
        "Python, and AWS to monitor 22 lab servers across QA teams."
    )
    assert "backend_development" not in _responsibility_concepts(evidence)


def test_v45_team_count_and_qa_audience_do_not_prove_collaboration():
    from app.analysis_v4 import _responsibility_concepts

    evidence = (
        "Built a dashboard to monitor 22 lab servers across 6 QA sub-teams."
    )
    assert "collaboration" not in _responsibility_concepts(evidence)


def test_v45_explicit_cross_functional_work_does_support_collaboration():
    from app.analysis_v4 import _responsibility_concepts

    evidence = (
        "Collaborated with product managers, QA engineers, and developers "
        "to agree on release criteria and resolve integration issues."
    )
    assert "collaboration" in _responsibility_concepts(evidence)


def test_v45_sql_and_mysql_listings_are_not_demonstrated_database_optimization():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills",
        "SQL, MySQL, MongoDB",
        "Experience", "Software Engineer Intern",
        "• Optimized device log compression before uploading files to S3.",
    ])
    result = _responsibility_result(
        resume, "Design database indexes and optimize SQL query execution."
    )
    assert not result["responsibility_matches"]


def test_v45_explicit_index_and_query_tuning_bullet_supports_database_optimization():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills", "SQL, PostgreSQL",
        "Experience", "Software Engineer Intern",
        "• Improved PostgreSQL query performance by adding indexes and rewriting slow SQL joins.",
    ])
    result = _responsibility_result(
        resume, "Design database indexes and optimize SQL query execution."
    )
    assert result["responsibility_matches"]
    match = result["responsibility_matches"][0]
    assert match["evidence_status"] == "demonstrated"
    assert "database_optimization" in match["matched_concepts"]


def test_v45_backend_api_project_out_ranks_frontend_dashboard_for_backend_duty():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills",
        "React, Node.js, Express.js, REST APIs",
        "Experience", "Software Engineer Intern",
        "• Built a React dashboard for QA users to monitor application status.",
        "Projects",
        "• Developed backend services and REST APIs using Node.js and Express.js, with MongoDB persistence.",
    ])
    result = _responsibility_result(
        resume, "Develop backend services and RESTful APIs."
    )
    assert result["responsibility_matches"]
    assert "Node.js" in result["responsibility_matches"][0]["resume_excerpt"]


def test_v45_displayed_primary_excerpt_has_primary_evidence_ids():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Experience", "Software Engineer Intern",
        "• Developed backend services using Node.js and Express.js.",
        "• Built a React dashboard for internal users.",
    ])
    result = _responsibility_result(resume, "Develop backend services and REST APIs.")
    match = result["responsibility_matches"][0]
    primary_text = match["resume_excerpt"]
    primary_ids = {
        evidence_id
        for section in resume["sections"]
        for item in section["items"]
        if item["text"] == primary_text
        for evidence_id in item["evidence_ids"]
    }
    assert primary_ids
    assert primary_ids <= set(match["evidence_ids"])


def test_v45_skills_list_code_quality_does_not_count_as_written_maintainable_code():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills",
        "Code Reviews, Code Quality, Java, Kotlin",
        "Experience", "Software Engineer Intern",
        "• Monitored application health dashboards and triaged service alerts.",
    ])
    result = _responsibility_result(
        resume, "Write clean, efficient, and maintainable code using Java and Kotlin."
    )
    assert not result["responsibility_matches"]


def test_v45_skills_list_testing_does_not_count_as_demonstrated_testing_duty():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills",
        "Unit Testing, Integration Testing, Automated Testing",
        "Experience", "Software Engineer Intern",
        "• Built a React dashboard for internal users.",
    ])
    result = _responsibility_result(
        resume, "Design and execute unit and integration tests."
    )
    assert not result["responsibility_matches"]


def test_v45_actual_test_execution_is_retrieved_for_testing_duty():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Experience", "QA Automation Intern",
        "• Wrote and executed 120 integration tests for payment APIs, catching 18 regressions before release.",
    ])
    result = _responsibility_result(
        resume, "Design and execute unit and integration tests."
    )
    assert result["responsibility_matches"]
    assert result["responsibility_matches"][0]["evidence_status"] == "demonstrated"


def test_v45_actual_failure_diagnosis_supports_debugging_and_troubleshooting():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Experience", "SDET Intern",
        "• Diagnosed production failures by analyzing application logs and tracing root causes, reducing mean triage time by 60%.",
    ])
    result = _responsibility_result(
        resume, "Debug software failures and troubleshoot production issues."
    )
    assert result["responsibility_matches"]
    assert "diagnostics" in result["responsibility_matches"][0]["matched_concepts"]


def test_v45_s3_storage_optimization_does_not_match_relational_database_duty():
    from app.analysis_v4 import _responsibility_similarity

    assert _responsibility_similarity(
        "Work with relational databases and write optimized SQL queries.",
        "Reduced S3 object storage size by 80% using gzip compression.",
    ) == 0.0


def test_v45_rest_api_mention_does_not_prove_http_protocol_expertise():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills", "REST APIs",
        "Experience", "Software Engineer Intern",
        "• Built REST APIs for an internal application.",
    ])
    result = analyze_job_match_v4(
        resume, "Required Qualifications:\n- HTTP protocol expertise"
    )
    assert "http" in result["missing_required_skills"]


def test_v45_express_does_not_satisfy_spring_boot_requirement():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills", "Node.js, Express.js",
        "Experience", "Software Engineer Intern",
        "• Developed backend services using Node.js and Express.js.",
    ])
    result = analyze_job_match_v4(
        resume, "Entry Level Backend Software Engineer\nRequired Qualifications:\n- Spring Boot"
    )
    assert "spring boot" in result["missing_required_skills"]


def test_v45_any_programming_language_phrase_is_recognized_as_generic_requirement():
    from app.analysis_v4 import _extract_jd_skills

    requirements = _extract_jd_skills(
        "Required Qualifications:\n- Proficiency in any programming language."
    )
    generic = [item for item in requirements if item["name"] == "programming_language"]
    assert len(generic) == 1
    assert generic[0]["match_rule"] == "any_language"


def test_v45_generic_language_does_not_turn_java_kotlin_examples_into_hard_requirements():
    from app.analysis_v4 import _extract_jd_skills

    requirements = _extract_jd_skills(
        "Required Qualifications:\n"
        "- Proficiency in at least one programming language, preferably Java or Kotlin."
    )
    names = {item["name"] for item in requirements}
    assert "programming_language" in names
    assert "preferred_programming_language" in names
    assert "java" not in names
    assert "kotlin" not in names


def test_v45_relational_database_alternatives_are_one_requirement_group():
    from app.analysis_v4 import _extract_jd_skills

    requirements = _extract_jd_skills(
        "Required Qualifications:\n"
        "- Working knowledge of SQL and relational databases such as PostgreSQL or MySQL."
    )
    groups = [item for item in requirements if item["name"] == "relational databases"]
    assert len(groups) == 1
    assert groups[0]["alternatives"] == ["postgresql", "mysql"]


def test_v45_requirement_parser_keeps_join_and_indexing_as_distinct_evidence_gaps():
    from app.analysis_v4 import _extract_jd_skills

    requirements = _extract_jd_skills(
        "Required Qualifications:\n"
        "- Understanding of database design, indexing, joins, and query optimization."
    )
    names = {item["name"] for item in requirements}
    assert {"database design", "indexing", "joins", "query optimization"} <= names


def test_v45_preferred_language_examples_remain_preferred_in_preferred_section():
    from app.analysis_v4 import _extract_jd_skills

    requirements = _extract_jd_skills(
        "Preferred Qualifications:\n"
        "- Proficiency in at least one programming language, preferably Java or Kotlin."
    )
    assert all(
        item["classification"] == "preferred"
        for item in requirements
        if item["name"] in {"programming_language", "preferred_programming_language"}
    )


def test_v45_role_family_recognizes_sdet_without_promoting_it_to_software_developer_specialty():
    result = analyze_job_match_v4(
        dakshta_resume(),
        "Entry Level Software Engineer\nRequired Qualifications:\n- Python",
    )
    assert result["role_alignment"]["candidate_family"] == "software_engineering"
    assert result["role_alignment"]["candidate_specialization"] == "quality_engineering"


def test_v45_internship_is_not_penalized_for_entry_level_zero_to_two_year_role():
    result = analyze_job_match_v4(
        dakshta_resume(),
        "Entry Level Software Engineer\nExperience: 0-2 Years\n"
        "Required Qualifications:\n- Python",
    )
    assert result["seniority_alignment"]["assessment"] == "aligned"


def test_v45_qualification_bullets_do_not_leak_into_responsibility_matching():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills", "Python, Java",
        "Experience", "Software Engineer Intern",
        "• Built a React dashboard for internal users.",
    ])
    result = analyze_job_match_v4(
        resume,
        "Required Qualifications:\n- Python\n- Java\n"
        "Preferred Qualifications:\n- AWS",
    )
    assert result["assessment_coverage"]["responsibility_statements"] == 0
    assert result["responsibility_matches"] == []


def test_v45_responsibility_count_excludes_listed_only_candidates():
    resume = parse_lines([
        "Alex Doe", "alex@example.com", "Skills",
        "Git, Code Reviews, Technical Documentation, Automated Testing",
        "Experience", "Software Engineer Intern",
        "• Built a React dashboard for internal users.",
    ])
    result = analyze_job_match_v4(
        resume,
        "Responsibilities:\n"
        "- Follow software engineering best practices, including version control, testing, and documentation.",
    )
    assert result["assessment_coverage"]["responsibility_matches"] == 0
    assert result["responsibility_matches"] == []
    assert result["responsibility_listed_evidence"]


def test_v45_real_resume_backend_responsibility_prefers_project_over_monitoring_bullet():
    result = analyze_job_match_v4(
        dakshta_resume(),
        "Responsibilities:\n- Develop backend services, RESTful APIs, and application components.",
    )
    match = result["responsibility_matches"][0]
    assert "Node.js" in match["resume_excerpt"] or "Express.js" in match["resume_excerpt"]


def test_v45_real_resume_database_responsibility_does_not_use_gzip_bullet_as_direct_evidence():
    result = analyze_job_match_v4(
        dakshta_resume(),
        "Responsibilities:\n- Work with relational databases and write optimized SQL queries.",
    )
    if result["responsibility_matches"]:
        match = result["responsibility_matches"][0]
        assert "gzip" not in match["resume_excerpt"].lower()
        assert match["evidence_type"] != "direct"


def test_v45_real_resume_collaboration_responsibility_requires_explicit_collaboration_evidence():
    result = analyze_job_match_v4(
        dakshta_resume(),
        "Responsibilities:\n- Collaborate with product managers, QA engineers, and other developers.",
    )
    assert result["responsibility_matches"] == []


def test_v45_real_resume_quality_best_practices_uses_test_validation_not_skills_list():
    result = analyze_job_match_v4(
        dakshta_resume(),
        "Responsibilities:\n"
        "- Follow software engineering best practices, including version control, testing, and documentation.",
    )
    assert result["responsibility_matches"]
    match = result["responsibility_matches"][0]
    assert match["evidence_status"] == "demonstrated"
    assert "validating 9/9 p0 scenarios" in match["resume_excerpt"].lower()
    assert "Engineering Practices:" not in match["resume_excerpt"]

def test_v45_test_automation_skill_split_across_pdf_lines_is_reconstructed():
    # A continuation line in a skills section must not become a separate skill.
    parsed = parse_lines([
        "Alex Doe", "alex@example.com", "Technical Skills",
        "Core: Data Structures and Algorithms, Object-Oriented Programming, DBMS, Test",
        "Automation",
    ])
    names = {item["canonical_name"] for item in parsed["skills"]}
    assert "test automation" in names
