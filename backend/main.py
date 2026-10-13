"""
Top-level entry point for the FastAPI backend.
Delegates to backend.app.main.
"""
import sys
from pathlib import Path

# Ensure 'lamit' directory is on sys.path so 'backend.app...' works regardless of CWD
_lamit_dir = str(Path(__file__).resolve().parent.parent)
if _lamit_dir not in sys.path:
    sys.path.insert(0, _lamit_dir)

from backend.app.main import app, main, create_app

__all__ = ["app", "main", "create_app"]

if __name__ == "__main__":
    main()
