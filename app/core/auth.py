"""
OAuth2 authentication and credential management for Gmail.
Automatically saves credentials to PostgreSQL.
"""

import os
import asyncio
from typing import Optional
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from app.core.database import SessionLocal, GmailUser
from datetime import datetime, timedelta

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
CREDENTIALS_PATH = "credentials.json"
DEFAULT_OAUTH_REDIRECT_URI = "http://127.0.0.1:8000/auth/callback"


async def get_oauth_flow():
    """Create OAuth2 flow."""
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"{CREDENTIALS_PATH} not found. Download it from Google Cloud Console."
        )
    
    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_PATH,
        SCOPES,
    )
    return flow


async def save_credentials_to_db(email: str, creds: Credentials):
    """Save Gmail credentials to PostgreSQL."""
    db = SessionLocal()
    try:
        # Check if user exists
        user = db.query(GmailUser).filter(GmailUser.email == email).first()
        refresh_token = creds.refresh_token
        
        if user:
            # Update existing user
            user.refresh_token = refresh_token or user.refresh_token
            user.access_token = creds.token
            user.token_expiry = datetime.fromtimestamp(creds.expiry.timestamp()) if creds.expiry else None
            user.updated_at = datetime.utcnow()
        else:
            if not refresh_token:
                raise ValueError("Google did not return a refresh token. Try connecting again.")
            # Create new user
            user = GmailUser(
                email=email,
                refresh_token=refresh_token,
                access_token=creds.token,
                token_expiry=datetime.fromtimestamp(creds.expiry.timestamp()) if creds.expiry else None,
            )
            db.add(user)
        
        db.commit()
        print(f"✓ Credentials saved for {email}")
        return user
    except Exception as e:
        db.rollback()
        print(f"ERROR saving credentials: {e}")
        raise
    finally:
        db.close()


async def get_credentials_from_db(email: str) -> Credentials:
    """Retrieve and refresh credentials from PostgreSQL."""
    db = SessionLocal()
    try:
        user = db.query(GmailUser).filter(GmailUser.email == email).first()
        
        if not user:
            raise ValueError(f"No credentials found for {email}")
        
        # Reconstruct Credentials object
        creds = Credentials(
            token=user.access_token,
            refresh_token=user.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=await get_client_id(),
            client_secret=await get_client_secret(),
            expiry=user.token_expiry,
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            try:
                await asyncio.to_thread(creds.refresh, Request())
            except RefreshError as exc:
                raise ValueError("Gmail connection expired. Connect Gmail again.") from exc
            await save_credentials_to_db(email, creds)
        
        return creds
    finally:
        db.close()


async def get_client_id():
    """Extract client_id from credentials.json."""
    import json
    with open(CREDENTIALS_PATH) as f:
        data = json.load(f)
        return data.get("installed", {}).get("client_id")


async def get_client_secret():
    """Extract client_secret from credentials.json."""
    import json
    with open(CREDENTIALS_PATH) as f:
        data = json.load(f)
        return data.get("installed", {}).get("client_secret")


from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

OAUTH_STATE: dict[str, str] = {}


def oauth_redirect_uri() -> str:
    """Return the browser callback URL used for local frontend OAuth."""
    return os.getenv("GOOGLE_OAUTH_REDIRECT_URI", DEFAULT_OAUTH_REDIRECT_URI)


def allow_local_oauth_http() -> None:
    """Allow OAuth callbacks over localhost HTTP during local development."""
    redirect_uri = oauth_redirect_uri()
    if redirect_uri.startswith("http://127.0.0.1") or redirect_uri.startswith("http://localhost"):
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


async def build_oauth_authorization_url(redirect_uri: Optional[str] = None) -> tuple[str, str]:
    """Create a Google OAuth URL for browser-based login."""
    allow_local_oauth_http()
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_PATH,
        scopes=SCOPES,
        redirect_uri=redirect_uri or oauth_redirect_uri(),
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    OAUTH_STATE[state] = flow.code_verifier
    return authorization_url, state


async def complete_oauth_callback(
    authorization_response: str,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
):
    """Exchange Google's callback code for tokens and save them."""
    try:
        allow_local_oauth_http()
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_PATH,
            scopes=SCOPES,
            state=state,
            redirect_uri=redirect_uri or oauth_redirect_uri(),
        )
        if state:
            code_verifier = OAUTH_STATE.pop(state, None)
            if code_verifier:
                flow.code_verifier = code_verifier
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials

        gmail_service = build(
            "gmail",
            "v1",
            credentials=creds,
            cache_discovery=False,
        )

        try:
            profile = gmail_service.users().getProfile(userId="me").execute()
        except HttpError as e:
            raise RuntimeError(
                "Google login succeeded, but this account does not appear to have Gmail enabled."
            ) from e

        email = profile.get("emailAddress")
        if not email:
            raise RuntimeError("Google login succeeded, but Gmail did not return an email address.")

        await save_credentials_to_db(email, creds)
        return email, creds

    except Exception as e:
        raise RuntimeError(f"Gmail connection failed: {e}") from e


async def authenticate_user_oauth():
    """Run user OAuth flow and save Gmail credentials."""
    try:
        flow = await get_oauth_flow()

        creds = flow.run_local_server(
            port=8080,
            access_type="offline",
            prompt="consent",
        )

        gmail_service = build(
            "gmail",
            "v1",
            credentials=creds,
            cache_discovery=False,
        )

        try:
            profile = gmail_service.users().getProfile(userId="me").execute()
        except HttpError as e:
            raise RuntimeError(
                "Google login succeeded, but this account does not appear to have Gmail enabled."
            ) from e

        email = profile.get("emailAddress")

        await save_credentials_to_db(email, creds)

        return email, creds

    except Exception as e:
        raise RuntimeError(f"Gmail connection failed: {e}") from e



