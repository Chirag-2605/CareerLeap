# Resume Analyzer — Version 1

An Android-first, explainable resume analysis app.

## Product scope

- Firebase login (Google and email/password)
- Resume upload (PDF and DOCX)
- General resume quality score (0–100)
- Optional job-specific match score (0–100) when a job description is provided
- Evidence-backed deductions and prioritized recommendations
- No scan history and no database for resume content in V1

## Architecture

- `mobile/`: Expo + React Native app
- `backend/`: FastAPI analysis API
- Firebase Authentication: identity only
- Backend: verifies Firebase ID tokens when configured
- Resume content is processed in memory; the app does not save scan sessions

## 1. Run the backend

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

For local development only, set `AUTH_REQUIRED=false` in `.env`.
For any deployed environment, set `AUTH_REQUIRED=true` and configure Firebase Admin credentials.
The API docs are at `http://localhost:8000/docs`.

### Firebase Admin setup

Create a Firebase service account in Firebase Console → Project settings → Service accounts.
Set `FIREBASE_SERVICE_ACCOUNT_JSON` to the full JSON string, or set
`GOOGLE_APPLICATION_CREDENTIALS` to the path of the service-account JSON file.
Do not commit service-account credentials.

## 2. Configure Firebase

1. Create a Firebase project.
2. Enable Authentication → Google and Email/Password providers.
3. Register an Android app in Firebase using the Android package name you choose.
4. For Google sign-in, configure OAuth client IDs in Google Cloud / Firebase.
5. Copy the Firebase web app configuration into `mobile/.env`.

`mobile/.env.example`:

```env
EXPO_PUBLIC_API_URL=http://10.0.2.2:8000
EXPO_PUBLIC_FIREBASE_API_KEY=
EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN=
EXPO_PUBLIC_FIREBASE_PROJECT_ID=
EXPO_PUBLIC_FIREBASE_APP_ID=
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=
EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID=
```

For a physical Android device, replace `10.0.2.2` with your computer's LAN IP.
For production, use your HTTPS API URL.

## 3. Run the mobile app

The project targets Expo SDK 58 / React Native 0.88. Expo SDK 58 is the current stable SDK at the time this starter was prepared. Check the [Expo SDK reference](https://docs.expo.dev/versions/latest/) before upgrading packages.

Requires Node.js 22.13+ for the current Expo SDK toolchain.

```bash
cd mobile
cp .env.example .env
npm install
npx expo start
```

Use Expo Go for basic UI/email auth development. Google authentication and native release
builds should be tested with an Expo development build / EAS Build and valid OAuth client IDs.

To build an Android app with EAS:

```bash
npm install -g eas-cli
eas login
eas build:configure
eas build --platform android --profile preview
```

## Scoring model

### General resume quality score

The score is deterministic and versioned (`quality-v1`). It is a product-quality heuristic,
not a promise of how every ATS vendor will rank a resume.

| Dimension | Weight |
|---|---:|
| Contact information | 10 |
| Section structure | 15 |
| Skills | 15 |
| Experience | 25 |
| Measurable impact | 15 |
| Education | 10 |
| ATS readability | 10 |
| **Total** | **100** |

Every deduction is attached to a finding and a recommendation. The report includes
evidence snippets where available.

### Job-specific match score

When a job description is supplied, a separate score (`match-v1`) is calculated from:
- required/relevant skill phrase coverage (60%)
- important terminology coverage (25%)
- title/role alignment (15%)

The current matcher is transparent lexical matching with a small synonym map. It is not a
semantic embedding model and should not be marketed as one. Future versions can add a
benchmarked semantic model without changing the API contract.

## Privacy and production checklist

- V1 has no scan-history endpoint and no resume database.
- Uploads are size-limited and parsed in memory.
- Do not log resume text, job descriptions, access tokens, or file contents.
- Deploy behind HTTPS; configure CORS to the app's trusted origins.
- Keep Firebase service-account credentials in a secret manager.
- Add abuse protection/rate limits at the gateway before public launch.
- Publish a privacy policy and accurately disclose transient processing to users.
- Add explicit consent before any future feature stores resumes or uses them for model training.
- Add monitoring for latency, parse failures, file type failures, and score distribution.
- Before release, benchmark against a human-reviewed resume set and calibrate the scoring rubric.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## Known V1 limitations

- DOCX/PDF extraction quality depends on the source file; image-only/scanned PDFs need OCR,
  which is not included yet.
- Job matching is lexical and explainable, not a guarantee of ATS ranking.
- The mobile app requires your own Firebase and OAuth configuration before sign-in works.
- This repository is a source project; an APK/AAB must be built and tested with your credentials.
