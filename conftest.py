"""Pytest configuration — adds waa/ to sys.path so `from app.xxx` works."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "waa"))
