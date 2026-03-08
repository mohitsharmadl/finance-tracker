"""
Configuration for Finance Tracker.
Loads settings from environment variables with validation.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ubuntu:straddle123@localhost:5432/finance_tracker")

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# Session - REQUIRED, no default
SESSION_SECRET = os.getenv("SESSION_SECRET", "")

# Auth
ALLOWED_EMAIL = os.getenv("ALLOWED_EMAIL", "mohit@mohitsharma.com")
APP_URL = os.getenv("APP_URL", "https://finance.mohitsharma.com")


def validate_config():
    """
    Validate required configuration on startup.
    Raises RuntimeError if critical settings are missing.
    """
    errors = []

    if not SESSION_SECRET:
        errors.append(
            "SESSION_SECRET is required. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    if SESSION_SECRET and len(SESSION_SECRET) < 32:
        errors.append(
            "SESSION_SECRET is too short (minimum 32 characters). "
            'Generate a secure one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        print("WARNING: Google OAuth credentials not configured. OAuth login will fail.", file=sys.stderr)

    if errors:
        for error in errors:
            print(f"CONFIG ERROR: {error}", file=sys.stderr)
        raise RuntimeError("Configuration validation failed. See errors above.")


# Validate on import (fail fast) — skip in test/dev if not set
import sys as _sys
if "pytest" not in _sys.modules:
    validate_config()
