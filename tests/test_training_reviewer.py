from copy import deepcopy

import pytest

from src.zhice_yuxun.agents.reviewer import (
    _check_teaching_completeness,
    review_content,
)


@pytest.fixture
def knowledge() -> list[dict]:
    return [
        {
            "知识ID": "CNC-SAFE-002",
            "内容": "操作机床时应使用适当的眼部和听力防护用品。",
            "来源": "数控机床安全手册",
            "来源定位": "安全防护章节",
            "主题": ["安全防护"],
            "验证状态": "已验证",
        }
    ]


@pytest.fixture
def structured_content() -> dict:
    fact = "操作机床时应使用适当的眼部和听力防护用品。"
    return {
        "类型": "实操指南",
        "标题": "安全防护微课",
        "正文": (
            "## 已核验知识\n\n"
            f"- {fact} [CNC-SAFE-002]\n\n"
            f"- {fact} [CNC-SAFE-002]\n\n"
            "完成练习后按检查表记录结果，遇到异常立即停止并报告指导人员。"
        ),
        "引用来源": ["数控机床安全手册"],
        "引用知识ID": ["CNC-SAFE-002"],
        "生成模式": "离线确定性（任务包驱动）",
        "学习目标": [
            {
                "行为": "完成个人防护检查",
                "条件": "进入操作区域前",
                "标准": "检查无遗漏",
            }
        ],
        "适用条件": {"设备": "通用数控机床", "环境": "现场带教"},
        "教学步骤": [
            {
                "序号": index,
                "操作": f"执行安全检查步骤{index}",
                "判定标准": "检查项符合要求",
                "异常处理": "停止操作并报告指导人员",
                "引用知识ID": ["CNC-SAFE-002"],
                "安全关键": index == 3,
            }
            for index in range(1, 5)
        ],
        "常见错误": [],
        "练习任务": {"任务": "完成一次模拟检查"},
        "考核": {
            "题目": [
                {"题目": "操作前应检查什么？", "标准答案": "个人防护"},
                {"题目": "发现异常怎么办？", "标准答案": "停止并报告"},
            ],
            "评分规则": ["两题均正确"],
            "合格线": "两题均正确",
        },
        "补学建议": ["重学个人防护检查并重新练习"],
    }


def test_complete_structured_content_passes(structured_content, knowledge):
    passed, problems, metrics = _check_teaching_completeness(structured_content)
    review = review_content(structured_content, knowledge)

    assert passed is True
    assert problems == []
    assert metrics == {
        "教学完整率": 1.0,
        "目标考核对齐率": 1.0,
        "关键步骤可判定率": 1.0,
    }
    assert review["通过"] is True
    assert review["事实审核"] == "pass"
    assert review["教学完整性"] == "pass"


def test_deleting_learning_objectives_fails_with_specific_problem(
    structured_content, knowledge
):
    content = deepcopy(structured_content)
    del content["学习目标"]

    review = review_content(content, knowledge)

    assert review["通过"] is False
    assert review["教学完整性"] == "fail"
    assert "学习目标不能为空" in review["教学问题"]
    assert "教学不完整：学习目标不能为空" in review["修改建议"]
    assert review["幻觉分数"] == 0.0


def test_safety_step_missing_standard_points_to_step_number(
    structured_content, knowledge
):
    content = deepcopy(structured_content)
    del content["教学步骤"][2]["判定标准"]

    review = review_content(content, knowledge)

    assert review["通过"] is False
    assert review["事实审核"] == "pass"
    assert review["教学完整性"] == "fail"
    assert "第3个教学步骤缺少判定标准" in review["教学问题"]


def test_unknown_equipment_rejects_obvious_model_in_step(
    structured_content, knowledge
):
    content = deepcopy(structured_content)
    content["适用条件"]["设备"] = "具体型号未知"
    content["教学步骤"][0]["操作"] += "，读取 HAAS-VF2 参数"

    review = review_content(content, knowledge)

    assert review["通过"] is False
    assert review["教学完整性"] == "fail"
    assert any("HAAS-VF2" in problem for problem in review["教学问题"])


