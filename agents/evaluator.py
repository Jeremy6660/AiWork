"""透明、可解释的单份内容评估。

注意：这里输出的是单份内容诊断，不冒充官方数据集上的“准确率”。官方指标由
knowledge_base/evaluate_benchmark.py 在完整测试集上汇总。
"""

from __future__ import annotations

import re
from typing import Any

from contracts import validate_profile, validate_training_content
from agents.reviewer import _deterministic_anchor


def evaluate(
    培训内容: dict[str, Any],
    知识列表: list[dict[str, Any]],
    画像: dict[str, Any],
) -> dict[str, Any]:
    validate_training_content(培训内容)
    validate_profile(画像)
    text = 培训内容["正文"]

    checks = _deterministic_anchor(培训内容, 知识列表)
    supported = sum(1 for item in checks if item["状态"] == "有依据")
    factuality = supported / len(checks) if checks else 0.0

    topic_terms = {
        topic
        for item in 知识列表
        for topic in item.get("主题", [])
        if len(topic) >= 2
    }
    covered_terms = {term for term in topic_terms if term in text}
    professionalism = (
        min(1.0, 0.4 + 0.6 * len(covered_terms) / len(topic_terms))
        if topic_terms
        else 0.0
    )

    sentences = [
        item.strip()
        for item in re.split(r"[。！？\n]", re.sub(r"\[[A-Z0-9-]+\]", "", text))
        if item.strip() and not item.strip().startswith("#")
    ]
    average_length = sum(len(item) for item in sentences) / len(sentences) if sentences else 0
    overly_long = sum(1 for item in sentences if len(item) > 90)
    readability = 0.45
    if 12 <= average_length <= 65:
        readability += 0.25
    if overly_long == 0:
        readability += 0.15
    if len(sentences) >= 4:
        readability += 0.15
    readability = min(1.0, readability)

    expected_type = {
        "入门": "定制讲义",
        "应用": "实操指南",
        "进阶": "分阶测试题",
    }.get(画像.get("推荐难度"), "定制讲义")
    type_match = 1.0 if 培训内容["类型"] == expected_type else 0.0
    target_skills = 画像.get("目标技能", [])
    target_coverage = (
        sum(1 for skill in target_skills if skill in text) / len(target_skills)
        if target_skills
        else 1.0
    )
    matching = 0.7 * type_match + 0.3 * target_coverage

    available_ids = {item["知识ID"] for item in 知识列表}
    cited_ids = set(培训内容["引用知识ID"]) & available_ids
    knowledge_coverage = len(cited_ids) / len(available_ids) if available_ids else 0.0

    overall = (
        factuality * 0.35
        + professionalism * 0.20
        + readability * 0.15
        + matching * 0.20
        + knowledge_coverage * 0.10
    )

    suggestions: list[str] = []
    if factuality < 0.95:
        suggestions.append("删除无依据断言，或补充对应知识ID")
    if professionalism < 0.7:
        suggestions.append("优先使用检索知识中的规范术语，避免堆砌无关术语")
    if readability < 0.7:
        suggestions.append("缩短长句，并把操作任务拆为可执行步骤")
    if matching < 0.85:
        suggestions.append(f"资源类型应匹配“{画像.get('推荐难度')}”难度，并覆盖目标技能")
    if knowledge_coverage < 0.9:
        suggestions.append("补充本次检索结果中的核心知识点")
    if not suggestions:
        suggestions.append("当前单份内容诊断通过；仍需在评测集上验证总体指标")

    return {
        "事实性": round(factuality, 4),
        "专业性": round(professionalism, 4),
        "可读性": round(readability, 4),
        "匹配度": round(matching, 4),
        "知识覆盖率": round(knowledge_coverage, 4),
        "综合分": round(overall, 4),
        "优化建议": "；".join(suggestions),
        "指标依据": {
            "有依据断言": f"{supported}/{len(checks)}",
            "命中专业主题词": f"{len(covered_terms)}/{len(topic_terms)}",
            "平均句长": round(average_length, 2),
            "预期资源类型": expected_type,
            "目标技能覆盖": round(target_coverage, 4),
            "引用知识": f"{len(cited_ids)}/{len(available_ids)}",
        },
    }
