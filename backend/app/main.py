from __future__ import annotations

from typing import Optional
from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from .auth import require_user
from .config import settings
from .parser import parse_resume
from .parser_v2 import parse_resume_v2
from .analysis_v2 import analyze_quality_v2, analyze_job_match_v2
from .analysis_v3 import analyze_quality_v3, analyze_job_match_v3
from .analysis_v4 import analyze_quality_v4, analyze_job_match_v4
from .scoring import analyze_quality, analyze_job_match
from .suggestion_design import design_suggestions

app = FastAPI(
    title="Resume Analyzer API",
    version="1.1.0",
    description="Explainable resume quality and job-match analysis. Resume content is not persisted."
)

origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:8081"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "resume-analyzer-api"}

@app.post("/api/v1/analyze")
async def analyze(
    file: UploadFile = File(...),
    job_description: Optional[str] = Form(default=None),
    user: dict = Depends(require_user),
):
    filename = file.filename or "resume"
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=415, detail="Please upload a PDF or DOCX file.")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File is too large. Maximum size is {settings.max_upload_mb} MB.")
    try:
        text, meta = parse_resume(filename, content)
        quality = analyze_quality(text)
        job_match = analyze_job_match(text, job_description) if job_description and job_description.strip() else None
        # Suggestions are designed only after scoring/matching has completed.
        # The layer adds coaching; it does not change analysis scores or persist resume data.
        quality["suggestion_design"] = design_suggestions(text, quality, job_match)
        # Deliberately do not persist resume text, file bytes, or scan result.
        return {
            "quality": quality,
            "job_match": job_match,
            "document": {"file_type": meta["file_type"], "pages": meta["pages"], "word_count": len(text.split())},
            "privacy": {"stored": False, "message": "This scan is not saved to scan history."}
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        await file.close()

@app.post("/api/v2/parse")
async def parse_v2(
    file: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    """Extract a normalized, evidence-linked resume structure without scoring."""
    filename = file.filename or "resume"
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=415, detail="Please upload a PDF or DOCX file.")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="File is too large. Maximum size is {0} MB.".format(settings.max_upload_mb),
        )
    try:
        parsed = parse_resume_v2(filename, content)
        return {
            "resume": parsed,
            "privacy": {
                "stored": False,
                "message": "This parse is processed in memory and is not saved."
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        await file.close()


@app.post("/api/v2/analyze")
async def analyze_v2(
    file: UploadFile = File(...),
    job_description: Optional[str] = Form(default=None),
    user: dict = Depends(require_user),
):
    """Run evidence-linked V2 resume quality and optional job-match analysis."""
    filename = file.filename or "resume"
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=415, detail="Please upload a PDF or DOCX file.")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="File is too large. Maximum size is {0} MB.".format(settings.max_upload_mb),
        )
    try:
        parsed = parse_resume_v2(filename, content)
        quality = analyze_quality_v2(parsed)
        job_match = (
            analyze_job_match_v2(parsed, job_description)
            if job_description and job_description.strip()
            else None
        )
        return {
            "quality": quality,
            "job_match": job_match,
            "resume": parsed,
            "privacy": {
                "stored": False,
                "message": "This analysis is processed in memory and is not saved.",
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        await file.close()


@app.post("/api/v3/analyze")
async def analyze_v3(
    file: UploadFile = File(...),
    job_description: Optional[str] = Form(default=None),
    user: dict = Depends(require_user),
):
    """Run the evidence-aware V3 analysis while preserving V1 and V2 contracts."""
    filename = file.filename or "resume"
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=415, detail="Please upload a PDF or DOCX file.")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="File is too large. Maximum size is {0} MB.".format(settings.max_upload_mb),
        )
    try:
        parsed = parse_resume_v2(filename, content)
        quality = analyze_quality_v3(parsed)
        job_match = (
            analyze_job_match_v3(parsed, job_description)
            if job_description and job_description.strip()
            else None
        )
        return {
            "quality": quality,
            "job_match": job_match,
            "resume": parsed,
            "privacy": {
                "stored": False,
                "message": "This analysis is processed in memory and is not saved.",
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        await file.close()


@app.post("/api/v4/analyze")
async def analyze_v4(
    file: UploadFile = File(...),
    job_description: Optional[str] = Form(default=None),
    user: dict = Depends(require_user),
):
    """Run the fresh content-first V4 analysis; V1-V3 remain available for comparison."""
    filename = file.filename or "resume"
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=415, detail="Please upload a PDF or DOCX file.")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="File is too large. Maximum size is {0} MB.".format(settings.max_upload_mb),
        )
    try:
        parsed = parse_resume_v2(filename, content)
        quality = analyze_quality_v4(parsed)
        job_match = (
            analyze_job_match_v4(parsed, job_description)
            if job_description and job_description.strip()
            else None
        )
        return {
            "quality": quality,
            "job_match": job_match,
            "resume": parsed,
            "privacy": {
                "stored": False,
                "message": "This analysis is processed in memory and is not saved.",
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        await file.close()