def test_assessment_problem_names_exact_missing_field(structured_content, knowledge):
    content = deepcopy(structured_content)
    del content["考核"]["合格线"]

    review = review_content(content, knowledge)

    assert "考核缺少合格线" in review["教学问题"]
    assert review["教学完整率"] == pytest.approx(8 / 9, abs=0.0001)


def test_legacy_content_keeps_fact_result_and_marks_teaching_disabled(
    structured_content, knowledge
):
    legacy = {
        key: deepcopy(structured_content[key])
        for key in ("类型", "标题", "正文", "引用来源", "引用知识ID", "生成模式")
    }

    assert _check_teaching_completeness(legacy) == (True, [], {})
    review = review_content(legacy, knowledge)

    assert review["通过"] is True
    assert review["事实审核"] == "pass"
    assert review["教学完整性"] == "未启用"
    assert review["教学问题"] == []
    assert review["教学完整率"] == 1.0


# ── 任务包锚定（集成修复）：结构化微课文本来自任务包字段，锚定依据任务包而非知识原文相似度 ──


@pytest.fixture
def golden_taskpkg() -> dict:
    """最小已核验任务包：黄金任务的结构缩影。"""
    return {
        "任务包ID": "TASK-TEST-001",
        "岗位": "数控机床操作工",
        "任务名称": "开机前安全检查与门联锁验证",
        "适用范围": {
            "设备类型": "带防护门和门联锁的数控机床",
            "具体型号": "未指定",
            "培训环境": ["课堂讲解", "仿真", "现场带教"],
            "建议时长分钟": 20,
        },
        "前置技能": ["识别急停按钮", "理解防护门作用"],
        "知识ID": ["CNC-SAFE-002"],
        "学习目标": [
            {
                "行为": "按检查表完成开机前安全检查",
                "条件": "在指导人员监督和设备未启动状态下",
                "标准": "关键项目无遗漏；发现异常时停止启动并上报",
                "引用知识ID": ["CNC-SAFE-002"],
            }
        ],
        "操作步骤": [
            {
                "序号": index,
                "操作": f"检查项{index}",
                "判定标准": "无明显损坏、错位、阻塞或紧固件缺失",
                "异常处理": "停止启动并交由授权人员处理",
                "引用知识ID": ["CNC-SAFE-002"],
            }
            for index in range(1, 5)
        ],
        "常见错误": [],
        "练习任务": {"任务": "根据模拟检查记录判断设备能否启动"},
        "考核": {
            "题目": [
                {
                    "题目": f"检查项{index}应确认哪些项目？",
                    "标准答案": "钥匙无弯曲或错位、紧固件齐全",
                    "引用知识ID": ["CNC-SAFE-002"],
                }
                for index in range(1, 3)
            ],
            "评分规则": ["安全关键项全对"],
            "合格线": "所有安全关键项必须正确",
            "错后补学": [
                {"补学内容": "重学门联锁检查要求", "引用知识ID": ["CNC-SAFE-002"]}
            ],
        },
        "验证状态": "已核验",
        "版本": "1.0",
        "来源缺口": [],
    }


