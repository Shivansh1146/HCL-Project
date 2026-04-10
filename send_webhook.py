import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load backend/.env so local runs work without shell exports.
ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / "backend" / ".env", override=False)

payload = {
    "action": "synchronize",
    "pull_request": {
        "number": 31,
        "head": {"sha": f"manual-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"},
        "base": {"repo": {"owner": {"login": "Shivansh1146"}, "name": "HCL-Project"}},
    },
    "repository": {
        "owner": {"login": "Shivansh1146"},
        "name": "HCL-Project",
        "full_name": "Shivansh1146/HCL-Project",
    },
}

webhook_url = os.getenv("WEBHOOK_URL", "http://localhost:8000/webhook")
webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
payload_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

if webhook_secret:
    digest = hmac.new(webhook_secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    signature = f"sha256={digest}"
else:
    # Backend requires header; when secret is unset, value is not validated.
    signature = "sha256=dev-placeholder"

headers = {"X-Hub-Signature-256": signature, "Content-Type": "application/json"}
response = requests.post(webhook_url, data=payload_body, headers=headers, timeout=20)

print(f"POST {webhook_url}")
print(response.status_code)
print(response.json())
