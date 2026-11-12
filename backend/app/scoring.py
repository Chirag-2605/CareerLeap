from __future__ import annotations
import re
from collections import Counter

VERSION = "quality-v2"
MATCH_VERSION = "match-v2"

SECTION_ALIASES = {
    "summary": ["summary", "professional summary", "profile", "objective", "career objective"],
    "experience": ["experience", "work experience", "professional experience", "employment", "internship"],
    "education": ["education", "academic background", "qualifications"],
    "skills": ["skills", "my skills", "technical skills", "key skills", "core competencies", "competencies", "skill set"],
    "projects": ["projects", "personal projects", "academic projects"],
    "certifications": ["certifications", "certificates", "licenses"],
}
SKILL_TERMS = [
    "python", "java", "javascript", "typescript", "react", "react native", "node.js", "node",
    "sql", "postgresql", "mysql", "mongodb", "aws", "azure", "gcp", "docker", "kubernetes",
    "spring boot", "fastapi", "django", "flask", "git", "linux", "html", "css", "machine learning",
    "deep learning", "data analysis", "pandas", "numpy", "tensorflow", "pytorch", "rest api",
    "microservices", "terraform", "redis", "kafka", "excel", "power bi", "tableau",
]
SYNONYMS = {
    "js": "javascript", "ts": "typescript", "postgres": "postgresql",
    "k8s": "kubernetes", "ml": "machine learning", "restful api": "rest api",
    "amazon web services": "aws",
}
ACTION_VERBS = {
    "built", "developed", "designed", "implemented", "created", "led", "improved",
    "optimized", "automated", "delivered", "launched", "reduced", "increased",
    "integrated", "managed", "analyzed", "migrated", "deployed", "engineered",
}
METRIC_RE = re.compile(r"(?<!\w)(?:\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?\s?(?:x|×)|[$₹€]\s?\d[\d,.]*|\d+\+?\s?(?:users|customers|requests|ms|seconds|hours|days|teams|projects|records|employees|clients))(?!\w)", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}\b")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
BULLET_RE = re.compile(r"^\s*(?:[•●▪◦‣*-]|\d+[.)])\s+", re.M)

def _norm(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#. ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for old, new in SYNONYMS.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    return text

def _has_any(text: str, terms: list[str]) -> bool:
    n = _norm(text)
    return any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", n) for t in terms)

def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]

def _section_presence(text: str) -> dict:
    nlines = [_norm(line).strip(": ") for line in _lines(text)]
    found = {}
    for key, aliases in SECTION_ALIASES.items():
        found[key] = any(line in aliases or any(line.startswith(a + " ") for a in aliases) for line in nlines)
    return found

def _finding(code, title, deduction, severity, evidence, recommendation):
    return {"code": code, "title": title, "deduction": deduction, "severity": severity,
            "evidence": evidence[:220] if evidence else None, "recommendation": recommendation}



JD_GENERIC_TERMS = {
    "requirement", "requirements", "design", "designing", "troubleshoot",
    "troubleshooting", "knowledge", "analyze", "analyzing", "analysis",
    "write", "writing", "communication", "ability", "experience", "work",
    "working", "team", "responsibility", "responsibilities", "skill", "skills",
    "strong", "good", "understanding", "develop", "development", "support",
    "maintain", "maintenance", "related", "including", "various", "using",
    "looking", "reliable", "code", "test", "testing", "engineer", "developer",
}


def _section_line_map(text: str) -> dict:
    """Map extracted resume section names to their 1-based source line numbers."""
    current = "Header"
    result = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        normalized = _norm(line).strip(": ")
        matched = next((key for key, aliases in SECTION_ALIASES.items()
                        if normalized in aliases), None)
        if matched:
            current = matched.title()
        result.setdefault(current, []).append({"line": number, "text": line})
    return result


def _find_resume_lines(text: str, terms: list[str], limit: int = 2) -> list:
    matches = []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        normalized = _norm(stripped)
        if any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized)
               for term in terms):
            matches.append({"line": number, "text": stripped[:260]})
    return matches[:limit]


