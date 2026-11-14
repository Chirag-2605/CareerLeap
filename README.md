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

## Credits database (Neon PostgreSQL)

The first credit-ledger milestone uses Neon PostgreSQL while Firebase remains the identity provider.

1. Create a Neon project and database.
2. Set `DATABASE_URL` in the backend environment to the Neon pooled or direct connection string (keep credentials server-side).
3. Apply `backend/migrations/001_credit_ledger.sql` once to the target database.
4. Install the updated backend requirements.
5. Set `CREDITS_ENABLED=true` only after the migration has been applied and the database connection has been verified.

The authenticated endpoints are:
- `GET /api/v1/credits/balance` — lazily creates a wallet and grants the initial three credits exactly once.
- `GET /api/v1/credits/transactions` — returns the authenticated user's latest ledger entries.

When `CREDITS_ENABLED=true`, the existing `/api/v1/analyze` endpoint requires an `Idempotency-Key` header. Job descriptions remain optional. The endpoint reserves one credit before analysis, commits the debit only after successful analysis, and releases the reservation when analysis raises an error. The flag defaults to false so deployments do not accidentally enable an unconfigured wallet.

### Google Play credit packs

The Android app uses Google Play Billing consumable one-time products:

| Product ID | Credits | India price |
| --- | ---: | ---: |
| `careerleap_10_scans` | 10 | ₹49 |
| `careerleap_25_scans` | 25 | ₹99 |

Configure these exact product IDs and prices in Play Console under Monetize > Products > In-app products. Products must be active and available to the app's testing track before they can be fetched by the app. The app obtains display prices from Google Play rather than hardcoding them.

Apply `backend/migrations/002_google_play_purchases.sql` after the credit-ledger migration. Configure `GOOGLE_PLAY_PACKAGE_NAME` and `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` on the backend. The Google Cloud service account must have the Android Publisher API enabled and be granted the required app permissions in Play Console. Never place this service-account JSON in the mobile app or commit it.

The authenticated `POST /api/v1/credits/google-play/verify` endpoint verifies product ID, purchase state, consumption state, quantity, and the obfuscated Firebase account ID against the Google Play Developer API. A unique purchase-token ledger and a single Neon transaction ensure each purchase can add credits only once. The mobile app finishes the consumable transaction only after backend verification succeeds. If verification is temporarily unavailable, the purchase is left unfinished so the app can retry instead of silently losing the purchase.

Expo IAP requires a custom native development build; Expo Go does not include the native billing module. Rebuild the Android development client after installing the IAP dependency and plugin. Do not merge or enable paid purchases in production until Play Console products, service-account access, migration, backend configuration, and a Play internal-testing purchase have all been validated. Never commit the Neon connection string or Google Play service-account credentials.
