# CareerLeap

CareerLeap is a career-assistance project. Its first module is an explainable resume analyzer for resume quality and job-specific alignment.

## Resume Analyzer

### Current capabilities (V1)
- Resume upload (PDF and DOCX)
- General resume quality score (0–100)
- Optional job-specific match score (0–100)
- Findings and prioritized recommendations
- Resume content processed in memory; no scan history is persisted by the API

### Parser V2 milestone
The V2 parser is being introduced alongside V1. It exposes POST /api/v2/parse and returns a normalized, evidence-linked representation of the uploaded resume. This endpoint extracts and organizes content only; it does not score the resume or call an LLM.

V2 parser output includes:
- Detected sections and their text/bullet items
- Evidence IDs linked to source lines and page numbers when available
- Basic contact fields and detected skills
- Document metadata and extraction warnings

The parser is heuristic. It does not currently perform OCR, guarantee PDF reading order for complex layouts, or infer a candidate's qualifications.


### Analysis V3 milestone (new, validation pending)
The V3 analysis is exposed separately at POST /api/v3/analyze. V1 and V2 endpoints and scoring modules remain unchanged.

V3 adds:
- Explicit required / preferred / informational job-skill classification; neutral mentions are not reported as missing.
- Conservative, explicit skill aliases rather than broad technology-family assumptions.
- Separate listed-versus-demonstrated skill match states, with resume evidence IDs.
- Requirement-level match details and explainable skill gaps.
- Responsibility-to-experience/project bullet comparison using transparent lexical overlap (not embeddings).
- Role-family and seniority signals only when both sides can be identified; unknown signals are treated neutrally.
- A V3 quality response with evidence coverage counts for recognized, demonstrated, and listed-only skills.

V3 remains a deterministic heuristic. It does not use embeddings or an LLM, and responsibility overlap is a preliminary lexical signal rather than semantic understanding. Run the complete backend test suite before relying on V3 results.

### Analysis V4 milestone (new, validation pending)

V4 is an independent analysis implementation exposed at POST /api/v4/analyze. It does not call the V2 or V3 scoring functions; the V1-V3 endpoints remain available for side-by-side comparison.

V4 quality scoring evaluates the content of achievement bullets, experience depth, measurable outcomes, demonstrated versus listed skills, education evidence, structure, and extraction/readability warnings. Section presence alone cannot produce a high score.

V4 job matching carries Required Qualifications / Preferred Qualifications heading context across bullet lists, preserves technical responsibility statements, distinguishes demonstrated/listed/missing skills, and compares responsibility text with resume evidence using a transparent lexical similarity measure. Only dimensions with enough input evidence are included in the normalized score; unassessed dimensions are shown with assessed=false and do not receive free points.

V4 is still a deterministic heuristic, not a semantic embedding model or an employer ATS prediction. Run the full backend test suite and compare real resumes/job descriptions before using the score in production.

## Architecture

- mobile/: Expo + React Native app
- backend/: FastAPI API
- Firebase Authentication: identity only
- Resume content is processed in memory and is not persisted by the analysis endpoints

## Run the backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

For local development only, set AUTH_REQUIRED=false in your local .env.
For deployed environments, set AUTH_REQUIRED=true and configure Firebase Admin credentials.
API docs: http://localhost:8000/docs.

### Firebase Admin setup

Create a Firebase service account in Firebase Console → Project settings → Service accounts.
Set FIREBASE_SERVICE_ACCOUNT_JSON to the full JSON string, or set
GOOGLE_APPLICATION_CREDENTIALS to the path of the service-account JSON file.
Do not commit service-account credentials.

## Configure the mobile app

1. Create a Firebase project.
2. Enable the required Authentication providers.
3. Register an Android app in Firebase using the Android package name.
4. Configure OAuth client IDs for Google sign-in if enabled.
5. Copy the Firebase web app configuration into mobile/.env.

For an Android emulator, the API URL is typically http://10.0.2.2:8000.
For a physical Android device, use your computer's LAN IP. For production, use an HTTPS API URL.

```bash
cd mobile
npm install
npx expo start
```

## Scoring model (V1)

The V1 general quality score (quality-v1) and job-match score (match-v1) are transparent product heuristics, not predictions of how every ATS vendor ranks a resume. The job matcher is lexical; it is not a semantic embedding model.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## Privacy and release notes

- Do not log resume text, job descriptions, access tokens, or file contents.
- Keep Firebase service-account credentials in a secret manager.
- Deploy behind HTTPS and restrict CORS to trusted origins.
- Add abuse protection/rate limits before public launch.
- Benchmark extraction and scoring against human-reviewed examples before making accuracy claims.
- Image-only/scanned PDFs require OCR, which is not included in the current parser.
