# ⚡ AI-Powered Pull Request Code Review Assistant

A production-grade, asynchronous code review agent that intercepts GitHub Pull Request webhooks in real-time, analyzes changed code using Groq LLaMA AI to detect security vulnerabilities and bugs, and posts inline suggested fixes directly onto the exact vulnerable lines in the PR thread.

---

## 🏗️ Architecture

| Layer | Technology |
|---|---|
| Backend | Python 3.11 + FastAPI |
| AI Engine | Groq API (`llama-3.3-70b-versatile`) — Free tier |
| Integration | GitHub REST API v3 (Webhooks + Inline Comments) |
| Anti-Hallucination | Custom `validator.py` — variable name cross-checker |
| Noise Filter | Custom `filter_service.py` — heuristic scoring engine |
| Dashboard | Vanilla JS + CSS Glassmorphism — polls `/api/stats` every 3s |
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
- **Live metrics:** PRs reviewed, total issues found, uptime counter, last review time
- **Severity breakdown:** Animated bars for Critical/High, Medium, Low
- **Type breakdown:** Animated bars for Security, Bug, Performance
- **Review feed:** Live list of recent PRs with per-severity issue counts
- **Poll indicator:** Bottom-right corner confirms live connection status

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
```

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

## ✅ Health Check

```bash
GET /api/health   → {"status": "healthy"}
GET /api/stats    → live telemetry JSON
GET /            → dashboard UI
```

---

## 🔥 Testing

Create a branch with intentional vulnerabilities and open a PR:

```python
# test_vulnerable.py
import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("db.sqlite")
    query = "SELECT * FROM users WHERE id=" + user_id  # SQL Injection
    return conn.execute(query)

DB_ACCESS_TOKEN = "mock-secret-abc123"  # Hardcoded secret
password = "admin123"                    # Hardcoded password
```

The bot will detect all three issues, validate variable names, and post inline comments with one-click suggested fixes on the exact lines.

---

## 📁 Project Structure

```
HCL Project/
├── backend/
│   ├── main.py                  # FastAPI app — webhook pipeline + dashboard routes
│   ├── stats_store.py           # In-memory telemetry store
│   ├── requirements.txt
│   ├── .env                     # API keys — never commit
│   ├── static/
│   │   └── index.html           # Live dashboard (Glassmorphism UI)
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

## 🔐 Security Notes

- All API keys stored in `.env` — excluded from version control via `.gitignore`
- Test secrets use a `mock-secret-` prefix to avoid triggering GitHub's secret scanner on non-production test values
- GITHUB_TOKEN requires minimum `repo` scope only — no admin permissions needed

---

*Built with Python · FastAPI · Groq · GitHub REST API*
