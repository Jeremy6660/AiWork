import json

import pytest

from src.zhice_yuxun.agents.retrieval import search_training_task
from src.zhice_yuxun.paths import DATA_DIR


GOLDEN_TASK_ID = "TASK-CNC-SAFE-CHECK-001"
POSITION = "数控机床操作工"


def _golden_task() -> dict:
    raw = json.loads((DATA_DIR / "training_tasks.json").read_text(encoding="utf-8"))
    tasks = raw if isinstance(raw, list) else [raw]
    return next(task for task in tasks if task["任务包ID"] == GOLDEN_TASK_ID)


def test_position_and_task_name_return_complete_golden_task():
    result = search_training_task(POSITION, "开机前安全检查怎么做")

    assert result == _golden_task()
    assert result["任务包ID"] == GOLDEN_TASK_ID
    assert result["验证状态"] == "草稿"


def test_task_alias_matches_golden_task():
    result = search_training_task(POSITION, "开机安全检查")

    assert result is not None
    assert result["任务包ID"] == GOLDEN_TASK_ID


@pytest.mark.parametrize(
    "question",
    ["数控机床换刀怎么做", "核电站操作规程"],
)
def test_uncovered_or_cross_domain_question_returns_none(question):
    assert search_training_task(POSITION, question) is None


def test_other_position_never_receives_training_task():
    assert search_training_task("质检员", "开机前安全检查怎么做") is None


@pytest.mark.parametrize(
    ("position", "question"),
    [
        ("", "开机检查"),
        ("   ", "开机检查"),
        (None, "开机检查"),
        (3, "开机检查"),
        (POSITION, ""),
        (POSITION, "   "),
        (POSITION, None),
        (POSITION, 3),
    ],
)
def test_invalid_input_is_rejected(position, question):
    with pytest.raises(ValueError):
        search_training_task(position, question)
