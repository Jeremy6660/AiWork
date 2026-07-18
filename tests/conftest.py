import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def force_offline_deterministic_mode(monkeypatch):
    """自动化测试永不因本机 .env 而产生真实 API 调用。"""

    monkeypatch.setenv("GENERATION_MODE", "offline")
    monkeypatch.setenv("ENABLE_LLM_REVIEW", "0")
    monkeypatch.setenv("ENABLE_L3_VOTING", "0")
    monkeypatch.setenv("ALLOW_OFFLINE_FALLBACK", "1")
