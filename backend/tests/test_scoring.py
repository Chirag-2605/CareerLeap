from app.scoring import analyze_quality, analyze_job_match

SAMPLE = '''
Alex Doe
alex@example.com | +1 415 555 0199 | https://linkedin.com/in/alex
Professional Summary
Software engineer with experience building scalable backend systems.
Skills
Python, Java, SQL, AWS, Docker, PostgreSQL, React, Git
Experience
Software Engineer, Acme Corp, 2022 - 2024
- Built APIs serving 2 million requests per month.
- Optimized query latency by 35%.
- Automated deployments and reduced release time by 4 hours.
Education
Bachelor of Technology, Example University, 2022
Projects
Created a distributed job processing platform.
'''

def test_quality_score_is_bounded_and_explainable():
    result = analyze_quality(SAMPLE)
    assert 0 <= result["score"] <= 100
    assert sum(x["possible"] for x in result["breakdown"]) == 100
    assert sum(x["earned"] for x in result["breakdown"]) == result["score"]
    assert result["version"] == "quality-v1"

def test_job_match_returns_separate_score():
    result = analyze_job_match(SAMPLE, "We need a Python Java backend engineer with AWS, SQL, Docker and Kubernetes.")
    assert 0 <= result["score"] <= 100
    assert "python" in result["matched_skills"]
    assert "kubernetes" in result["missing_skills"]

def test_quality_deductions_have_recommendations():
    result = analyze_quality("A short resume without sections or contact information.")
    assert result["findings"]
    assert all(f["recommendation"] for f in result["findings"])
