from copy import deepcopy

import pytest

import src.zhice_yuxun.orchestrator as orchestrator
from src.zhice_yuxun.agents.generator import generate_content as real_generate_content


@pytest.fixture(autouse=True)
def force_offline(monkeypatch):
    monkeypatch.setenv("GENERATION_MODE", "offline")
    monkeypatch.setenv("ENABLE_LLM_REVIEW", "0")
    monkeypatch.setenv("ENABLE_L3_VOTING", "0")
    monkeypatch.delenv("ALLOW_DRAFT_TASKPKG", raising=False)


@pytest.fixture
def verified_taskpkg() -> dict:
    fact = "操作机床时应使用适当的眼部和听力防护用品。"
    return {
        "任务包ID": "TASK-CNC-TEST-001",
        "岗位": "数控机床操作工",
        "任务名称": "个人防护检查",
        "主题": ["个人防护"],
        "适用范围": {
            "设备类型": "通用数控机床",
            "具体型号": "已指定",
            "培训环境": ["仿真"],
            "建议时长分钟": 15,
        },
        "前置技能": ["识别个人防护用品"],
        "知识ID": ["CNC-SAFE-002"],
        "学习目标": [
            {
                "行为": fact,
                "条件": fact,
                "标准": fact,
                "引用知识ID": ["CNC-SAFE-002"],
            }
        ],
        "操作步骤": [
            {
                "序号": index,
                "操作": fact,
                "判定标准": fact,
                "异常处理": fact,
                "引用知识ID": ["CNC-SAFE-002"],
            }
            for index in range(1, 5)
        ],
        "常见错误": [
            {
                "错误": fact,
                "后果": fact,
                "纠正": fact,
                "引用知识ID": ["CNC-SAFE-002"],
            }
        ],
        "练习任务": {
            "任务": "完成个人防护用品识别练习",
            "所需材料": ["防护用品卡片"],
            "完成证据": "提交检查表",
        },
        "考核": {
            "题目": [
                {"题目": "列出眼部防护用品", "标准答案": "护目镜"},
                {"题目": "列出听力防护用品", "标准答案": "耳塞"},
            ],
            "评分规则": ["每题一分"],
            "合格线": "两分",
            "错后补学": [
                {
                    "触发条件": "任一题错误",
                    "补学内容": "复习个人防护用品",
                    "引用知识ID": ["CNC-SAFE-002"],
                }
            ],
        },
        "验证状态": "已核验",
        "版本": "1.0",
        "来源缺口": [],
    }


def test_verified_taskpkg_runs_structured_generation_and_dual_review(
    monkeypatch, verified_taskpkg
):
    monkeypatch.setattr(
        orchestrator, "search_training_task", lambda _position, _question: verified_taskpkg
    )

    result = orchestrator.run(
        "数控机床操作工",
        question="个人防护检查",
        学习场景={
            "经验水平": "首次上岗",
            "设备或工具": "通用数控机床",
            "本次任务": "个人防护检查",
            "可用时长分钟": 15,
        },
    )

    assert result["任务包"] == verified_taskpkg
    assert result["任务包提示"] == ""
    assert len(result["培训内容"]["教学步骤"]) == 4
    assert result["审核通过"] is True
    assert result["事实审核"] == "pass"
    assert result["教学完整性"] == "pass"
    assert result["教学完整率"] == 1.0


def test_taskpkg_miss_keeps_legacy_path(monkeypatch):
    monkeypatch.setattr(
        orchestrator, "search_training_task", lambda _position, _question: None
    )

    result = orchestrator.run("CNC编程员", question="M代码编程")

    assert result["任务包"] is None
    assert result["任务包提示"] == ""
    assert "教学步骤" not in result["培训内容"]
    assert result["教学完整性"] == "未启用"
    assert result["审核通过"] is True


def test_empty_question_skips_taskpkg_search(monkeypatch):
    def fail_if_called(_position, _question):
        raise AssertionError("question 为空时不应检索任务包")

    monkeypatch.setattr(orchestrator, "search_training_task", fail_if_called)

    result = orchestrator.run("质检员", question="")

    assert result["任务包"] is None
    assert result["任务包提示"] == ""
    assert "协同日志" in result


def test_draft_taskpkg_falls_back_to_legacy_content(
    monkeypatch, verified_taskpkg
):
    draft = deepcopy(verified_taskpkg)
    draft["验证状态"] = "草稿"
    monkeypatch.setattr(
        orchestrator, "search_training_task", lambda _position, _question: draft
    )

    result = orchestrator.run("数控机床操作工", question="数控机床安全操作")

    assert result["任务包"] == draft
    assert "尚未完成专业核验" in result["任务包提示"]
    assert "教学步骤" not in result["培训内容"]


def test_teaching_failure_never_passes_overall(
    monkeypatch, verified_taskpkg
):
    monkeypatch.setattr(
        orchestrator, "search_training_task", lambda _position, _question: verified_taskpkg
    )

    def generate_without_objectives(*args, **kwargs):
        content = real_generate_content(*args, **kwargs)
        del content["学习目标"]
        return content

    monkeypatch.setattr(orchestrator, "generate_content", generate_without_objectives)

    result = orchestrator.run(
        "数控机床操作工",
        question="个人防护检查",
        学习场景={"经验水平": "首次上岗"},
    )

    assert result["审核通过"] is False
    assert result["流程状态"] != "通过"
    assert result["事实审核"] == "pass"
    assert result["教学完整性"] == "fail"
    assert "学习目标不能为空" in result["教学问题"]
