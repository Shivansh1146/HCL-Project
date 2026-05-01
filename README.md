# ⚡ AI-Powered Pull Request Code Review Assistant (Hardened Production Edition)

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Groq](https://img.shields.io/badge/Groq_AI-F4AF38?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)

The **HCL Project** is an enterprise-grade, deterministic AI Pull Request Reviewer. Unlike standard AI reviewers that "guess," this system uses a multi-layered hardening pipeline to ensure **zero noise**, **zero hallucinations**, and **surgical accuracy**.

The system is optimized for production stability, providing a "silent success" experience—only flagging real, exploitable bugs while verifying perfect code with a professional green checkmark.

---

## ✨ Key Features

- **🛡️ Deterministic Rejection Engine**: Rejects common LLM hallucinations regarding binary search, search spaces, and "off-by-one" nitpicks.
- **🔍 4-Layer Hardening Pipeline**:
    - **Content Guard**: Protects your comments, docstrings (`"""`), and structural keywords (`else:`, `def`) from being overwritten by AI logic.
    - **Syntax Guard**: Every AI suggestion is parsed via `ast.parse`. If the AI suggests broken code or plain text, it is instantly discarded.
    - **Literal Blacklist**: Hard-coded rejection of pedantic nitpicks like "pivot selection" or "median of three" in standard algorithms.
    - **Stability Stop**: Database-backed SHA fingerprinting prevents redundant reports across multiple commits.
- **✅ PERFECT Status • ZERO RISK**: For flawless code, the system returns a **"ZERO RISK • VERIFIED"** status on the dashboard and a **Green Checkmark** on GitHub.
- **📊 Glassmorphism Dashboard**: A premium, real-time command center showing PR health, spectral severity metrics, and deterministic decision telemetry.
- **✨ GitHub Suggestions UI**: Automatically posts native ````suggestion` syntax for one-click fixes directly on the Pull Request.

---

## 🏗️ Architecture & Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Python 3.11 + FastAPI | Core API and high-performance asynchronous background processing. |
| **AI Engine** | Groq (`llama-3.1-8b`) | Highly deterministic inference using a strict 10-rule system prompt. |
| **Filter Layer** | `filter_service.py` | Literal blacklist for algorithmic nitpicks and pedantic hallucinations. |
| **Safety Layer** | `main.py` (Guards) | Cross-checks AI suggestions against code structure and syntax integrity. |
| **Persistence** | SQLite (`reviews.db`) | WAL-mode database for atomic state tracking and SHA fingerprinting. |
| **Dashboard** | Vanilla HTML/JS/CSS | Real-time observability with zero-flicker state management and premium aesthetics. |

---

## 🛡️ Production Decision Logic

The system follows a fail-closed, deterministic logic to ensure the highest fidelity reviews:

- **PERFECT**: 0 issues found. Triggers **Green Checkmark ✅** and **"ZERO RISK"** UI.
- **SAFE**: Only low-severity or minor quality improvements. Triggers **Green Checkmark ✅** and **"SAFE TO MERGE"** UI.
- **REVIEW_REQUIRED**: Significant logic or security issues detected. Triggers **Yellow Warning ⚠️**.
- **BLOCK**: Critical vulnerabilities (SQLi, RCE, Secrets). Triggers **Red X ❌**.

---

## 🛠️ Setup & Deployment

### 1. Environment Configuration
Create `backend/.env`:
```env
GROQ_API_KEY=gsk_...         # From console.groq.com
GITHUB_TOKEN=github_pat_...  # Needs 'repo' scope
```

### 2. Docker Deployment (Recommended)
The system is fully containerized with persistent volumes for history.
```bash
# Start the entire stack
docker-compose up --build -d

# View real-time telemetry logs
docker logs -f hclproject-ai-reviewer-1
```

### 3. Webhook Configuration
1. **Payload URL:** `https://your-tunnel.app/webhook`
2. **Content type:** `application/json`
3. **Events:** Select **Pull requests** only.

---

## 📁 Project Structure

```
HCL Project/
├── Dockerfile                   # Hardened container environment
├── docker-compose.yml           # Orchestration & Volume persistence
├── backend/
│   ├── main.py                  # Core Engine, Decision Logic & Content Guards
│   ├── stats_store.py           # Atomic Telemetry & SHA Fingerprinting
│   ├── static/index.html        # Premium Real-time Dashboard
│   └── services/
│       ├── ai_service.py        # Deterministic Prompting & Retry Logic
│       ├── filter_service.py    # Iron-Clad Literal Blacklist & Nitpick Filters
│       ├── github_service.py    # High-fidelity GitHub REST Integration
│       └── syntax_validator.py  # Zero-Tolerance Python Syntax Verification
```

---

## ✅ Production Readiness
- **Fail-Safe**: Any API error or rate-limit results in a silent "Analysis Incomplete" state rather than an incorrect approval.
- **Observability**: Real-time Gunicorn logs track every "Content Guard" and "Iron-Clad Rejection" decision.
- **Zero-Noise**: Tuned to return 0 issues on perfect implementations of standard algorithms (Binary Search, Sorting, Tree Traversal).

---

## 👤 Author

**Shivansh**
- GitHub: [Shivansh1146](https://github.com/Shivansh1146)
- Project: [HCL Project](https://github.com/Shivansh1146/hcl-project)

*Built with Precision · Hardened for Production · Powered by Groq*