def _actionable_job_suggestions(resume_text: str, missing_skills: list[str],
                                missing_terms: list[str]) -> list[dict]:
    sections = _section_line_map(resume_text)
    skills_section = sections.get("Skills", [])
    experience_section = sections.get("Experience", [])
    project_section = sections.get("Projects", [])
    suggestions = []

    for skill in missing_skills[:8]:
        suggestions.append({
            "code": "add_missing_skill_" + re.sub(r"[^a-z0-9]+", "_", skill).strip("_"),
            "priority": "high",
            "title": f"Java is not evidenced in your resume" if skill == "java" else f"{skill.title()} is not evidenced in your resume",
            "what_is_missing": f"The job description asks for {skill}, but the resume text contains no direct evidence of it.",
            "where_to_edit": "Skills section" if skills_section else "Add a Skills section",
            "target_line": ({"line": skills_section[0]["line"], "text": skills_section[0]["text"]}
                           if skills_section else None),
            "suggested_change": f"If you have genuinely used {skill}, list it under the relevant technical skills category. If you used it in a project or role, add it to that specific bullet instead of listing it without evidence.",
            "safe_wording": f"Skills: ... | {skill.title()} | ... (include only if accurate)",
            "resume_evidence": _find_resume_lines(resume_text, [skill]),
        })

    generic_to_ignore = JD_GENERIC_TERMS | {"java", "javascript", "engineer", "developer"}
    useful_terms = [term for term in missing_terms if term not in generic_to_ignore]
    if useful_terms:
        target = experience_section or project_section or skills_section
        section_name = "Experience" if experience_section else "Projects" if project_section else "Skills"
        target_line = next((item for item in target if len(item["text"].split()) >= 7), None)
        suggestions.append({
            "code": "jd_language_gaps",
            "priority": "medium",
            "title": "Mirror specific job language where your experience supports it",
            "what_is_missing": "These more specific terms from the job description were not found: " + ", ".join(useful_terms[:6]) + ".",
            "where_to_edit": f"{section_name} section" if target else "Relevant Experience or Projects bullet",
            "target_line": target_line,
            "suggested_change": "Choose the closest existing bullet and add only the missing technical concept or responsibility if it accurately describes what you did. Do not paste a keyword list into the resume.",
            "safe_wording": "Use the employer's exact term in a sentence describing your own action, the technical method, and the outcome. Keep the original facts and metrics unchanged.",
            "resume_evidence": [],
        })
    return suggestions


def _quality_actionable_suggestions(text: str, sections_present: dict) -> list[dict]:
    sections = _section_line_map(text)
    suggestions = []
    if not sections_present.get("summary"):
        experience_heading = next((item for item in sections.get("Experience", [])
                                   if _norm(item["text"]).strip(": ") in SECTION_ALIASES["experience"]), None)
        suggestions.append({
            "code": "add_summary_section",
            "priority": "low",
            "title": "Add an optional, targeted professional summary",
            "what_is_missing": "No clearly labelled summary was detected. This is optional; it is not a universal ATS requirement.",
            "where_to_edit": "Below your contact details and before Experience",
            "target_line": experience_heading,
            "suggested_change": "Add 2–3 concise lines that state your target role, strongest relevant technical strengths, and one or two substantiated areas of experience. Avoid generic claims such as 'hard-working' or 'team player'.",
            "safe_wording": "[Target role] with hands-on experience in [relevant technologies] through [internship/project]. Built or improved [specific system or outcome], with a focus on [role-relevant strength]. Replace every bracket with a fact already supported by your resume.",
        })

    weak_bullets = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if len(line.split()) < 6 or not BULLET_RE.match(line):
            continue
        clean = BULLET_RE.sub("", line).strip()
        first = re.findall(r"[a-z]+", clean.lower())[:1]
        vague = bool(first and first[0] in {"worked", "helped", "assisted", "involved", "responsible", "participated"})
        has_metric = bool(METRIC_RE.search(clean))
        if vague or (len(clean.split()) < 12 and not has_metric):
            weak_bullets.append({"line": number, "text": clean[:260], "vague": vague, "metric": has_metric})
    for item in weak_bullets[:3]:
        suggestions.append({
            "code": f"rewrite_bullet_line_{item['line']}",
            "priority": "medium",
            "title": f"Make the bullet on line {item['line']} more specific",
            "what_is_missing": ("The bullet starts with a vague phrase and does not make your individual contribution clear."
                                if item["vague"] else "The bullet describes work, but gives limited detail about the method, scope, or outcome."),
            "where_to_edit": "Keep this bullet in its current section",
            "target_line": {"line": item["line"], "text": item["text"]},
            "suggested_change": "Rewrite this same bullet using: strong action verb + what you built/changed + how or with which technology + result or scale. Add a metric only when you can verify it.",
            "safe_wording": "[Action verb] [specific component or task] using [technology/method], resulting in [verified outcome, scale, or improvement]. Do not invent a number if you do not have one.",
        })
    return suggestions


