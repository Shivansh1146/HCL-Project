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
- **🧠 Decision Explainability**: Deep insights into every flagged issue. The AI provides the rationale ("Why flagged"), potential impact, suggested fixes, and a code quality summary across Security, Performance, Maintainability, and Reliability.
- **⚡ One-Click Fixes**: Automatically posts native ` ```suggestion ` syntax to GitHub, allowing developers to apply fixes directly from the PR interface.
- **🔒 Fail-Safe BLOCK**: If the AI engine is unreachable or returns malformed data, the system immediately defaults to `BLOCK` to prevent any unsafe approvals.
- **🔄 GitHub App Integration**: Full GitHub OAuth login, App Installation flow, and seamless Repository Synchronization.

---

## 🏗️ Technical Architecture

| Layer             | Technology            | Purpose                                                                    |
| ----------------- | --------------------- | -------------------------------------------------------------------------- |
| **Cloud Hosting** | Render (Blueprint)    | Automated CI/CD deployment with dynamic port binding and persistent state. |
| **Backend**       | FastAPI (Python 3.11) | High-performance, asynchronous orchestration engine.                       |
| **AI Engine**     | Groq (LLaMA 3)        | Security-focused analysis with deterministic temperature (0.1).            |
| **Hardening**     | Python Services       | Literal blacklist, syntactic validation, and content guards.               |
| **Persistence**   | SQLite (`reviews.db`) | Atomic state tracking with WAL mode for concurrency control.               |
| **Dashboard**     | Vanilla JS / CSS      | Minimalist, high-performance UI with real-time state synchronization.      |

---

## 🚀 Cloud Deployment (Render)

1. Connect this repository to **Render** via the dashboard.
2. Render will automatically detect the `render.yaml` blueprint.
3. Configure the following **Environment Variables**:
   - `GITHUB_TOKEN`: Your GitHub Personal Access Token.
   - `GROQ_API_KEY`: Your Groq API Key.
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
GROQ_API_KEY=gsk_...
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
- **Database**: The `reviews.db` is mounted as a volume, ensuring data survives restarts.
- **Dashboard**: Accessible at `http://localhost:8000`.

---

## 📁 Project Structure

```
HCL Project/
├── render.yaml                  # Automated Cloud Deployment Blueprint
├── docker-compose.yml           # Local Orchestration & Persistence
└── backend/
    ├── main.py                  # Webhook Pipeline & App Initialization
    ├── auth/                    # OAuth & Session Management
    ├── routers/                 # API Routes (PRs, Webhooks, Auth)
    ├── services/                # Business Logic
    │   ├── ai_service.py        # Groq LLaMA Engine + Hardening Guards
    │   ├── github_service.py    # GitHub API Integration & Rate Limiting
    │   ├── pr_service.py        # Pull Request State Management
    │   └── review_publisher.py  # GitHub Review Comment Publisher
    └── static/                  # Vanilla JS Frontend (Glassmorphism UI)
        └── js/pages/            # Dashboard, Review History, Analytics
```

---

## 🔐 Security & Safety Notes

- **Secrets**: All API keys and PEM certificates are strictly excluded from version control.
- **Non-Destructive**: The AI is programmed to never delete code blocks; it only suggests surgical line-level fixes.
- **Fail-Safe BLOCK**: If the AI engine is unreachable or times out, the system immediately defaults to `BLOCK`.

---

## 👤 Author

**Shivansh Jaiswal**

This project was fully designed, developed, and implemented by Shivansh Jaiswal.

- GitHub: [Shivansh1146](https://github.com/Shivansh1146)
- Project: [HCL AI Code Reviewer](https://github.com/Shivansh1146/HCL-Project)

_Built with Python · FastAPI · Groq · GitHub REST API · Optimized for Production_

---

## 📝 Recent Updates & Fixes

### Final Production Audit & UI Polish (August 2026)
- **Design System Standardization**: Created centralized severity CSS variables (`--severity-high`, `--severity-medium`, `--severity-low`) and reusable component library for consistent UI across all pages
- **Terminology Standardization**: Unified severity terminology across Dashboard, Analytics, Review History, and Pull Requests pages (High/Critical, Medium, Low/Code Smell)
- **Code Quality Improvements**: Removed duplicate debug endpoints, unused PostgreSQL infrastructure, and cleaned up dependencies (removed asyncpg, sqlalchemy, alembic)
- **Repository Management UX**: Simplified button labels (Enable Review, Disable Review, Save Repository Settings) with helpful tooltips and smart disable when no repositories are visible
- **Button State Synchronization**: Added automatic disabled state updates for bulk action buttons when repository list changes via search, filters, pagination, or sync
- **Production Validation**: Successfully completed end-to-end test with 100% bug detection rate (5/5 intentional security bugs detected with BLOCK decision)

### Analytics Dashboard Enhancements (August 2026)
- **Fixed Data Inconsistency**: Updated Analytics API to query the correct `pull_requests` table instead of the deprecated `prs` table, ensuring consistent data across Dashboard, Analytics, Review History, and Pull Requests pages
- **Fixed Connection Error**: Added missing database columns (`total_chunks`, `processed_chunks`) to the pull_requests schema migration, resolving Analytics page loading issues
- **Improved UI**: Standardized severity distribution colors - High/Critical (red), Medium (orange), Low/Code Smell (blue) for better visual consistency with the application's design system

### System Status
- ✅ All webhooks processing correctly
- ✅ AI review pipeline fully operational
- ✅ GitHub integration working seamlessly
- ✅ Database schema optimized (SQLite-only)
- ✅ Frontend design system standardized
- ✅ Production-ready with comprehensive security and error handling
