# ⚡ AI-Powered Pull Request Code Review Assistant

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

- **🚀 Senior Security Reviewer Persona**: AI acts as a strict static analyzer, focusing on real, exploitable vulnerabilities and providing minimal, surgical fixes.
- **🛡️ 3-Layer Hardening Pipeline**: Multi-stage validation rejects false positives (e.g., safe SQL), destructive code deletions, and vague/non-actionable feedback.
- **🔍 Anti-Hallucination Guard**: Cross-references AI suggestions against the actual git diff to ensure valid line mappings and non-redundant code changes.
- **🧠 Proximity Deduplication**: Intelligently collapses identical issues occurring on adjacent lines (within a 3-line window) into a single, high-fidelity report.
- **📊 Glassmorphism Dashboard**: Premium SaaS-style Command Center with live telemetry, spectral severity metrics, and real-time decision intelligence.
- **✨ GitHub Suggestions UI**: Automatically posts native ````suggestion` syntax for one-click fixes directly on the Pull Request.

---

## 🏗️ Architecture

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Python 3.11 + FastAPI | Core API and asynchronous background processing engine. |
| **AI Engine** | Groq (`llama-3.3-70b`) | Security-focused analysis with deterministic temperature (0.1). |
| **Filter Layer** | `filter_service.py` | Rejects SQLi false positives on parameterized queries and vague prose. |
| **Safety Layer** | `validator.py` | Detects AI line-mapping hallucinations and auto-corrects them. |
| **Persistence** | SQLite (`reviews.db`) | Atomic state tracking and historical review telemetry. |
| **Dashboard** | Vanilla HTML/JS/CSS | Real-time observability with zero-flicker state management. |

---

## 🛡️ Production Hardening Layers

### 1. Senior Security Mindset (`ai_service.py`)
The system prompt is tuned to a "Static Analyzer" persona.
*   **Rules**: No generic advice, no hypothetical bugs, and no destructive fixes.
*   **Minimalism**: Every fix must modify only the affected line(s) to maintain original logic.
*   **Confidence Kill Switch**: If a large diff (> 3,000 chars) returns zero issues, the system marks it as `REVIEW_REQUIRED` to prevent silent failures.

### 2. Strict Validation Pipeline (`filter_service.py`)
Replaces simple scoring with binary "Hard Rejection" rules:
*   **SQLi False-Positive Guard**: Automatically rejects SQL Injection reports if the code uses parameterized indicators (`?`, `%s`).
*   **Destructive Fix Guard**: Rejects suggestions that delete logic instead of fixing it (e.g., removing a DB call).
*   **Signal-to-Noise Filter**: Rejects any feedback using vague keywords like "improve", "optimize", or "consider".

### 3. Anti-Hallucination Validator (`validator.py`)
The final safety gate before posting to GitHub:
*   **Identity Check**: Rejects "Suggestions" that are identical to the existing code (prevents GitHub 422 errors).
*   **Auto-Correction**: Intelligently shifts comments to the correct line if the AI reports a slightly misaligned line number based on keyword matching.

### 4. Proximity Deduplication
Prevents "Feedback Loops" where the AI reports the same bug on multiple lines in a block. Issues within a 3-line window with similar descriptions are collapsed into one.

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

### 4. Expose via Tunnel (Recommended: ngrok)

```bash
# Option A: ngrok (Stable)
ngrok http 8001

# Option B: localtunnel
npx -y localtunnel --port 8001
```

### 5. Configure GitHub Webhook

1. Go to your GitHub repo → **Settings** → **Webhooks** → **Add webhook**
2. **Payload URL:** `https://your-tunnel-url.ngrok-free.app/webhook`

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
GET /            → dashboard UI
```

---

## 📁 Project Structure

```
HCL Project/
├── Dockerfile                   # Production container config (Gunicorn + Uvicorn)
├── docker-compose.yml           # Multi-container orchestration & persistence
├── README.md                    # Comprehensive documentation & setup guide
├── requirements.txt             # Project-wide dependency index
│
├── backend/
│   ├── main.py                  # Webhook pipeline + Real-time Dashboard API
│   ├── stats_store.py           # Atomic SQLite telemetry & history engine
│   ├── reviews.db               # SQLite database (Git ignored)
│   ├── requirements.txt         # Container-specific dependencies
│   ├── .env                     # Secrets (API Keys) — NEVER COMMIT
│   ├── static/
│   │   └── index.html           # Real-time Glassmorphism Dashboard UI
│   └── services/
│       ├── ai_service.py        # Groq LLaMA engine + Proximity Deduplication
│       ├── github_service.py    # GitHub API integration (REST v3)
│       ├── filter_service.py    # Strict Security Filter (SQLi Guard)
│       ├── validator.py         # Anti-Hallucination Variable Cross-checker
│       └── syntax_validator.py  # Local code-correctness verification
└── .gitignore                   # Standard Python + Environment exclusion
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

### 1. AI Integration Test (5-Bug & 1-Bug cases)
Verify that the Groq AI service is correctly analyzing diffs and returning JSON issues.
```bash
# Test 5 diverse bugs
python buggy_code.py

# Test 1 security bug
python single_bug.py

# Internal integration logic test
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
# Ensure ngrok/localtunnel and backend are running first
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