def analyze_quality(text: str) -> dict:
    lines = _lines(text)
    lower = text.lower()
    sections = _section_presence(text)
    findings = []
    earned = {}

    # Contact: 10
    contact = 0
    if EMAIL_RE.search(text): contact += 4
    else: findings.append(_finding("missing_email", "Email address not found", 4, "high", None, "Add a professional email address in the header."))
    if PHONE_RE.search(text): contact += 3
    else: findings.append(_finding("missing_phone", "Phone number not found", 3, "medium", None, "Add a reachable phone number with country code."))
    if URL_RE.search(text) or "linkedin.com" in lower: contact += 3
    else: findings.append(_finding("missing_profile_link", "No professional profile link found", 3, "low", None, "Add a LinkedIn, portfolio, or GitHub URL if relevant."))
    earned["contact"] = contact

    # Structure: 15
    structure = 0
    for key, points in [("experience", 5), ("education", 4), ("skills", 4), ("summary", 2)]:
        if sections[key]: structure += points
        else:
            findings.append(_finding(f"missing_{key}_section", f"{key.title()} section not detected", points, "high" if key in ("experience","education") else "medium", None,
                                     f"Add a clearly labelled {key} section so recruiters and parsers can find it."))
    earned["structure"] = structure

    # Skills: 15
    detected_skills = [s for s in SKILL_TERMS if re.search(rf"(?<![a-z0-9]){re.escape(s)}(?![a-z0-9])", _norm(text))]
    skills_score = min(15, round(len(detected_skills) * 1.5))
    if not sections["skills"]:
        skills_score = min(skills_score, 6)
    if len(detected_skills) < 5:
        findings.append(_finding("few_skills", "Limited skills evidence detected", max(0, 15-skills_score), "medium",
                                 ", ".join(detected_skills) if detected_skills else None,
                                 "Add a focused skills section containing tools and competencies you can demonstrate."))
    earned["skills"] = skills_score

    # Experience: 25. Score only content inside the Experience section.
    experience_items = _section_line_map(text).get("Experience", [])
    experience_content = [
        item["text"] for item in experience_items
        if item["text"] and _norm(item["text"]).strip(": ") not in SECTION_ALIASES["experience"]
    ]
    experience_bullets = [
        BULLET_RE.sub("", line).strip()
        for line in experience_content if BULLET_RE.match(line)
    ]
    experience_roles = [
        line for line in experience_content
        if not BULLET_RE.match(line) and len(line.split()) >= 2
    ]
    exp_score = 5 if sections["experience"] else 0

    # Role/employer/date context: do not award these points for dates elsewhere.
    has_role_context = any(
        re.search(r"\b(intern|engineer|developer|analyst|manager|designer|consultant|lead)\b", line, re.I)
        for line in experience_roles
    )
    has_experience_date = any(re.search(r"\b(20\d{2}|19\d{2})\b", line) for line in experience_roles)
    if has_role_context:
        exp_score += 2
    if has_experience_date:
        exp_score += 2

    # Reward specific, action-led bullets rather than merely counting every bullet.
    bullet_quality = 0
    for bullet in experience_bullets:
        words = len(bullet.split())
        starts_with_action = bool(re.match(
            r"^(built|developed|designed|implemented|managed|led|created|optimized|automated|delivered|launched|reduced|increased|integrated|analyzed|migrated|deployed|engineered)\b",
            bullet, re.I
        ))
        has_technical_detail = _has_any(bullet, SKILL_TERMS)
        has_outcome = bool(METRIC_RE.search(bullet)) or bool(re.search(
            r"\b(improv(ed|ement)|reduc(ed|tion)|increas(ed|e)|sav(ed|ing)|support(ed)?|serv(ed|ing))\b",
            bullet, re.I
        ))
        bullet_quality += int(starts_with_action) + int(has_technical_detail) + int(words >= 10 or has_outcome)
    exp_score += min(12, bullet_quality)

    # Distinct outcome evidence in this section contributes at most four points.
    exp_metrics = sum(len(METRIC_RE.findall(bullet)) for bullet in experience_bullets)
    exp_score += min(4, exp_metrics * 2)
    exp_score = min(25, exp_score)

    if not sections["experience"]:
        findings.append(_finding("experience_missing", "Experience section is missing or unclear", 5, "high", None, "Add an Experience section with role, organization, dates, and achievement-focused bullets."))
    elif not experience_bullets:
        findings.append(_finding("thin_experience", "Few detailed experience bullets detected", max(0, 20-exp_score), "medium",
                                 experience_roles[0] if experience_roles else None,
                                 "Add 2–4 bullets under each role describing your own contribution, technical approach, and outcome."))
    elif exp_score < 17:
        findings.append(_finding("thin_experience", "Experience bullets need more specific evidence", 25-exp_score, "medium",
                                 experience_bullets[0] if experience_bullets else None,
                                 "Strengthen bullets with your action, the component or task, relevant technologies, and a verified outcome or scope."))
    earned["experience"] = exp_score

    # Impact: 15
    metric_matches = METRIC_RE.findall(text)
    action_count = sum(1 for line in lines if any(re.search(rf"\b{v}\b", line, re.I) for v in ACTION_VERBS))
    impact = min(8, len(metric_matches) * 2) + min(7, action_count)
    impact = min(15, impact)
    if len(metric_matches) < 2:
        findings.append(_finding("few_metrics", "Few measurable outcomes found", max(0, 15-impact), "high",
                                 experience_bullets[0] if experience_bullets else None,
                                 "Where truthful, quantify outcomes: latency reduced, users supported, revenue, accuracy, time saved, or project scale."))
    if action_count < 3:
        findings.append(_finding("weak_action_verbs", "Limited action-led achievement statements", max(0, 7-action_count), "low", None,
                                 "Start bullets with precise verbs such as built, automated, optimized, launched, or improved."))
    earned["impact"] = impact

    # Education: 10
    education = 0
    if sections["education"]:
        education += 5
        if re.search(r"\b(bachelor|b\.?tech|b\.?e\.?|master|m\.?tech|ph\.?d|degree|university|college)\b", text, re.I): education += 3
        if re.search(r"\b(20\d{2}|19\d{2})\b", text): education += 2
    else:
        findings.append(_finding("education_missing", "Education details not detected", 10, "high", None,
                                 "Add your degree, institution, and graduation year (or expected graduation year)."))
    earned["education"] = min(10, education)

    # ATS readability measures extraction and structural parseability, not resume
    # quality or length. A short but cleanly extracted resume can still score well.
    readability = 10
    bullet_count = len(BULLET_RE.findall(text))
    recognized_sections = sum(1 for present in sections.values() if present)
    replacement_chars = text.count("\ufffd")
    nonprintable_chars = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    if len(lines) < 8:
        readability -= 3
        findings.append(_finding("low_line_structure", "Very little line structure was extracted", 3, "medium", None,
                                 "Check whether the PDF/DOCX text was extracted into separate lines. Avoid flattening the resume into one text block."))
    if recognized_sections < 3:
        readability -= 2
        findings.append(_finding("few_recognized_sections", "Few standard resume headings were recognized", 2, "medium", None,
                                 "Use conventional headings such as Experience, Education, Skills, and Projects so parsing systems can identify sections."))
    if bullet_count == 0:
        readability -= 1
        findings.append(_finding("no_bullets", "No bullet formatting detected", 1, "low", None,
                                 "Use simple bullets for experience and project achievements where appropriate."))
    if replacement_chars or nonprintable_chars:
        penalty = min(3, max(1, replacement_chars + nonprintable_chars))
        readability -= penalty
        findings.append(_finding("extraction_characters", "Some characters may not have extracted cleanly", penalty, "medium", None,
                                 "Review the extracted text for replacement symbols or missing characters; check font embedding and PDF export settings."))
    earned["readability"] = max(0, readability)

    total = max(0, min(100, sum(earned.values())))
    # Stable, user-readable category breakdown.
    labels = {
        "contact": ("Contact information", 10), "structure": ("Section structure", 15),
        "skills": ("Skills", 15), "experience": ("Experience", 25),
        "impact": ("Measurable impact", 15), "education": ("Education", 10),
        "readability": ("ATS readability", 10),
    }
    breakdown = [{"key": k, "label": labels[k][0], "earned": earned[k], "possible": labels[k][1],
                  "deducted": labels[k][1]-earned[k]} for k in labels]
    findings.sort(key=lambda f: ({"high":0,"medium":1,"low":2}.get(f["severity"],3), -f["deduction"]))
    suggestions = [f["recommendation"] for f in findings[:6]]
    actionable_suggestions = _quality_actionable_suggestions(text, sections)
    return {
        "score": total, "version": VERSION, "breakdown": breakdown,
        "findings": findings, "top_suggestions": suggestions,
        "actionable_suggestions": actionable_suggestions,
        "detected_skills": detected_skills,
        "summary": _quality_summary(total),
    }

