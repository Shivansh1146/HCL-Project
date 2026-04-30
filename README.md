# ⚡ AI-Powered Pull Request Code Review Assistant

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Groq](https://img.shields.io/badge/Groq_AI-F4AF38?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)

The **HCL Project** is a production-hardened AI-powered GitHub Pull Request Reviewer designed to automate deep code analysis with the precision of a Senior Security Engineer.

Built using **FastAPI**, **Groq LLaMA-3**, and **SQLite**, this system goes beyond simple "AI advice" by enforcing a strict 3-layer validation pipeline to eliminate false positives and provide surgical, one-click fixes.

---

## ✨ Production Hardening (New)

The system has been "hardened" for high-stakes production environments with three critical safety layers:

### 1️⃣ Layer 1: Strict Security Prompting
- **Static Analyzer Mindset**: The AI acts as a senior security reviewer, not a teacher. Generic advice is strictly banned.
- **Minimalist Fixes**: Enforcement of "patch-like" fixes that modify only the targeted line, preserving original logic.

### 2️⃣ Layer 2: Post-AI Strict Filtering
- **SQLi False Positive Guard**: Proactively rejects SQL injection reports if the code already uses parameterized queries.
- **Destructive Fix Guard**: Rejects suggestions that attempt to delete logic instead of fixing it.
- **Proximity Deduplication**: Collapses identical issues found on adjacent lines (within a 3-line window) into a single high-fidelity report.

### 3️⃣ Layer 3: Confidence Kill Switch
- **Large Diff Safety**: If a complex diff (> 3000 chars) returns zero issues, the system marks the PR as `REVIEW_REQUIRED` to prevent silent failures on massive changes.

---

## 🏗️ Architecture

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11 + FastAPI (Async/Non-blocking) |
| **AI Engine** | Groq API (`llama-3.3-70b-versatile`) — 5 concurrent analyses |
| **Integrations** | GitHub REST API (Webhooks + Inline Suggestions) |
| **Persistence** | SQLite (`reviews.db`) — WAL mode enabled for high concurrency |
| **Validator** | Anti-Hallucination Engine with **Keyword Auto-Correction** |
| **Dashboard** | Premium Glassmorphism UI with real-time telemetry |

---

## 🔍 Anti-Hallucination Validator (`validator.py`)

A custom post-processing engine that cross-checks every AI-generated issue against the actual code in the raw git diff before anything is posted to GitHub.

- **Identity Guard**: Rejects suggestions where the "fix" is identical to the existing code (prevents invalid GitHub suggestions).
- **Auto-Mapping Correction**: Uses semantic keyword matching to auto-correct AI line-mapping errors. If the AI reports line 17 but the bug is on line 15, the validator finds it and anchors the comment correctly.

---

## 🛠️ Setup & Deployment

### 1. Clone & Install
```bash
git clone https://github.com/Shivansh1146/hcl-project
cd "HCL Project"
python -m venv .venv
.\.venv\Scripts\activate  # Windows
pip install -r .\backend\requirements.txt
```

### 2. Configure Environment (`backend/.env`)
```env
GROQ_API_KEY=gsk_...
GITHUB_TOKEN=github_pat_...
```

### 3. Docker Deployment (Recommended)
The system is fully containerized for production consistency.
```bash
docker-compose up --build -d
```

---

## 📁 Project Structure

```
HCL Project/
├── Dockerfile                   # Production container config
├── docker-compose.yml           # Service orchestration & persistence
├── README.md                    # Project documentation
├── backend/
│   ├── main.py                  # FastAPI app — Hardened webhook pipeline
│   ├── stats_store.py           # Atomic SQLite telemetry engine
│   ├── reviews.db               # SQLite database
│   ├── static/
│   │   └── index.html           # Live SaaS Dashboard
│   ├── services/
│   │   ├── ai_service.py        # Proximity Dedup + Security Prompting
│   │   ├── filter_service.py    # Multi-layer safety filters
│   │   ├── validator.py         # Anti-hallucination variable checker
│   │   └── github_service.py    # GitHub REST integration
│   └── requirements.txt         # Production dependencies
└── .gitignore
```

---

## 👤 Author

**Shivansh**
- GitHub: [Shivansh1146](https://github.com/Shivansh1146)
- Project: [HCL Project](https://github.com/Shivansh1146/hcl-project)

*Built with Python · FastAPI · Groq · GitHub REST API*
