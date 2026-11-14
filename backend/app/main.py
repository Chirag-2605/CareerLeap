from __future__ import annotations

from typing import Optional
from fastapi import FastAPI, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .auth import require_user
from .config import settings
from .parser_v2 import parse_resume_v2
from .analysis_v4 import analyze_quality_v4, analyze_job_match_v4
from .suggestion_design import design_suggestions
from .credits import (
    router as credits_router,
    reserve_scan_credit,
    commit_scan_credit,
    release_scan_credit,
)

app = FastAPI(
    title="Resume Analyzer API",
    version="1.1.0",
    description="Single evidence-based V4 resume analyzer with post-analysis suggestions. Resume content is not persisted."
)

app.include_router(credits_router)

origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:8081"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "resume-analyzer-api"}


@app.post("/api/v1/analyze")
async def analyze(
    file: UploadFile = File(...),
    job_description: Optional[str] = Form(default=None),
    user: dict = Depends(require_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Run the single production V4 analyzer and then design its suggestions."""
    filename = file.filename or "resume"
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=415, detail="Please upload a PDF or DOCX file.")

    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="File is too large. Maximum size is {0} MB.".format(settings.max_upload_mb),
        )

    reservation_id = None
    if settings.credits_enabled:
        if not idempotency_key:
            raise HTTPException(status_code=400, detail="Idempotency-Key header is required when credits are enabled.")
        reservation_id = reserve_scan_credit(user["uid"], idempotency_key)

    try:
        parsed = parse_resume_v2(filename, content)
        quality = analyze_quality_v4(parsed)
        job_match = (
            analyze_job_match_v4(parsed, job_description)
            if job_description and job_description.strip()
            else None
        )

        # Rebuild a section-aware text view from normalized parser output.
        # The raw evidence list has no section headings; feeding it directly
        # to suggestion design caused every line to look like header content.
        suggestion_lines = []
        for section in parsed.get("sections", []):
            heading = section.get("heading") or section.get("type") or "Other"
            suggestion_lines.append(str(heading))
            for item in section.get("items", []):
                text = str(item.get("text", "")).strip()
                if text:
                    suggestion_lines.append(("• " if item.get("kind") == "bullet" else "") + text)
        resume_text = "\n".join(suggestion_lines)
        suggestion_plan = design_suggestions(resume_text, quality, job_match)
        quality["suggestion_design"] = suggestion_plan
        quality["top_suggestions"] = [item["title"] for item in suggestion_plan["items"][:5]]

        # Keep the existing mobile presentation contract while exposing V4's
        # more explicit required/preferred skill evidence.
        if job_match is not None:
            job_match["missing_skills"] = sorted(
                set(job_match.get("missing_required_skills", []))
                | set(job_match.get("missing_preferred_skills", []))
            )
            job_match["matched_skills"] = sorted(
                set(job_match.get("matched_required_skills", []))
                | set(job_match.get("matched_preferred_skills", []))
            )

        document = parsed.get("document", {})
        if reservation_id:
            commit_scan_credit(user["uid"], reservation_id)
        return {
            "quality": quality,
            "job_match": job_match,
            "document": {
                "file_type": document.get("file_type"),
                "pages": document.get("pages"),
                "word_count": document.get("word_count", 0),
            },
            "privacy": {
                "stored": False,
                "message": "This scan is processed in memory and is not saved to scan history.",
            },
        }
    except ValueError as exc:
        if reservation_id:
            release_scan_credit(user["uid"], reservation_id)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        if reservation_id:
            release_scan_credit(user["uid"], reservation_id)
        raise
    finally:
        await file.close()
