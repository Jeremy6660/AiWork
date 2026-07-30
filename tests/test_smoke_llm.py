import os
import subprocess
import sys
from pathlib import Path

import scripts.smoke_llm as smoke_llm


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_smoke_default_is_zero_call_dry_run(monkeypatch, capsys):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key-never-used")
    monkeypatch.setattr(
        smoke_llm,
        "call_llm_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run 不得调用模型")
        ),
    )

    exit_code = smoke_llm.main(
        ["--provider", "deepseek", "--scenario", "generate"]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "预计逻辑调用次数：0" in output
    assert "未发起任何网络请求" in output
    assert "fake-key-never-used" not in output


def test_smoke_execute_without_key_is_blocked_before_client(monkeypatch, capsys):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(
        smoke_llm,
        "call_llm_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("无 Key 不得创建调用")
        ),
    )

    exit_code = smoke_llm.main(
        ["--provider", "deepseek", "--scenario", "generate", "--execute"]
    )

    assert exit_code == 2
    assert "未配置 DEEPSEEK_API_KEY" in capsys.readouterr().out


def test_test_run_stays_offline_even_when_fake_key_exists():
    env = os.environ.copy()
    env["DEEPSEEK_API_KEY"] = "fake-key-never-used"
    env["GENERATION_MODE"] = "auto"
    env["PYTHONUTF8"] = "1"

    completed = subprocess.run(
        [sys.executable, "test_run.py"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "离线确定性" in completed.stdout
    assert "离线降级" not in completed.stdout
