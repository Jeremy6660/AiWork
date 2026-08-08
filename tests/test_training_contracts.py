import pytest

from src.zhice_yuxun.contracts import (
    ContractError,
    validate_learning_scene,
    validate_training_content_optional,
    validate_training_task,
)


def _valid_training_task() -> dict:
    return {
        "任务包ID": "TASK-CNC-001",
        "岗位": "数控机床操作工",
        "任务名称": "上岗前安全检查",
        "适用范围": {"设备": "CNC 机床"},
        "前置技能": ["安全防护"],
        "知识ID": ["CNC-SAFE-001"],
        "学习目标": [
            {"行为": "完成检查", "条件": "上机前", "标准": "无遗漏"}
        ],
        "操作步骤": [
            {
                "序号": 1,
                "操作": "检查防护门",
                "判定标准": "闭合到位",
                "异常处理": "停止上机并报修",
                "引用知识ID": ["CNC-SAFE-001"],
            }
        ],
        "常见错误": [],
        "练习任务": {"任务": "复述检查顺序"},
        "考核": {"方式": "现场操作"},
        "验证状态": "已核验",
        "版本": "1.0",
        "来源缺口": [],
    }


def test_valid_training_task_passes():
    task = _valid_training_task()

    assert validate_training_task(task) is task


def test_training_task_allows_omitted_optional_fields():
    task = {"任务包ID": "TASK-CNC-001", "岗位": "数控机床操作工"}

    assert validate_training_task(task) is task


@pytest.mark.parametrize("missing_key", ["行为", "条件", "标准"])
def test_training_task_rejects_incomplete_learning_objective(missing_key):
    task = _valid_training_task()
    del task["学习目标"][0][missing_key]

    with pytest.raises(ContractError, match="行为、条件、标准"):
        validate_training_task(task)


def test_training_task_rejects_step_without_judgement_standard():
    task = _valid_training_task()
    del task["操作步骤"][0]["判定标准"]

    with pytest.raises(ContractError, match="判定标准"):
        validate_training_task(task)


def test_training_task_rejects_unknown_validation_status():
    task = _valid_training_task()
    task["验证状态"] = "已验证"

    with pytest.raises(ContractError, match="草稿或已核验"):
        validate_training_task(task)


def test_old_training_content_passes_optional_validation():
    content = {
        "类型": "定制讲义",
        "标题": "安全检查",
        "正文": "旧版正文",
        "引用来源": ["操作手册"],
        "引用知识ID": ["CNC-SAFE-001"],
        "生成模式": "离线确定性",
    }

    assert validate_training_content_optional(content) is content


def test_structured_training_content_passes_optional_validation():
    content = {
        "学习目标": [{"行为": "完成检查"}],
        "适用条件": {"经验水平": "首次上岗"},
        "教学步骤": [{"序号": 1}],
        "常见错误": [{"错误": "遗漏检查"}],
        "练习任务": {"任务": "模拟检查"},
        "考核": {"方式": "观察"},
        "补学建议": ["重学安全检查"],
    }

    assert validate_training_content_optional(content) is content


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("学习目标", ["非字典"]),
        ("适用条件", []),
        ("教学步骤", {}),
        ("常见错误", [1]),
        ("练习任务", []),
        ("考核", "及格"),
        ("补学建议", [1]),
    ],
)
def test_structured_training_content_rejects_invalid_optional_field(
    field, invalid_value
):
    with pytest.raises(ContractError, match=field):
        validate_training_content_optional({field: invalid_value})


def test_learning_scene_allows_empty_optional_fields():
    assert validate_learning_scene({}) == {}
    assert validate_learning_scene({"经验水平": "", "可用时长分钟": None})


@pytest.mark.parametrize(
    "scene",
    [
        {"经验水平": "专家"},
        {"可用时长分钟": 0},
        {"可用时长分钟": True},
    ],
)
def test_learning_scene_rejects_invalid_optional_value(scene):
    with pytest.raises(ContractError):
        validate_learning_scene(scene)
