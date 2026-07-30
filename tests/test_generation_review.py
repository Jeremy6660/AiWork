import copy

import pytest

from agents.generator import KnowledgeNotCoveredError, generate_content
from agents.profile import apply_feedback, build_profile
from agents.retrieval import search_knowledge
from agents.reviewer import review_content


def test_empty_knowledge_refuses_generation():
    with pytest.raises(KnowledgeNotCoveredError):
        generate_content(build_profile("数控机床操作工"), [], "未知主题")


def test_topic_and_profile_change_output():
    operator = build_profile("数控机床操作工")
    safety = generate_content(operator, search_knowledge("数控机床安全操作"), "数控机床安全操作")
    mcode = generate_content(operator, search_knowledge("M代码编程"), "M代码编程")
    quality = generate_content(
        build_profile("质检员"),
        search_knowledge("量具使用与质量检测"),
        "量具使用与质量检测",
    )
    assert safety["标题"] != mcode["标题"]
    assert quality["标题"] != mcode["标题"]


def test_three_difficulty_levels_map_to_three_required_resources():
    knowledge = search_knowledge("量具使用与质量检测")
    # 质检员冷启动有多个技能 < 0.4（不合格品0.25/抽样0.35/质量记录0.35）
    # 需要把全部弱技能推到 >= 0.4 才能让基础难度变成 应用
    base = build_profile(
        "质检员",
        [
            {"技能": "不合格品处理与8D报告", "正确": True},
            {"技能": "不合格品处理与8D报告", "正确": True},
            {"技能": "抽样检验标准应用", "正确": True},
            {"技能": "质量记录与可追溯管理", "正确": True},
        ],
    )
    beginner = generate_content(apply_feedback(base, "降维解释"), knowledge, "量具使用")
    application = generate_content(base, knowledge, "量具使用")
    advanced = generate_content(apply_feedback(base, "进阶挑战"), knowledge, "量具使用")
    assert {beginner["类型"], application["类型"], advanced["类型"]} == {
        "定制讲义",
        "实操指南",
        "分阶测试题",
    }


def test_generated_facts_are_grounded_and_pass_deterministically():
    knowledge = search_knowledge("M代码编程")
    content = generate_content(build_profile("CNC编程员"), knowledge, "M代码编程")
    first = review_content(content, knowledge)
    second = review_content(content, knowledge)
    assert first == second
    assert first["通过"] is True
    assert first["幻觉分数"] == 0.0


def test_fabricated_uncited_fact_is_rejected():
    knowledge = search_knowledge("M代码编程")
    content = generate_content(build_profile("CNC编程员"), knowledge, "M代码编程")
    bad = copy.deepcopy(content)
    bad["正文"] += "\n- M88 必须用于启动主轴。"
    result = review_content(bad, knowledge)
    assert result["通过"] is False
    assert result["流程状态"] == "失败"


def test_out_of_scope_citation_is_rejected():
    knowledge = search_knowledge("M代码编程")
    content = generate_content(build_profile("CNC编程员"), knowledge, "M代码编程")
    bad = copy.deepcopy(content)
    bad["引用知识ID"].append("FAKE-001")
    bad["正文"] += "\n- 伪造事实 [FAKE-001]"
    result = review_content(bad, knowledge)
    assert result["通过"] is False
    assert result["幻觉分数"] == 1.0

