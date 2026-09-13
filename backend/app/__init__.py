"""Load settings from a .env file (if present) before anything reads os.environ.

Looked for at backend/.env first, then at the repo root. Docker Compose reads the root .env
by itself; this makes `uvicorn app.main:app` behave the same way.
"""
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv not installed: environment variables still work
    load_dotenv = None

if load_dotenv:
    _here = Path(__file__).resolve().parent
    for _candidate in (_here.parent / ".env", _here.parent.parent / ".env"):
        if _candidate.is_file():
            load_dotenv(_candidate, override=False)
            break
