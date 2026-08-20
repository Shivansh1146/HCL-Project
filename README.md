# ⚡ AI-Powered Pull Request Code Review Assistant (HCL Project)

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Groq](https://img.shields.io/badge/Groq_AI-F4AF38?style=for-the-badge)
![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)

The **HCL Project** is a production-grade, AI-powered GitHub Pull Request Reviewer designed for high-fidelity security analysis, deterministic code verification, and deep explainability. Built with a "Zero-Noise" philosophy, it empowers teams with automated, committable suggestions while maintaining a rigorous security posture.

🌐 **Live Demo**: [https://hcl-project-3tgd.onrender.com](https://hcl-project-3tgd.onrender.com)

---

## ✨ Production-Grade Features

- **🛡️ Iron-Clad Deterministic Engine**: Multi-layered filtering that rejects LLM hallucinations and ensures multi-layer validated suggestions.
- **🛡️ Content Guard & Syntax Guard**: Permanent protection that prevents the AI from suggesting changes to comments, docstrings, or structural keywords.
- **💎 PERFECT Status Mapping**: Flawless code is recognized as **"ZERO RISK • VERIFIED,"** triggering an automatic success status on GitHub.
- **📊 Real-Time Glassmorphism Dashboard**: A premium, state-aware Command Center with live telemetry, spectral severity metrics, and instant decision intelligence.
- **📈 Advanced Review History & Analytics**: Full historical context of every AI review, displaying severity breakdowns, confidence levels, and overall code quality scores.
- **📅 14-Day Activity Trend Chart**: Accurate full calendar bar chart showing all 14 days including zero-count days, proper pixel-scaled bars, and alternating date labels.
- **🧠 Decision Explainability**: Deep insights into every flagged issue — rationale, impact, suggested fixes, and code quality summary across Security, Performance, Maintainability, and Reliability.
- **⚡ One-Click Fixes**: Automatically posts native ` ```suggestion ` syntax to GitHub, allowing developers to apply fixes directly from the PR interface.
- **🔒 Fail-Safe BLOCK**: If the AI engine is unreachable or returns malformed data, the system immediately defaults to `BLOCK` to prevent any unsafe approvals.
- **🔄 GitHub App Integration**: Full GitHub OAuth login, App Installation flow, and seamless Repository Synchronization.
- **⚙️ Live System Health Dashboard**: Settings page shows real-time status tiles for API Gateway, PostgreSQL, AI Provider Pipeline, and GitHub App — all fetched live from health endpoints.

---

## 🏗️ Technical Architecture

| Layer             | Technology            | Purpose                                                                    |
| ----------------- | --------------------- | -------------------------------------------------------------------------- |
| **Cloud Hosting** | Render (Blueprint)    | Automated CI/CD deployment with dynamic port binding and persistent state. |
| **Backend**       | FastAPI (Python 3.11) | High-performance, asynchronous orchestration engine.                       |
| **AI Engine**     | Groq (`openai/gpt-oss-20b`) | Security-focused analysis with deterministic temperature (0.1). Model configurable via `GROQ_MODEL` env var. |
| **Hardening**     | Python Services       | Literal blacklist, syntactic validation, and content guards.               |
| **Persistence**   | PostgreSQL (Neon Async Pool via `asyncpg`) | High-scale, concurrent connection pool with enterprise table schemas. |
| **Dashboard**     | Vanilla JS / CSS      | Minimalist, high-performance UI with real-time state synchronization.      |

---

## 🚀 Cloud Deployment (Render)

1. Connect this repository to **Render** via the dashboard.
2. Render will automatically detect the `render.yaml` blueprint.
3. Configure the following **Environment Variables**:
   - `DATABASE_URL`: PostgreSQL / Neon database connection string (`postgresql://...`).
   - `GROQ_API_KEY`: Your Groq API Key.
   - `GROQ_MODEL` *(optional)*: Override the AI model (default: `openai/gpt-oss-20b`).
   - `GITHUB_TOKEN`: Your GitHub Personal Access Token.
   - `GITHUB_WEBHOOK_SECRET`: Your custom webhook secret used to verify GitHub webhooks.
   - `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`: GitHub OAuth App credentials for the user login flow.
   - `APP_URL`: Set this to `https://hcl-project-3tgd.onrender.com` in production.
   - `GITHUB_OAUTH_REDIRECT_URI`: Set this to `https://hcl-project-3tgd.onrender.com/auth/callback` in production.
   - `GITHUB_APP_ID`: GitHub App ID used for installation tokens.
   - `GITHUB_APP_PRIVATE_KEY`: PEM private key for GitHub App JWTs.
   - `GITHUB_APP_SLUG` or `GITHUB_APP_NAME`: Used to generate the GitHub App installation link.
   - `GITHUB_APP_INSTALL_URL`: Optional explicit override for the GitHub App installation link.
4. The system will deploy automatically and provide a public URL.

### GitHub setup notes

- Use a **GitHub OAuth App** for the `/auth/login` and `/auth/callback` sign-in flow.
- Use a **GitHub App** for repository installation, webhooks, and installation access tokens.
- The callback URL for the OAuth App must be exactly:

```text
https://hcl-project-3tgd.onrender.com/auth/callback
```

- For Render, set `GITHUB_APP_PRIVATE_KEY` directly from the PEM contents. A local file path such as `GITHUB_APP_PRIVATE_KEY_PATH` works only on a machine that has the file.

---

## 🛠️ Local Setup & Development

### 1. Installation

```bash
git clone https://github.com/Shivansh1146/HCL-Project
cd "HCL Project"
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Create `backend/.env`:

```env
DATABASE_URL=postgresql://user:password@ep-host.neon.tech/neondb?sslmode=require
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-20b
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=your_secret
PORT=8000
APP_URL=http://localhost:8000
GITHUB_OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback
GITHUB_CLIENT_ID=your_id
GITHUB_CLIENT_SECRET=your_secret
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=/path/to/private-key.pem
```

### 3. Launching the System

```bash
cd backend
uvicorn main:app --reload --port 8000
```

---

## 🐳 Docker Orchestration

### 1. Build and Run

```bash
# Start with persistence and auto-restart
docker-compose up --build -d
```

### 2. Monitoring & Persistence

- **Logs**: View real-time output with `docker-compose logs -f`.
- **Database**: PostgreSQL connection pool handles persistent enterprise telemetry.
- **Dashboard**: Accessible at `http://localhost:8000`.

---

## 📁 Project Structure

```
HCL Project/
├── render.yaml                  # Automated Cloud Deployment Blueprint
├── docker-compose.yml           # Local Orchestration & Persistence
└── backend/
    ├── main.py                  # Webhook Pipeline & App Initialization
    ├── db_engine.py             # PostgreSQL asyncpg Connection Pool
    ├── auth/                    # OAuth & Session Management
    │   └── store.py             # Audit log retrieval & user data
    ├── routers/                 # API Routes (PRs, Webhooks, Auth, Analytics)
    ├── services/                # Business Logic
    │   ├── ai_service.py        # Groq GPT-OSS Engine + Hardening Guards
    │   ├── github_service.py    # GitHub API Integration & Rate Limiting
    │   ├── pr_service.py        # Pull Request State Management
    │   └── review_publisher.py  # GitHub Review Comment Publisher
    └── static/                  # Vanilla JS Frontend (Glassmorphism UI)
        └── js/pages/            # Dashboard, Review History, Analytics, Settings
```

---

## 🔐 Security & Safety Notes

- **Secrets**: All API keys and PEM certificates are strictly excluded from version control.
- **No Credential Exposure**: Settings page health tiles show connectivity status only — never database URLs, passwords, tokens, or private keys.
- **Non-Destructive**: The AI is programmed to never delete code blocks; it only suggests surgical line-level fixes.
- **Fail-Safe BLOCK**: If the AI engine is unreachable or times out, the system immediately defaults to `BLOCK`.

---

## 👤 Author

**Shivansh Jaiswal**

This project was fully designed, developed, and implemented by Shivansh Jaiswal.

- GitHub: [Shivansh1146](https://github.com/Shivansh1146)
- Project: [HCL AI Code Reviewer](https://github.com/Shivansh1146/HCL-Project)

_Built with Python · FastAPI · Groq · PostgreSQL · asyncpg · GitHub REST API · Optimized for Production_

---

## 📝 Recent Updates & Production Verification

### UI & Data Accuracy Fixes (August 2026)

- **🔧 Settings: Live System Health Status**: Replaced 100% hardcoded status cards with live data from `/api/health` and `/api/health/ai`. Database correctly shows **PostgreSQL Connected**, AI pipeline shows live model name. No credentials or secrets are ever exposed.
- **📊 Analytics: 14-Day Trend Chart**: Fixed the trend chart to always render all 14 calendar days, including zero-count days. Frontend now performs a date-join so sparse backend SQL data always fills the full timeline. Bars use pixel-accurate heights, count labels appear only on non-zero bars, and alternating x-axis labels prevent crowding.
- **📋 Review History: Table Layout**: Fixed horizontal overflow and cell wrapping. Table now enforces `white-space: nowrap` on headers and data rows, uses compact padding, and correctly ellipsizes long PR titles. Horizontal scrolling is scoped to the table container only.
- **🔍 Profile: Refresh Log Button**: Restored the audit log retrieval function (`get_audit_logs_for_user`) that was missing from `auth/store.py`. Added loading state and success toast to the Refresh Logs button.
- **🤖 AI Model Update**: Migrated from the deprecated `llama-3.1-8b-instant` (Groq removed all Llama 3.x models mid-2026) to `openai/gpt-oss-20b`, the current Groq production model. Configurable via `GROQ_MODEL` environment variable.

### Enterprise PostgreSQL Migration & Production Stabilization (August 2026)
- **PostgreSQL / Neon Engine**: Complete transition of backend persistence to high-performance `asyncpg` connection pool with dynamic `$n` positional parameter bindings.
- **Deduplication Race Condition Fix**: Eliminated pre-emptive delivery ID insertions in `webhook_service.py` that were poisoning idempotency checks, ensuring smooth GitHub webhook ingestion.
- **Production Schema Auto-Initialization**: Fully integrated automatic schema updates across `pull_requests`, `webhook_deliveries`, `selected_repos`, `installations`, and user session tables.
- **End-to-End Live Verification**: Validated full pipeline execution with real GitHub PRs on Render.

### Analytics and GitHub Publication-State Synchronization (August 2026)
- **Canonical repository names**: Analytics now uses the stored full repository name when it is present and prefixes the owner only for short names.
- **Reliable GitHub publication persistence**: After GitHub confirms a review, the corresponding `pull_requests` row records `review_posted`, `review_posted_at`, and the GitHub review ID.
- **Large GitHub review IDs**: `github_review_id` uses PostgreSQL `BIGINT`, so GitHub review identifiers are stored without 32-bit integer overflow.

### Real-time UI & End-to-End AI Publishing Pipeline (August 2026)
- **Zero-Flicker Dashboard Auto-Refresh**: All frontend pages now feature seamless 5-second polling for live updates.
- **GitHub Review Publisher Engine**: The AI autonomously publishes native GitHub Pull Request Reviews with exact inline comments mapped to the changed code.
- **Strict Suggestion Generation**: DiffValidator explicitly filters hallucinated fixes.

---

### ✅ Current System Status

| Component | Status |
|---|---|
| API Gateway | ✅ Operational |
| PostgreSQL Database | ✅ Connected (asyncpg pool) |
| AI Provider Pipeline | ✅ `openai/gpt-oss-20b` Active on Groq |
| GitHub App Integration | ✅ Configured |
| Webhook Processing | ✅ Zero race conditions |
| Review History UI | ✅ Layout fixed, all filters operational |
| Analytics Chart | ✅ Full 14-day calendar rendering |
| Settings Health Dashboard | ✅ Live data, no hardcoded values |
| Production URL | ✅ [https://hcl-project-3tgd.onrender.com](https://hcl-project-3tgd.onrender.com) |