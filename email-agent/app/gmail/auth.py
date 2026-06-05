import json
import secrets

from google_auth_oauthlib.flow import Flow
from app.config import settings
from datetime import datetime

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _build_flow():
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [f"{settings.app_url}/auth/gmail/callback"],
            }
        },
        scopes=SCOPES,
    )


def get_auth_url(email: str) -> str:
    flow = _build_flow()
    flow.redirect_uri = f"{settings.app_url}/auth/gmail/callback"
    code_verifier = secrets.token_urlsafe(32)
    flow.code_verifier = code_verifier
    state = json.dumps({"email": email, "cv": code_verifier})
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline", state=state)
    return auth_url


def exchange_code(code: str, state: str) -> tuple[str, str, datetime]:
    state_data = json.loads(state)
    code_verifier = state_data.get("cv")
    flow = _build_flow()
    flow.redirect_uri = f"{settings.app_url}/auth/gmail/callback"
    flow.fetch_token(code=code, code_verifier=code_verifier)
    creds = flow.credentials
    return creds.refresh_token, creds.token, creds.expiry
