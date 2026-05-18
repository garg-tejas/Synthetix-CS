"""Test suite for RAG system."""

from pathlib import Path

from dotenv import load_dotenv

# Load .env before any test imports that read environment variables
_env_path = Path(__file__).resolve().parents[1] / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)

