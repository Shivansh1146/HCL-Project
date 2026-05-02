# ⚡ AI-Powered Pull Request Code Review Assistant (HCL Project)

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Groq](https://img.shields.io/badge/Groq_AI-F4AF38?style=for-the-badge)
![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)

The **HCL Project** is a production-grade, AI-powered GitHub Pull Request Reviewer designed for high-fidelity security analysis and deterministic code verification. Built with a "Zero-Noise" philosophy, it empowers teams with automated, committable suggestions while maintaining a rigorous security posture.

---

## ✨ Production-Grade Features

- **🛡️ Iron-Clad Deterministic Engine**: Multi-layered filtering that rejects LLM hallucinations (e.g., binary search logic errors) and ensures 100% accurate suggestions.
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
| **AI Intelligence** | Groq (LLaMA 3.3 70B) | Security-optimized analysis with ultra-low latency inference. |
| **Hardening** | `filter_service.py` | Literal blacklist and structural guards for iron-clad reliability. |
| **Persistence** | SQLite (`reviews.db`) | Atomic state management with WAL mode for concurrency. |
| **Observability** | Vanilla CSS/JS | Minimalist, high-performance UI with real-time state synchronization. |

---

## 🚀 Quick Start (Deployment)

### 1. Cloud Deployment (Render)
The project is pre-configured for Render.
1. Connect this repository to **Render**.
2. Add the following Environment Variables in the Render Dashboard:
   - `GITHUB_TOKEN`: Your GitHub Personal Access Token.
   - `GROQ_API_KEY`: Your Groq API Key.
   - `WEBHOOK_SECRET`: Your custom webhook secret.
3. Render will automatically use the `render.yaml` blueprint to build and deploy.

### 2. Local Setup (Docker)
```bash
# Build and run with persistence
docker-compose up --build -d
```
Access the dashboard at `http://localhost:8000`.

---

## 🛠️ Local Development

### 1. Environment Setup
Create `backend/.env`:
```env
GROQ_API_KEY=gsk_...
GITHUB_TOKEN=ghp_...
WEBHOOK_SECRET=your_secret
PORT=8000
```

### 2. Launching the System
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

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
│       ├── filter_service.py    # Iron-Clad Logic & Content Guards
│       └── validator.py         # Anti-Hallucination Cross-Checker
```

---

## 👤 Author

**Shivansh**
- GitHub: [Shivansh1146](https://github.com/Shivansh1146)
- Project: [HCL Project](https://github.com/Shivansh1146/hcl-project)

---

*Built with Python · FastAPI · Groq · GitHub REST API*