def _quality_summary(score: int) -> str:
    if score >= 85: return "Strong foundation. Focus on tailoring and sharpening measurable outcomes."
    if score >= 70: return "Good foundation, with clear opportunities to improve evidence and presentation."
    if score >= 50: return "Several important sections or signals need strengthening before applying."
    return "The resume needs foundational improvements to structure, evidence, and completeness."

def analyze_job_match(resume_text: str, job_text: str) -> dict:
    if not job_text or len(job_text.strip()) < 40:
        raise ValueError("Please provide a job description with at least 40 characters.")
    resume = _norm(resume_text)
    job = _norm(job_text)
    skills_in_job = [s for s in SKILL_TERMS if re.search(rf"(?<![a-z0-9]){re.escape(s)}(?![a-z0-9])", job)]
    matched = [s for s in skills_in_job if re.search(rf"(?<![a-z0-9]){re.escape(s)}(?![a-z0-9])", resume)]
    missing = [s for s in skills_in_job if s not in matched]
    skill_score = round(60 * len(matched) / max(1, len(skills_in_job))) if skills_in_job else 30
    stop = JD_GENERIC_TERMS | {
        "the", "and", "for", "with", "you", "will", "our", "are", "this", "that",
        "from", "your", "have", "has", "who", "all", "can", "not", "job", "role",
        "team", "work", "years", "year", "looking", "reliable", "code", "test",
        "testing", "engineer", "developer",
    }
    words = [w for w in re.findall(r"[a-z][a-z0-9+#.]{2,}", job) if w not in stop]
    freq = Counter(words)
    important = [w for w, _ in freq.most_common(12)]
    matched_terms = [w for w in important if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", resume)]
    term_score = round(25 * len(matched_terms) / max(1, len(important)))
    # Role alignment must come from an actual resume role title, not from
    # the target title repeating a generic word such as "engineer".
    role_families = {
        "frontend": ("frontend", "front end", "ui developer", "ui engineer"),
        "backend": ("backend", "back end", "server-side developer", "server side developer"),
        "full_stack": ("full stack", "fullstack"),
        "data": ("data analyst", "data scientist", "data engineer", "business intelligence"),
        "machine_learning": ("machine learning engineer", "ml engineer", "ai engineer"),
        "design": ("ux designer", "ui designer", "product designer"),
        "devops": ("devops", "site reliability engineer", "sre", "cloud engineer"),
        "software_engineering": ("software engineer", "software developer", "software intern"),
    }
    def role_family(value: str):
        found = [family for family, aliases in role_families.items()
                 if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", value)
                        for alias in aliases)]
        return found[0] if len(found) == 1 else None

    experience_lines = _section_line_map(resume_text).get("Experience", [])
    role_title_text = " ".join(
        item["text"] for item in experience_lines
        if item["text"] and not BULLET_RE.match(item["text"])
        and len(item["text"].split()) >= 2
    )
    candidate_role = role_family(_norm(role_title_text))
    target_role = role_family(job)
    title_score = 0
    role_assessment = "not_identified"
    if candidate_role and target_role:
        if candidate_role == target_role:
            title_score, role_assessment = 15, "aligned"
        elif candidate_role == "software_engineering" and target_role in {"frontend", "backend", "full_stack"}:
            title_score, role_assessment = 6, "broadly_related"
        elif target_role == "full_stack" and candidate_role in {"frontend", "backend"}:
            title_score, role_assessment = 8, "partially_related"
        else:
            title_score, role_assessment = 0, "different"
    total = min(100, skill_score + term_score + title_score)
    findings = []
    if missing:
        findings.append({"code":"missing_job_skills","title":"Relevant skills not found","severity":"high",
                         "evidence":", ".join(missing[:12]),
                         "recommendation":"If you genuinely have these skills, add them in context in your Skills, Experience, or Projects sections. Do not add skills you cannot support."})
    if matched:
        findings.append({"code":"matched_job_skills","title":"Relevant skills detected","severity":"low",
                         "evidence":", ".join(matched[:12]),
                         "recommendation":"Keep these skills visible and reinforce the most important ones with examples in your experience or projects."})
    missing_terms = [w for w in important if w not in matched_terms]
    if len(matched_terms) < len(important) * 0.5:
        findings.append({"code":"keyword_coverage","title":"Some job-description terminology is missing","severity":"medium",
                         "evidence":", ".join(missing_terms[:8]),
                         "recommendation":"Review the specific missing terms below and add only those that accurately describe your work."})
    actionable_suggestions = _actionable_job_suggestions(resume_text, missing, missing_terms)
    return {
        "score": total, "version": MATCH_VERSION,
        "breakdown": [
            {"key":"skills","label":"Relevant skill coverage","earned":skill_score,"possible":60,"deducted":60-skill_score},
            {"key":"terminology","label":"Job terminology coverage","earned":term_score,"possible":25,"deducted":25-term_score},
            {"key":"role_alignment","label":"Role/title alignment","earned":title_score,"possible":15,"deducted":15-title_score},
        ],
        "matched_skills": matched, "missing_skills": missing, "findings": findings,
        "role_alignment": {
            "candidate_family": candidate_role,
            "target_family": target_role,
            "assessment": role_assessment,
        },
        "actionable_suggestions": actionable_suggestions,
        "summary": (
            f"Matched {len(matched)} of {len(skills_in_job)} skills detected in the job description."
            if skills_in_job else
            "No recognized technical skills were detected in the job description; skill coverage uses a neutral baseline."
        )
    }
