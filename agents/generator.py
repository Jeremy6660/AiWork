"""内容生成 Agent：主题 + 画像 + 已验证知识的约束生成。"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from contracts import (
    ContractError,
    validate_knowledge_item,
    validate_profile,
    validate_training_content,
)
from llm_client import LLMError, available_providers, call_llm_json


class KnowledgeNotCoveredError(ValueError):
    """知识库没有覆盖当前培训主题。"""


def _resource_type(profile: dict[str, Any]) -> str:
    return {
        "入门": "定制讲义",
        "应用": "实操指南",
        "进阶": "分阶测试题",
    }.get(profile.get("推荐难度", "入门"), "定制讲义")


def _validate_knowledge(knowledge: list[dict[str, Any]]) -> None:
    if not isinstance(knowledge, list) or not knowledge:
        raise KnowledgeNotCoveredError("知识库暂未覆盖该主题，已停止专业内容生成")
    for item in knowledge:
        validate_knowledge_item(item)
        if item.get("验证状态") != "已验证":
            raise KnowledgeNotCoveredError(
                f"知识 {item['知识ID']} 尚未核验，不能作为生成依据"
            )


def _citation_ids(text: str) -> set[str]:
    return set(re.findall(r"\[([A-Z0-9-]+)\]", text))


def _validate_grounding(
    content: dict[str, Any], knowledge: list[dict[str, Any]]
) -> dict[str, Any]:
    validate_training_content(content)
    available_ids = {item["知识ID"] for item in knowledge}
    declared_ids = set(content["引用知识ID"])
    inline_ids = _citation_ids(content["正文"])
    invalid = (declared_ids | inline_ids) - available_ids
    if invalid:
        raise ContractError("生成内容引用了检索结果之外的知识：" + "、".join(sorted(invalid)))
    if not declared_ids or not inline_ids:
        raise ContractError("生成内容缺少知识ID引用")
    if not inline_ids.issubset(declared_ids):
        raise ContractError("正文行内引用与“引用知识ID”字段不一致")
    return content


def _offline_generate(
    profile: dict[str, Any],
    knowledge: list[dict[str, Any]],
    topic: str,
    revision_advice: str,
    *,
    mode: str = "离线确定性",
) -> dict[str, Any]:
    resource_type = _resource_type(profile)
    target_skills = "、".join(profile.get("目标技能", [])) or "岗位核心技能"
    facts = "\n".join(
        f"- {item['内容']} [{item['知识ID']}]" for item in knowledge
    )
    if resource_type == "定制讲义":
        activity = (
            "## 学习检查\n\n"
            "1. 用自己的话复述上面的关键要求。\n"
            "2. 指出每条要求对应的知识编号，并说明实际操作前应向谁确认。"
        )
    elif resource_type == "实操指南":
        activity = (
            "## 实操任务\n\n"
            "1. 按知识清单逐项准备并记录检查结果。\n"
            "2. 遇到设备型号差异时暂停操作，查阅本机说明书并请指导人员复核。\n"
            "3. 完成后逐条回查知识编号，记录未能确认的项目。"
        )
    else:
        activity = (
            "## 分阶测试\n\n"
            "### 基础题\n"
            "从知识清单中选择两条要求，说明其适用场景与知识编号。\n\n"
            "### 应用题\n"
            "给出一个违反其中一条要求的操作情境，说明应如何纠正。\n\n"
            "### 挑战题\n"
            "比较知识条目之间的关系，并列出需要进一步查阅设备手册才能回答的问题。"
        )

    revision = ""
    if revision_advice:
        revision = f"\n\n## 本轮修订目标\n\n{revision_advice.strip()}"

    content = {
        "类型": resource_type,
        "标题": f"{topic}｜{profile['岗位']} {resource_type}",
        "正文": (
            f"## 学习目标\n\n"
            f"本资源面向“{profile['岗位']}”，重点补强：{target_skills}。\n\n"
            f"## 已核验知识清单\n\n{facts}\n\n{activity}{revision}"
        ),
        "引用来源": list(dict.fromkeys(item["来源"] for item in knowledge)),
        "引用知识ID": [item["知识ID"] for item in knowledge],
        "生成模式": mode,
    }
    return _validate_grounding(content, knowledge)


def _llm_generate(
    profile: dict[str, Any],
    knowledge: list[dict[str, Any]],
    topic: str,
    revision_advice: str,
) -> dict[str, Any]:
    expected_type = _resource_type(profile)
    material = [
        {
            "知识ID": item["知识ID"],
            "内容": item["内容"],
            "来源": item["来源"],
        }
        for item in knowledge
    ]
    prompt = f"""
你是制造业培训内容生成 Agent。知识列表是唯一允许使用的事实来源。

培训主题：{topic}
学习者画像：{json.dumps(profile, ensure_ascii=False)}
知识列表：{json.dumps(material, ensure_ascii=False)}
审核修改建议：{revision_advice or '无'}

必须遵守：
1. 资源类型固定为“{expected_type}”。
2. 每条专业事实后必须写对应的 [知识ID]，不得补充知识列表以外的参数、标准或操作要求。
3. “引用知识ID”只能包含本次知识列表中的 ID；“引用来源”只能使用给定来源。
4. 正文使用 Markdown，针对画像中的目标技能和推荐难度形成实质差异。
5. 输出 JSON：{{"类型":"{expected_type}","标题":"...","正文":"...","引用来源":["..."],"引用知识ID":["..."]}}。
""".strip()
    result = call_llm_json(
        "deepseek",
        [
            {"role": "system", "content": "只输出符合要求的 JSON 对象。"},
            {"role": "user", "content": prompt},
        ],
    )
    model = str(result.pop("_模型", "deepseek-v4-flash"))
    result["生成模式"] = f"DeepSeek:{model}"
    return _validate_grounding(result, knowledge)


def generate_content(
    画像: dict[str, Any],
    知识列表: list[dict[str, Any]],
    培训主题: str,
    修改建议: str = "",
) -> dict[str, Any]:
    validate_profile(画像)
    _validate_knowledge(知识列表)
    if not isinstance(培训主题, str) or not 培训主题.strip():
        raise ValueError("培训主题必须是非空字符串")
    if not isinstance(修改建议, str):
        raise ValueError("修改建议必须是字符串")

    llm_mode = os.getenv("GENERATION_MODE", "auto").lower()
    should_use_llm = llm_mode == "llm" or (
        llm_mode == "auto" and "deepseek" in available_providers()
    )
    if should_use_llm:
        try:
            return _llm_generate(画像, 知识列表, 培训主题.strip(), 修改建议)
        except (LLMError, ContractError, KeyError, TypeError, ValueError) as exc:
            if os.getenv("ALLOW_OFFLINE_FALLBACK", "1") != "1":
                raise
            return _offline_generate(
                画像,
                知识列表,
                培训主题.strip(),
                修改建议,
                mode=f"离线降级（LLM失败：{type(exc).__name__}）",
            )
    return _offline_generate(画像, 知识列表, 培训主题.strip(), 修改建议)


if __name__ == "__main__":
    from agents.profile import build_profile
    from agents.retrieval import search_knowledge

    topic = "M代码编程"
    print(
        json.dumps(
            generate_content(
                build_profile("数控机床操作工"),
                search_knowledge(topic),
                topic,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
