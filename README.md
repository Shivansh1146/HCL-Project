# ⚡ AI-Powered Pull Request Code Review Assistant (HCL Project)

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Groq](https://img.shields.io/badge/Groq_AI-F4AF38?style=for-the-badge)
![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)

The **HCL Project** is a production-grade, AI-powered GitHub Pull Request Reviewer designed for high-fidelity security analysis and deterministic code verification. Built with a "Zero-Noise" philosophy, it empowers teams with automated, committable suggestions while maintaining a rigorous security posture.

---

## ✨ Production-Grade Features

- **🛡️ Iron-Clad Deterministic Engine**: Multi-layered filtering that rejects LLM hallucinations (e.g., binary search logic errors) and ensures multi-layer validated suggestions.
- **🛡️ Content Guard & Syntax Guard**: Permanent protection that prevents the AI from suggesting changes to comments, docstrings, or structural keywords. Any malformed code suggestion is automatically discarded.
- **💎 PERFECT Status Mapping**: Flawless code is recognized as **"ZERO RISK • VERIFIED,"** triggering an automatic success status (Green Checkmark) on GitHub.
- **🧪 Stability Stop (Fingerprinting)**: Prevents redundant reports by tracking issue fingerprints across commits, ensuring the dashboard remains clean and focused.
- **📊 Real-Time Glassmorphism Dashboard**: A premium, state-aware Command Center with live telemetry, spectral severity metrics, and instant decision intelligence.
- **⚡ One-Click Fixes**: Automatically posts native ````suggestion` syntax to GitHub, allowing developers to apply fixes directly from the PR interface.

---

## 🏗️ Technical Architecture

| Layer | Technology | Purpose |
|---|---|---|
| **Cloud Hosting** | Render (Blueprint) | Automated CI/CD deployment with dynamic port binding and persistent state. |
| **Backend** | FastAPI (Python 3.11) | High-performance, asynchronous orchestration engine. |
| **AI Engine** | Groq (LLaMA 3.3 70B) | Security-focused analysis with deterministic temperature (0.1). |
| **Hardening** | `filter_service.py` | Literal blacklist and structural guards for iron-clad reliability. |
| **Persistence** | SQLite (`reviews.db`) | Atomic state tracking with WAL mode for concurrency control. |
| **Dashboard** | Vanilla CSS/JS | Minimalist, high-performance UI with real-time state synchronization. |

---

## 🚀 Cloud Deployment (Render)

1. Connect this repository to **Render** via the dashboard.
2. Render will automatically detect the `render.yaml` blueprint.
3. Configure the following **Environment Variables**:
   - `GITHUB_TOKEN`: Your GitHub Personal Access Token.
   - `GROQ_API_KEY`: Your Groq API Key.
   - `WEBHOOK_SECRET`: Your custom webhook secret.
4. The system will deploy automatically and provide a public URL.

---

## 🛠️ Local Setup & Development

### 1. Installation
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
GROQ_API_KEY=gsk_...
GITHUB_TOKEN=ghp_...
WEBHOOK_SECRET=your_secret
PORT=8000
```

### 3. Launching the System
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
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
├── Dockerfile                   # Hardened Production Image Config
├── docker-compose.yml           # Local Orchestration & Persistence
├── backend/
│   ├── main.py                  # Webhook Pipeline & Decision Intelligence
│   ├── stats_store.py           # Atomic Telemetry Engine
│   ├── static/index.html        # Glassmorphism Command Center UI
│   └── services/
│       ├── ai_service.py        # Groq LLaMA Engine + Hardening Guards
│       ├── diff_validator.py    # Diff Parsing & Line Mapping
│       ├── filter_service.py    # Iron-Clad Logic & Content Guards
│       ├── github_service.py    # GitHub API Integration & Rate Limiting
│       ├── syntax_validator.py  # Local Code-Correctness Verification
│       └── validator.py         # Anti-Hallucination Cross-Checker
```

---

## 🔐 Security & Safety Notes

- **Secrets**: All API keys are stored in `.env` and are strictly excluded from version control.
- **Non-Destructive**: The AI is programmed to never delete code blocks; it only suggests surgical line-level fixes.
- **Fail-Safe**: If the AI engine is unreachable or returns malformed data, the system defaults to `REVIEW_REQUIRED` to prevent unsafe approvals.

---

## 👤 Author

**Shivansh**
- GitHub: [Shivansh1146](https://github.com/Shivansh1146)
- Project: [HCL AI Code Reviewer](https://github.com/Shivansh1146/hcl-project)

---

*Built with Python · FastAPI · Groq · GitHub REST API · Optimized for Production*
