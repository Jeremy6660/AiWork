from copy import deepcopy

import pytest

from src.zhice_yuxun.agents.generator import generate_content
from src.zhice_yuxun.contracts import ContractError


@pytest.fixture
def profile() -> dict:
    return {
        "岗位": "数控机床操作工",
        "技能掌握度": {"安全检查": 0.3},
        "目标技能": ["安全检查"],
        "推荐难度": "入门",
    }


@pytest.fixture
def knowledge() -> list[dict]:
    return [
        {
            "知识ID": "CNC-SAFE-001",
            "内容": "开机前检查防护门。",
            "来源": "数控机床安全手册",
            "来源定位": "第 1 章",
            "主题": ["安全检查"],
            "验证状态": "已验证",
        },
        {
            "知识ID": "CNC-SAFE-002",
            "内容": "异常时停止启动并上报。",
            "来源": "数控机床安全手册",
            "来源定位": "第 2 章",
            "主题": ["异常处理"],
            "验证状态": "已验证",
        },
    ]


@pytest.fixture
def verified_taskpkg() -> dict:
    return {
        "任务包ID": "TASK-CNC-SAFE-001",
        "岗位": "数控机床操作工",
        "任务名称": "开机前安全检查",
        "适用范围": {
            "设备类型": "带防护门的数控机床",
            "具体型号": "CNC-X1",
            "培训环境": ["仿真", "现场带教"],
            "建议时长分钟": 20,
        },
        "前置技能": ["识别急停按钮"],
        "知识ID": ["CNC-SAFE-001"],
        "学习目标": [
            {
                "行为": "完成开机前检查",
                "条件": "设备未运行时",
                "标准": "检查无遗漏",
                "引用知识ID": ["CNC-SAFE-001"],
            }
        ],
        "操作步骤": [
            {
                "序号": 1,
                "操作": "检查防护门",
                "判定标准": "防护门关闭到位",
                "异常处理": "停止启动并上报",
                "引用知识ID": ["CNC-SAFE-001", "CNC-SAFE-002"],
            }
        ],
        "常见错误": [
            {
                "错误": "跳过防护门检查",
                "后果": "无法确认防护状态",
                "纠正": "重新执行步骤1",
                "引用知识ID": ["CNC-SAFE-001"],
            }
        ],
        "练习任务": {
            "任务": "完成一次模拟检查",
            "所需材料": ["检查表", "情境卡"],
            "完成证据": "提交填写完整的检查表",
        },
        "考核": {
            "题目": [{"题目": "开机前首先检查什么？"}],
            "合格线": "安全关键项全部正确",
            "错后补学": [
                {
                    "触发条件": "防护门检查题答错",
                    "补学内容": "重学防护门检查要求",
                    "引用知识ID": ["CNC-SAFE-001"],
                }
            ],
        },
        "验证状态": "已核验",
        "版本": "1.0",
        "来源缺口": [],
    }


def test_none_taskpkg_keeps_legacy_output(profile, knowledge, monkeypatch):
    monkeypatch.setenv("GENERATION_MODE", "offline")

    legacy = generate_content(profile, knowledge, "开机前安全检查")
    explicit_none = generate_content(
        profile, knowledge, "开机前安全检查", 任务包=None
    )

    assert explicit_none == legacy
    assert set(explicit_none) == {
        "类型",
        "标题",
        "正文",
        "引用来源",
        "引用知识ID",
        "生成模式",
    }
    assert "教学步骤" not in explicit_none


def test_verified_taskpkg_generates_complete_structured_course(
    profile, knowledge, verified_taskpkg
):
    content = generate_content(
        profile, knowledge, "调用方主题不会替代任务名称", 任务包=verified_taskpkg
    )

    assert content["类型"] == "实操指南"
    assert content["标题"] == "开机前安全检查｜数控机床操作工 岗位微课"
    assert content["生成模式"] == "离线确定性（任务包驱动）"
    assert content["学习目标"] == verified_taskpkg["学习目标"]
    assert content["教学步骤"] == verified_taskpkg["操作步骤"]
    assert content["常见错误"] == verified_taskpkg["常见错误"]
    assert content["练习任务"] == verified_taskpkg["练习任务"]
    assert content["考核"] == verified_taskpkg["考核"]
    assert content["补学建议"] == ["重学防护门检查要求"]
    assert content["适用条件"] == {
        "设备": "带防护门的数控机床",
        "环境": ["仿真", "现场带教"],
        "前置技能": ["识别急停按钮"],
        "建议时长分钟": 20,
    }
    assert content["引用来源"] == ["数控机床安全手册"]
    assert set(content["引用知识ID"]) == {"CNC-SAFE-001", "CNC-SAFE-002"}
    assert set(verified_taskpkg["知识ID"]).issubset(content["引用知识ID"])
    assert "## 分步操作与判断标准" in content["正文"]
    for step in verified_taskpkg["操作步骤"]:
        assert step["判定标准"] in content["正文"]
    assert "[CNC-SAFE-001][CNC-SAFE-002]" in content["正文"]


def test_draft_taskpkg_is_rejected_by_default_and_allowed_for_debugging(
    profile, knowledge, verified_taskpkg, monkeypatch
):
    taskpkg = deepcopy(verified_taskpkg)
    taskpkg["验证状态"] = "草稿"
    monkeypatch.delenv("ALLOW_DRAFT_TASKPKG", raising=False)

    with pytest.raises(
        ContractError, match="任务包尚未核验，不能作为完整培训课程依据"
    ):
        generate_content(profile, knowledge, "开机前安全检查", 任务包=taskpkg)

    monkeypatch.setenv("ALLOW_DRAFT_TASKPKG", "1")
    content = generate_content(
        profile, knowledge, "开机前安全检查", 任务包=taskpkg
    )

    assert "草稿任务包" in content["生成模式"]


def test_taskpkg_rejects_references_missing_from_loaded_knowledge(
    profile, knowledge, verified_taskpkg
):
    with pytest.raises(ContractError, match="CNC-SAFE-002"):
        generate_content(
            profile,
            knowledge[:1],
            "开机前安全检查",
            任务包=verified_taskpkg,
        )


def test_unspecified_model_adds_boundary_notice(
    profile, knowledge, verified_taskpkg
):
    taskpkg = deepcopy(verified_taskpkg)
    taskpkg["适用范围"]["具体型号"] = "未指定时必须查阅本机说明书"

    content = generate_content(
        profile, knowledge, "开机前安全检查", 任务包=taskpkg
    )

    assert content["正文"].startswith(
        "> 边界提示：本任务包未指定具体设备型号，涉及型号专属参数时请查阅本机操作说明书。"
    )
