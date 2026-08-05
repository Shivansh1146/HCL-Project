# Enterprise AI Pull Request Review System — Technical Documentation

## 1. Architecture Overview

The system is an enterprise-grade AI Pull Request Review SaaS built on FastAPI (Python) and Vanilla JavaScript ES6 modules. It provides automated security, bug detection, quality, and performance code reviews for GitHub Pull Requests.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Browser Client (SPA)                             │
│  State Store · Hash Router · API Client Wrapper · Component Layer (Vanilla) │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HttpOnly Cookie / JSON API
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                            FastAPI Backend Server                           │
│  OAuth Service · Webhook Processor · Audit Logger · Rate Limiter (SlowAPI) │
└────────────────══┬───────────────────────────────────────┬──────────────────┘
                   │                                       │
┌──────────────────▼──────────────────┐         ┌──────────▼──────────────────┐
│         SQLite Telemetry DB         │         │   Groq LLM Review Pipeline  │
│  prs · issues · repos · audit_logs  │         │  Llama-3 70B Deep Analysis  │
└─────────────────────────────────────┘         └─────────────────────────────┘
```

---

## 2. Directory & Folder Structure

```
.
├── backend/
│   ├── auth/
│   │   ├── dependencies.py    # Auth dependencies (require_auth)
│   │   ├── models.py          # Pydantic schemas (User, AuditLog)
│   │   ├── oauth_service.py   # GitHub OAuth code exchange logic
│   │   ├── session.py         # Session token creation & verification
│   │   └── store.py           # SQLite auth schema & user CRUD
│   ├── routers/
│   │   ├── analytics_router.py # GET /api/analytics & GET /api/analytics/export
│   │   ├── app_router.py       # GitHub App lifecycle & repository endpoints
│   │   ├── auth_router.py      # /auth/login, /auth/callback, /auth/me, /auth/logout
│   │   └── pr_router.py        # /api/prs list, detail, and re-review trigger
│   ├── services/
│   │   ├── audit_service.py    # Structured enterprise audit logging
│   │   └── github_app_service.py # GitHub App JWT token generation
│   ├── static/
│   │   ├── css/               # Modular CSS design system (tokens, utilities, cards)
│   │   ├── js/
│   │   │   ├── components/    # Header, Sidebar, Toast, Skeleton, Empty State
│   │   │   ├── config/        # Central config.js routes & API endpoints
│   │   │   ├── pages/         # Dashboard, Repositories, PRs, Analytics, Profile, Settings, Error
│   │   │   ├── services/      # api.js request wrapper, auth.js session, router.js SPA
│   │   │   ├── tests/         # frontend_tests.js Node test runner
│   │   │   └── utils/         # state.js store, dom.js XSS sanitizer
│   │   └── index.html         # Main SPA mount document
│   ├── main.py                # FastAPI app initialization & router mounting
│   ├── stats_store.py         # DB helpers for PR telemetry and issues
│   └── tests/                 # Pytest backend test suite
```

---

## 3. Complete API Endpoint Reference

### Authentication Endpoints

- `GET  /auth/login` — Initiates GitHub OAuth flow.
- `GET  /auth/callback` — Exchanges OAuth code for session token cookie.
- `GET  /auth/me` — Returns currently logged-in user profile.
- `POST /auth/logout` — Revokes session cookie.
- `GET  /auth/audit-logs` — Fetches security audit trail for user.

### GitHub App Lifecycle & Repository Endpoints

- `GET  /api/app/installations` — Lists connected GitHub App installations.
- `GET  /api/app/installations/{inst_id}/repos` — Fetches repositories for an installation.
- `POST /api/app/installations/{inst_id}/repos/select` — Updates selected repositories for AI review.
- `POST /api/app/installations/{inst_id}/sync` — Triggers force re-sync for an installation.

### Pull Request Review Endpoints

- `GET  /api/prs` — Lists PR reviews (supports `repo` and `status` query filters).
- `GET  /api/prs/{owner}/{repo}/{pr_number}` — Retrieves detailed issue findings and AI decision rationale.
- `POST /api/prs/{owner}/{repo}/{pr_number}/review` — On-demand trigger for re-running AI code review.

### Analytics Endpoints

- `GET  /api/analytics` — Computes overall review counts, decision breakdown, severity distribution, and leaderboards.
- `GET  /api/analytics/export` — Exports telemetry data in CSV or JSON format.

---

## 4. Environment Variables

| Variable Name            | Required | Default Value | Description                                                      |
| ------------------------ | -------- | ------------- | ---------------------------------------------------------------- |
| `GITHUB_CLIENT_ID`       | Yes      | —             | GitHub OAuth App Client ID                                       |
| `GITHUB_CLIENT_SECRET`   | Yes      | —             | GitHub OAuth App Client Secret                                   |
| `GITHUB_APP_ID`          | Yes      | —             | GitHub App ID for webhooks & installation tokens                 |
| `GITHUB_PRIVATE_KEY`     | Yes      | —             | PEM RSA private key for GitHub App JWT generation                |
| `GITHUB_APP_PRIVATE_KEY` | No       | —             | Legacy alias for the GitHub App PEM private key                  |
| `GITHUB_APP_NAME`        | No       | —             | GitHub App display name used to derive the installation URL slug |
| `GITHUB_APP_SLUG`        | No       | —             | GitHub App slug used to generate the installation URL            |
| `GITHUB_APP_INSTALL_URL` | No       | —             | Explicit GitHub App installation URL override                    |
| `GROQ_API_KEY`           | Yes      | —             | Groq Llama-3 70B API key for code analysis                       |
| `SECRET_KEY`             | Yes      | `dev-secret`  | Cryptographic secret for signing session tokens                  |
| `ENVIRONMENT`            | No       | `development` | Environment mode (`development` / `production`)                  |

---

## 5. Local Setup & Execution Instructions

### Prerequisites

- Python 3.10+
- Node.js 18+ (for running the frontend test suite)

### 1. Clone Repository & Install Python Dependencies

```bash
cd "backend"
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GROQ_API_KEY=your_groq_key
SECRET_KEY=super-secret-key-32-chars
```

### 3. Run Backend & Dashboard Server

```bash
python -m uvicorn main:app --reload --port 8000
```

Open browser at `http://localhost:8000`.

### 4. Run Test Suites

```bash
# Run Frontend Unit Tests
node static/js/tests/frontend_tests.js

# Run Backend Pytest Suite
python -m pytest tests
```
