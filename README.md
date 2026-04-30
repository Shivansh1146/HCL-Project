# ⚡ HCL Project: AI-Powered Pull Request Reviewer

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Groq](https://img.shields.io/badge/Groq_AI-F4AF38?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)

The **HCL Project** is an AI-powered GitHub Pull Request Reviewer designed to automate code analysis and provide actionable feedback directly within the developer workflow.

The system is built using **FastAPI** with asynchronous processing, integrated with **Groq LLMs** for semantic analysis, and uses **SQLite** for reliable state tracking. It is fully containerized with **Docker** for consistent deployment.

The review pipeline processes pull requests sequentially to ensure full diff coverage while handling API rate limits safely. A fail-safe decision system prevents unsafe approvals—any incomplete or uncertain analysis results in a `REVIEW_REQUIRED` outcome.

To improve accuracy, the system combines rule-based security checks (e.g., hardcoded secrets, unsafe functions) with AI-based reasoning, while minimizing false positives by ignoring already mitigated patterns such as parameterized SQL queries.

A key feature is its deep GitHub integration: the system posts inline review comments with native **"Suggested Changes,"** allowing developers to apply fixes instantly with one click. Additionally, a real-time dashboard provides visibility into analysis progress, detected issues, and system status.

---

## ✨ Key Features

- **🚀 Sequential Analysis Pipeline**: Processes PRs chunk-by-chunk to ensure **100% coverage** without hitting Groq API rate limits.
- **🧠 Precise AI Feedback**: Optimized prompting eliminates false positives (e.g., ignored mitigated SQLi) and provides specific, technical remediation.
- **📊 Glassmorphism Dashboard**: Premium SaaS-style Command Center with live telemetry and spectral severity metrics.
- **🛡️ SQLite Persistence**: Full history of reviews and issues stored persistently in `reviews.db`.
- **✨ GitHub Suggestions UI**: Automatically posts inline comments using GitHub's native ````suggestion` syntax for one-click fixes.
- **🔍 Intelligent Deduplication**: Advanced logic filters out redundant findings for the same file, line, and issue type.


---

## 🏗️ Architecture

| Layer | Technology |
|---|---|
| Backend | Python 3.11 + FastAPI |
| AI Engine | Groq API (`llama-3.3-70b-versatile`) — Free tier |
| Integration | GitHub REST API v3 (Webhooks + Inline Comments) |
| Persistence | SQLite (`reviews.db`) — stores history across restarts |
| Dashboard | Glassmorphism UI + **Decision Intelligence** (Actionable Guidance) |
| Tunneling | `localtunnel` (development) |

---

## ⚙️ The 9-Stage Pipeline

```
GitHub PR opened/updated
        │
        ▼
[1] POST /webhook → instant 200 OK (BackgroundTask spawned)
        │
        ▼
[2] Extract: owner, repo, pr_number, head_sha
        │
        ▼
[3] SHA Deduplication → skip if already processed
        │
        ▼
[4] Fetch raw .diff via GitHub REST API
        │
        ▼
[5] AI Analysis (Groq LLaMA, temp=0.1, chunked if >8000 chars)
        │
        ▼
[6] Heuristic Filter → drops vague/self-contradicting issues
        │
        ▼
[7] Anti-Hallucination Validator → corrects variable names & types
        │
        ▼
[8] Post inline comments to GitHub PR (422 fallback to thread)
        │
        ▼
[9] Record to telemetry → dashboard updates live
```

Uses FastAPI `BackgroundTasks` to return `200 OK` to GitHub instantly — preventing webhook timeouts caused by AI inference latency (5–15s).

---

## 🧠 AI Service (`ai_service.py`)

- **Model:** `llama-3.3-70b-versatile` via Groq (free, no billing required)
- **Temperature:** `0.1` — clamped for deterministic, accurate output
- **Prompt Architecture:** System/user role separation — rules sent as `system` for hard constraint enforcement
- **Chunking:** Diffs > 8000 chars split on newline boundaries into 4000-char chunks
- **Retry Logic:** 3 attempts with 1s backoff on API or network failures
- **Semantic Deduplication:** Word-overlap matching (threshold: 3 shared significant words) collapses duplicate findings across chunks
- **JSON Enforcement:** `response_format={"type": "json_object"}` at API level — no markdown parsing needed

---

## 🛡️ Filter Service (`filter_service.py`)

Heuristic scoring engine that eliminates hallucinated, vague, and self-contradicting AI output. Issues must pass **all hard filters** and score `> 0` to proceed.

**Hard Filters (instant drop — no scoring):**

| Check | Drops if |
|---|---|
| Required fields | Missing `type`, `severity`, `file`, `line`, `description`, or `fix` |
| Line number | Not a positive integer |
| Self-contradiction | Fix or description contains phrases like "no fix needed", "already mitigated", "which mitigates the risk" |
| Fix quality | Fix is plain English prose, a placeholder (`N/A`, `TODO`), or has no code characters |

**Scoring (must be > 0 to pass):**

| Condition | Score |
|---|---|
| `severity == "high"` | +2 |
| `severity == "medium"` | +1 |
| `description length > 30 chars` | +1 |
| Vague words (`improve`, `optimize`, `consider`, `refactor`...) | −2 |
| Fix shorter than 15 chars | −1 |

---

## 🔍 Anti-Hallucination Validator (`validator.py`)

A custom post-processing engine that cross-checks every AI-generated issue against the actual code in the raw git diff before anything is posted to GitHub.

**What it corrects:**

| Problem | Fix |
|---|---|
| AI used `password =` but code has `API_KEY =` | Rewrites fix to use `API_KEY =` |
| AI used `os.environ.get('PASSWORD')` but variable is `API_KEY` | Rewrites to `os.environ.get('API_KEY')` |
| Description says "hardcoded password" but code has `API_KEY` | Corrects description to match actual variable |
| Issue typed as `bug` but line contains a hardcoded secret | Overrides type to `security` |

The validator locates the actual code line using the diff's hunk headers and line counters — it never trusts AI line references blindly.

---

## 📊 Live Analytics Dashboard

Accessible at `http://localhost:8001/` — auto-refreshes every 3 seconds.


- **Status bar:** Shows backend offline warning if connection is lost
- **Actionable Insights:** Decision-first guidance (e.g., "Block Merge" vs "Safe to Merge")
- **Refined Spectrum:** Fixed overuse of red; subtle borders for High, neutral for Medium, and dimmed for Low
- **Live metrics:** PRs reviewed, total issues found, uptime counter, last review time
- **Severity & Type BREAKDOWN:** Animated charts for Critical, Significant, Minor, and Category distribution
- **Micro-Polish:** Hover scale effects, smooth animations (200ms ease), and refined CTA buttons

---

## 🛠️ Setup

### 1. Clone & Install

```bash
git clone https://github.com/Shivansh1146/hcl-project
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
GROQ_API_KEY=gsk_...         # Free at console.groq.com
GITHUB_TOKEN=github_pat_...  # Needs repo + pull_request scopes
DASHBOARD_API_KEY=your_key   # Optional unless auth is enforced
REQUIRE_DASHBOARD_API_KEY=false
```

By default, dashboard API auth is disabled for local development.
Set `REQUIRE_DASHBOARD_API_KEY=true` to require `X-API-Key` on `/api/stats`.

### 3. Run Backend

```bash
cd backend
python -m uvicorn main:app --reload --port 8001

```

### 4. Expose via Tunnel

```bash
npx -y localtunnel --port 8001

# → your url is: https://xxxx.loca.lt
```

### 5. Configure GitHub Webhook

1. Go to your GitHub repo → **Settings** → **Webhooks** → **Add webhook**
2. **Payload URL:** `https://xxxx.loca.lt/webhook`
3. **Content type:** `application/json`
4. **Events:** Select **Pull requests** only
5. Click **Save**

---

## 🐳 Docker Deployment

The AI Code Reviewer is fully containerized for production consistency and easy deployment.

### 1. Build and Run
```bash
# Option A: Build and run with Docker Compose (Recommended)
docker-compose up --build -d

# Option B: Manual build and run
docker build -t ai-reviewer .
docker run -p 8001:8001 -v "${PWD}/backend/reviews.db:/app/reviews.db" ai-reviewer

```

### 2. Monitoring
- **Dashboard**: Still accessible at `http://localhost:8001/`

- **Logs**: View real-time container logs with `docker-compose logs -f`

### 3. Persistence
- Your `reviews.db` and logs are mounted as volumes, ensuring data survives container restarts.

---

## ✅ Health Check

```bash
GET /api/health   → {"status": "healthy"}
GET /api/stats    → live telemetry JSON
GET /            → dashboard UI (Port 8001)

```

---

## 📁 Project Structure

```
HCL Project/
├── Dockerfile                   # Production container config (Root context)
├── docker-compose.yml           # Service orchestration & persistence
├── README.md                    # Project documentation
├── vulnerable_verification.py   # Intentionally vulnerable code for testing
├── send_webhook.py              # Utility to trigger webhook manually
├── backend/
│   ├── main.py                  # FastAPI app — webhook pipeline + dashboard routes
│   ├── stats_store.py           # Persistent SQLite telemetry engine
│   ├── reviews.db               # SQLite database (Git ignored)
│   ├── requirements.txt         # Production dependencies (gunicorn included)
│   ├── .env                     # API keys — never commit
│   ├── vulnerable_test.py       # Internal security test script
│   ├── test_ai.py               # AI service integration test
│   ├── static/
│   │   └── index.html           # Live dashboard (Refined Glassmorphism UI)
│   ├── services/
│   │   ├── ai_service.py        # Groq LLaMA integration + chunking
│   │   ├── github_service.py    # GitHub API — diff fetch + comment post
│   │   ├── filter_service.py    # Heuristic scoring + noise filter
│   │   └── validator.py         # Anti-hallucination variable cross-checker
│   └── utils/
│       └── formatter.py         # GitHub markdown comment formatter
├── .gitignore
└── README.md
```

---

## 🧪 Testing & Verification

### 0. Manual End-to-End Verification (Step-by-Step)
Use this checklist to verify the project manually on Windows before testing GitHub integration.

```bash
# 1) Open terminal at project root
cd "C:\Users\shivansh\Desktop\HCL Project"

# 2) Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3) Install/update backend dependencies
pip install -r .\backend\requirements.txt

# 4) Start backend
cd .\backend
python -m uvicorn main:app --reload --port 8001

```

Expected startup output:
- `Uvicorn running on http://127.0.0.1:8001`


In your browser, verify:
- `http://127.0.0.1:8001/api/health` returns healthy JSON
- `http://127.0.0.1:8001/api/stats` returns telemetry JSON
- `http://127.0.0.1:8001/` loads dashboard UI (no API-key prompt by default)


Open a second terminal (project root, venv active) and run:

```bash
python .\send_webhook.py
```

Expected result:
- HTTP status `200`
- Response like: `{"status":"processing","sha":"..."}`

Optional GitHub webhook validation:

```bash
npx -y localtunnel --port 8001

```

Then set GitHub Webhook **Payload URL** to:
- `https://<your-url>.loca.lt/webhook`

### 1. AI Integration Test
Verify that the Groq AI service is correctly analyzing diffs and returning JSON issues.
```bash
cd backend
python test_ai.py
```

### 2. Security Vulnerability Test
An intentionally vulnerable script is provided to verify the AI's detection capabilities (SQLi, Command Injection, etc.).
```bash
python vulnerable_verification.py
```

### 3. Webhook Simulation
Trigger a manual webhook event to test the full pipeline (Induction → Analysis → Response).
```bash
# Ensure localtunnel and backend are running first
python send_webhook.py
```

---

## 🔐 Security Notes

- All API keys stored in `.env` — excluded from version control via `.gitignore`
- Test secrets use a `mock-secret-` prefix to avoid triggering GitHub's secret scanner on non-production test values
- GITHUB_TOKEN requires minimum `repo` scope only — no admin permissions needed

---

## 👤 Author

**Shivansh**
- GitHub: [Shivansh1146](https://github.com/Shivansh1146)
- Project: [HCL Project](https://github.com/Shivansh1146/hcl-project)

---

*Built with Python · FastAPI · Groq · GitHub REST API*