@pytest.fixture
def taskpkg_content(golden_taskpkg) -> dict:
    """任务包驱动生成的结构化微课（等价于 generator._offline_generate_taskpkg 输出）。"""
    return {
        "类型": "实操指南",
        "标题": "开机前安全检查与门联锁验证｜数控机床操作工 岗位微课",
        "正文": (
            "## 本次培训任务\n\n"
            "开机前安全检查与门联锁验证\n\n"
            "- 设备类型：带防护门和门联锁的数控机床\n"
            "- 培训环境：课堂讲解、仿真、现场带教\n"
            "- 建议时长：20 分钟\n"
            "- 前置技能：识别急停按钮、理解防护门作用\n\n"
            "## 学习目标\n\n"
            "- 按检查表完成开机前安全检查（在指导人员监督和设备未启动状态下，"
            "关键项目无遗漏；发现异常时停止启动并上报） [CNC-SAFE-002]\n\n"
            "## 分步操作与判断标准\n\n"
            "### 步骤1 检查项1 [CNC-SAFE-002]\n"
            "- 判定标准：无明显损坏、错位、阻塞或紧固件缺失 [CNC-SAFE-002]\n"
            "- 异常处理：停止启动并交由授权人员处理 [CNC-SAFE-002]\n\n"
            "### 步骤2 检查项2 [CNC-SAFE-002]\n"
            "- 判定标准：无明显损坏、错位、阻塞或紧固件缺失 [CNC-SAFE-002]\n"
            "- 异常处理：停止启动并交由授权人员处理 [CNC-SAFE-002]\n\n"
            "### 步骤3 检查项3 [CNC-SAFE-002]\n"
            "- 判定标准：无明显损坏、错位、阻塞或紧固件缺失 [CNC-SAFE-002]\n"
            "- 异常处理：停止启动并交由授权人员处理 [CNC-SAFE-002]\n\n"
            "### 步骤4 检查项4 [CNC-SAFE-002]\n"
            "- 判定标准：无明显损坏、错位、阻塞或紧固件缺失 [CNC-SAFE-002]\n"
            "- 异常处理：停止启动并交由授权人员处理 [CNC-SAFE-002]\n\n"
            "## 考核与合格标准\n\n"
            "1. 检查项1应确认哪些项目？ [CNC-SAFE-002]\n"
            "2. 检查项2应确认哪些项目？ [CNC-SAFE-002]\n\n"
            "- 合格线：所有安全关键项必须正确 [CNC-SAFE-002]\n\n"
            "## 错后补学\n\n"
            "- 重学门联锁检查要求 [CNC-SAFE-002]"
        ),
        "引用来源": ["数控机床安全手册"],
        "引用知识ID": ["CNC-SAFE-002"],
        "生成模式": "离线确定性（任务包驱动）",
        "学习目标": golden_taskpkg["学习目标"],
        "适用条件": {"设备": "带防护门和门联锁的数控机床", "环境": ["课堂讲解", "仿真", "现场带教"], "前置技能": ["识别急停按钮"], "建议时长分钟": 20},
        "教学步骤": golden_taskpkg["操作步骤"],
        "常见错误": [],
        "练习任务": golden_taskpkg["练习任务"],
        "考核": golden_taskpkg["考核"],
        "补学建议": ["重学门联锁检查要求"],
    }


def test_taskpkg_anchored_content_passes_fact_review(taskpkg_content, golden_taskpkg, knowledge):
    """任务包驱动的结构化微课应通过事实审核（锚定依据任务包字段）。"""
    review = review_content(taskpkg_content, knowledge, 任务包=golden_taskpkg)

    assert review["通过"] is True
    assert review["事实审核"] == "pass"
    assert review["幻觉分数"] == 0.0
    assert all(item["状态"] == "有依据" for item in review["断言核查"])


def test_taskpkg_anchor_rejects_out_of_boundary_claim(taskpkg_content, golden_taskpkg, knowledge):
    """任务包锚定不能放行幻觉：任务包之外的新事实断言必须被拦截。"""
    bad = deepcopy(taskpkg_content)
    bad["正文"] += "\n- 主轴转速必须 8000 rpm [CNC-SAFE-002]"

    review = review_content(bad, knowledge, 任务包=golden_taskpkg)

    assert review["通过"] is False
    assert review["幻觉分数"] > 0.0
    assert any(item["状态"] == "无依据" for item in review["断言核查"])


def test_taskpkg_anchor_rejects_fake_id(taskpkg_content, golden_taskpkg, knowledge):
    """任务包锚定不能放行不存在的知识ID。

    伪造 ID 会在规则引擎层被拦截（行内引用越界→直接 fail），
    也可能在锚定层被拦截（引用ID不存在）——两种路径都算安全拒绝。
    """
    bad = deepcopy(taskpkg_content)
    bad["正文"] += "\n- 门联锁测试需要专用夹具 [FAKE-999]"

    review = review_content(bad, knowledge, 任务包=golden_taskpkg)

    assert review["通过"] is False
    assert review["幻觉分数"] > 0.0
