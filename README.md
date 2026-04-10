# ⚡ AI-Powered Pull Request Code Review Assistant

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Groq](https://img.shields.io/badge/Groq_AI-F4AF38?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)

A production-grade, asynchronous code review agent that intercepts GitHub Pull Request webhooks in real-time. It analyzes code using **Groq LLaMA 3.3** to detect vulnerabilities and posts **inline suggested fixes** directly to the PR thread.

---

## ✨ Key Features

- **🚀 Real-Time Webhook Pipeline**: FastAPI `BackgroundTasks` handle induction instantly to prevent GitHub timeouts.
- **🧠 AI-Powered Insights**: LLaMA-based analysis catches SQL injection, hardcoded secrets, and logic bugs.
- **📊 Glassmorphism Dashboard**: Premium SaaS-style Command Center with live telemetry and spectral severity metrics.
- **🛡️ SQLite Persistence**: Full history of reviews and issues stored persistently in `reviews.db`.
- **🔍 Anti-Hallucination Engine**: Custom validator cross-checks AI findings against raw git diffs for near-zero false positives.
- **✨ Decision Intelligence**: Actionable PR status (Block Merge vs. Safe) for rapid decision making.

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
DASHBOARD_API_KEY=your_key   # Required for dashboard telemetry auth
```

### 3. Run Backend

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

### 4. Expose via Tunnel

```bash
npx -y localtunnel --port 8000
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
docker run -p 8000:8000 -v "${PWD}/backend/reviews.db:/app/reviews.db" ai-reviewer
```

### 2. Monitoring
- **Dashboard**: Still accessible at `http://localhost:8000/`
- **Logs**: View real-time container logs with `docker-compose logs -f`

### 3. Persistence
- Your `reviews.db` and logs are mounted as volumes, ensuring data survives container restarts.

---

## ✅ Health Check

```bash
GET /api/health   → {"status": "healthy"}
GET /api/stats    → live telemetry JSON
GET /            → dashboard UI
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
