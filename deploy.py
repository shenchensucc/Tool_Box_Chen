#!/usr/bin/env python3
"""
Deploy Chen's Engineer Toolbox to ai-builders.space
Run: python deploy.py
Requires: AI_BUILDER_TOKEN in environment or .env file
"""
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOKEN = os.getenv("AI_BUILDER_TOKEN")
if not TOKEN:
    print("ERROR: AI_BUILDER_TOKEN not set.")
    print("Set it in .env or: $env:AI_BUILDER_TOKEN='your-token'  (PowerShell)")
    print("Get your token from the AI Builders platform.")
    sys.exit(1)

import httpx

# AI Builders Space API — base URL from platform (same as MCP user-ai-builders-coach get_base_url)
_api_base = os.getenv("AI_BUILDERS_BASE_URL", "https://space.ai-builders.com/backend").rstrip("/")
url = f"{_api_base}/v1/deployments"
payload = {
    "repo_url": "https://github.com/shenchensucc/Tool_Box_Chen",
    "service_name": "tool-box-chen",
    "branch": "main",
    "port": 8000,
    "streaming_log_timeout_seconds": 30,
}

resp = httpx.post(
    url,
    json=payload,
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    timeout=60,
)

if resp.status_code == 202:
    data = resp.json()
    print("Deployment queued successfully!")
    print(f"Service: {data.get('service_name', 'tool-box-chen')}")
    print(f"URL: https://tool-box-chen.ai-builders.space")
    print("\nProvisioning takes 5-10 minutes. Check status at:")
    print(f"{_api_base}/v1/deployments/tool-box-chen")
    if data.get("streaming_logs"):
        print("\n--- Build logs ---")
        print(data["streaming_logs"])
else:
    print(f"Deployment failed: {resp.status_code}")
    print(resp.text)
    sys.exit(1)
