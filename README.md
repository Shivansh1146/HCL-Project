# ⚡ AI-Powered Pull Request Code Review Assistant

A production-grade application that intercepts GitHub Pull Request webhooks in real-time, analyzes the changed code using AI to detect bugs and security flaws, and posts inline comments directly onto the vulnerable lines in the PR.

---

## 🏗️ Architecture

| Layer | Technology |
|---|---|
| **Backend** | Python + FastAPI |
| **AI Engine** | Groq API (`llama-3.3-70b-versatile`) — Free |
| **Integration** | GitHub REST API (Webhooks & Inline Comments) |
| **Tunneling** | localtunnel (dev) |

---

## 📊 Live Analytics Dashboard

The platform includes a gorgeous, real-time tracking interface that auto-refreshes every 3 seconds to reflect the AI's autonomous activity.

- **URL:** `http://localhost:8001/`
- **Features:**
  - **Live Metrics**: Total PRs parsed, Uptime counter, System Status
  - **Animated Charts**: Glowing progress bars showing breakdown by Severity (Critical/Med/Low) and Type (Security/Bug/Performance).
  - **Review Feed**: Real-time tumbling feed showing exact PRs and timestamped review metadata.

---

## ⚙️ Pipeline (`main.py`)

GitHub sends a `POST` → instantly returns `200 OK` → background task runs:

1. **Validate** — Accepts only `opened` / `synchronize` PR events
2. **Extract** — Pulls `owner`, `repo`, `pr_number`, `head_sha` from payload
3. **Fetch Diff** — Downloads raw `.diff` from GitHub (`application/vnd.github.v3.diff`)
4. **AI Analysis** — Sends diff to Groq LLaMA for security/bug detection
5. **Filter** — Scores and drops low-signal / vague AI suggestions
6. **Post Comment** — Posts inline comments on the exact changed lines via GitHub API
7. **Record Stats** — Logs metadata (severity counts, issue types) to the live memory tracker

> Uses FastAPI `BackgroundTasks` to return instant `200 OK` to GitHub before heavy processing begins — preventing webhook timeouts.

---

## 🧠 AI Service (`ai_service.py`)

- **Model**: `llama-3.3-70b-versatile` via Groq (free, no billing)
- **Chunking**: Diffs > 8000 chars split into 4000-char chunks processed separately
- **Retry Logic**: 3 attempts with 1s backoff on API failures
- **Semantic Deduplication**: Merges similar issues across chunks using word-overlap matching
- **Strict JSON Schema**: Forces structured output — `type`, `severity`, `file`, `line`, `description`, `fix`

---

## 🛡️ Filter Service (`filter_service.py`)

Scoring engine to eliminate hallucinated or vague AI output:

| Condition | Score |
|---|---|
| `severity == "high"` | +2 |
| `severity == "medium"` | +1 |
| `description length > 30` | +1 |
| Vague words (`improve`, `optimize`, etc.) | -2 |
| **Threshold to pass** | `≥ 0` |

---

## 🛠️ Setup

### 1. Clone & Install

```powershell
git clone https://github.com/Shivansh1146/hcl-project
cd "HCL Project"
python -m venv .venv
.\.venv\Scripts\activate
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Create `backend/.env`:

```env
GROQ_API_KEY=gsk_...        # Get free at console.groq.com
GITHUB_TOKEN=github_pat_... # Needs 'repo' scope
PORT=8000
ENVIRONMENT=development
```

### 3. Run Backend

```powershell
cd backend
python -m uvicorn main:app --reload --port 8001
```

### 4. Expose via Tunnel

```powershell
npx -y localtunnel --port 8001
# → your url is: https://xxxx.loca.lt
```

### 5. Configure GitHub Webhook

1. Go to **GitHub Repo → Settings → Webhooks → Add webhook**
2. **Payload URL**: `https://xxxx.loca.lt/webhook`
3. **Content type**: `application/json`
4. **Events**: Select `Pull requests` only
5. Click **Save**

---

## ✅ Health Check

```
GET https://xxxx.loca.lt/api/health
→ {"status": "healthy"}

GET https://xxxx.loca.lt/webhook
→ {"detail": "Method Not Allowed"}  ✅ (correct — expects POST from GitHub)
```

---

## 🔥 Testing

Create a new branch and introduce a security flaw:

```python
# bad_code.py
password = "123456"
query = "SELECT * FROM users WHERE id=" + user_input
```

Push and open a PR — the bot will automatically detect the vulnerability and post an inline comment on the exact line!

---

## 📁 Project Structure

```
HCL Project/
├── backend/
│   ├── main.py                  # FastAPI app + webhook pipeline + dashboard routes
│   ├── stats_store.py           # In-memory analytics & metrics tracker
│   ├── requirements.txt
│   ├── .env                     # API keys (never commit!)
│   ├── static/
│   │   └── index.html           # Live interactive dashboard UI
│   ├── services/
│   │   ├── ai_service.py        # Groq LLaMA integration
│   │   ├── github_service.py    # GitHub API (diff fetch + comment post)
│   │   └── filter_service.py    # Issue scoring & filtering
│   └── utils/
│       └── formatter.py         # Markdown comment formatter
└── README.md
```
