#!/usr/bin/env python3
"""
generate_token.py — manually obtain OAuth token.json for YouTube Data API.
Requires: pip install google-auth google-auth-oauthlib google-api-python-client
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os, json

SCOPES = ["https://www.googleapis.com/auth/youtube"]

os.makedirs("tools", exist_ok=True)
flow = InstalledAppFlow.from_client_secrets_file(
    "tools/client_secret.json", SCOPES
)

creds = flow.run_local_server(port=0)
token_path = "tools/token.json"

with open(token_path, "w") as f:
    json.dump({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
        "universe_domain": "googleapis.com",
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }, f, indent=2)

print(f"✅ Token saved to {token_path}")
