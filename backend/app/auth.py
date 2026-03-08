"""
Google OAuth + session cookie auth for Finance Tracker.
"""
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode
from app.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET,
    ALLOWED_EMAIL, APP_URL
)

COOKIE_NAME = "ft_session"
SESSION_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def build_google_auth_url():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": f"{APP_URL}/auth/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": f"{APP_URL}/auth/callback",
        "grant_type": "authorization_code",
    })
    resp.raise_for_status()
    return resp.json()


def get_user_info(access_token: str) -> dict:
    resp = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={
        "Authorization": f"Bearer {access_token}"
    })
    resp.raise_for_status()
    return resp.json()


def create_session_token(email: str) -> str:
    payload = f"{email}:{int(time.time())}"
    sig = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_session_token(token: str) -> str | None:
    """Returns email if token is valid and not expired, else None."""
    parts = token.split(":")
    if len(parts) != 3:
        return None
    email, ts_str, sig = parts
    try:
        ts = int(ts_str)
    except ValueError:
        return None

    if time.time() - ts > SESSION_MAX_AGE:
        return None

    payload = f"{email}:{ts_str}"
    expected = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None

    if email != ALLOWED_EMAIL:
        return None

    return email


def is_allowed(email: str) -> bool:
    return email == ALLOWED_EMAIL
