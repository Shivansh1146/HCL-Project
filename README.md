# 🚀 AI Code Review Assistant

A production-ready, full-stack AI-powered Code Review assistant that seamlessly integrates into GitHub workflows. This system hooks into Pull Request webhooks, reads code diffs securely, processes them via OpenAI's language models acting as a strict Senior Security Engineer, rigorously scores the AI's feedback, and intelligently annotates your PR natively via inline comments!

## ✨ Core Features
- **🤖 Autonomous AI Engineer**: Analyzes PR patches via `gpt-4o-mini` with strict security constraints (banning aesthetic/stylistic noise, enforcing precise vulnerability isolation).
- **📝 Native Inline Comments**: Uses the native GitHub API to pinpoint exact line numbers across specific files within your codebase, avoiding generic massive "dump" chat logs.
- **🛡️ Quality Control Scoring Engine**: Filters AI responses actively, penalizing vague adjectives (e.g., "improve", "optimize") and assigning a `+2` multiplier to explicit HIGH severity architectural bugs.
- **🔄 Smart Commit SHA Deduplication**: Validates incoming GitHub payloads instantly against volatile processed hashes to block API-limit-draining comment spam.
- **🔪 Advanced Chunking & Semantic Deduplication**: Defeats OpenAI API character limits by cleanly chopping massive PR diffs natively, and leverages semantic word-overlap checks to perfectly merge overlapping vulnerability warnings.
- **🌐 Web UI Framework**: Contains a modular vanilla HTML/JS/CSS frontend to act as a standalone gateway for isolated evaluations without needing native GitHub PR integration.

## 📦 Repository Architecture
```text
hcl-project/
 ┣ 📂 backend
 ┃ ┣ 📂 services
 ┃ ┃ ┣ 📜 ai_service.py       # OpenAI pipeline, diff chunking, and semantic matching
 ┃ ┃ ┣ 📜 filter_service.py   # Heuristic logic filtering and weak-description blocking
 ┃ ┃ ┗ 📜 github_service.py   # Webhook extraction, patch compilation, & GitHub commenting
 ┃ ┣ 📂 utils
 ┃ ┃ ┗ 📜 formatter.py        # Secure Markdown synthesis for generic & inline PR layouts
 ┃ ┣ 📜 main.py               # 10-Stage FastAPI webhook gateway intercepting GitHub POSTs
 ┃ ┣ 📜 requirements.txt
 ┃ ┗ 📜 .env
 ┣ 📂 frontend
 ┃ ┣ 📜 index.html
 ┃ ┣ 📜 script.js
 ┃ ┗ 📜 style.css
 ┗ 📜 README.md
```

## 🛠️ Quick Start Guide

### 1. Set Up Your Environment
Launch your terminal and create a `.env` file within the `backend/` directory harboring your valid secret credentials:
```env
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
```

### 2. Install Dependencies
Initialize a sterile virtual environment and install the FastAPI tracking requirements.
```powershell
python -m venv venv
.\venv\Scripts\activate
cd backend
pip install -r requirements.txt
```

### 3. Spin Up the FastAPI Backend
Initialize the standard backend gateway pipeline natively:
```powershell
python -m uvicorn main:app --reload --port 8001
```

### 4. Enable Webhook Routing
To permit GitHub to push webhook events directly into your locally running machine, spin up localtunnel:
```powershell
npx -y localtunnel --port 8001
```

## 🔌 Securing the GitHub Integration
1. Copy the `localtunnel` URL dynamically generated (e.g., `https://shaky-doodles-kneel.loca.lt`).
2. Navigate to your target **GitHub Repository** -> **Settings** -> **Webhooks** -> **Add webhook**.
3. Set **Payload URL** to `https://<YOUR_URL>.loca.lt/webhook`.
4. Set **Content type** to `application/json`.
5. Under triggers, click **"Let me select individual events"**, actively check **Pull requests**, and click **Save**.

## 🔥 Live Validation Testing
Ready to watch it work?
Check out a new Git branch and introduce critical (simulated) failures to any file:
```python
password = "123456"
query = "SELECT * FROM users WHERE id=" + user_input
```
Open a Pull Request into your tracker, and your assistant will instantaneously parse the event payload, flag the malicious logic, and securely execute an inline comment directly onto the vulnerable lines requiring remediation!
