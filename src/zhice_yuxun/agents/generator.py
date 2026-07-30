"""内容生成 Agent：主题 + 画像 + 已验证知识的约束生成。"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from ..contracts import (
    ContractError,
    validate_knowledge_item,
    validate_profile,
    validate_training_content,
)
from ..llm_client import LLMError, available_providers, call_llm_json


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


def _filter_hallucinated_sources(
    content: dict[str, Any], knowledge: list[dict[str, Any]]
) -> dict[str, Any]:
    '''Filter hallucinated citation sources, keep only sources present in knowledge list.

    Document requirement: Check if all cited sources are actually in the input knowledge list.
    Sources not in the list = hallucination, filter them out.
    '''
    valid_sources = set()
    for item in knowledge:
        source = item.get('来源', '')
        if isinstance(source, str) and source.strip():
            valid_sources.add(source.strip())

    original = list(content.get('引用来源', []))
    filtered = [s for s in original if s in valid_sources]
    removed = [s for s in original if s not in valid_sources]

    if removed:
        content['引用来源'] = filtered
        content.setdefault('_幻觉来源已过滤', []).extend(removed)

    return content


def _validate_grounding(
    content: dict[str, Any], knowledge: list[dict[str, Any]]
) -> dict[str, Any]:
    validate_training_content(content)
    available_ids = {item['知识ID'] for item in knowledge}
    declared_ids = set(content['引用知识ID'])
    inline_ids = _citation_ids(content['正文'])
    invalid_ids = (declared_ids | inline_ids) - available_ids
    if invalid_ids:
        raise ContractError('生成内容引用了检索结果之外的知识：' + '、'.join(sorted(invalid_ids)))
    if not declared_ids or not inline_ids:
        raise ContractError('生成内容缺少知识ID引用')
    if not inline_ids.issubset(declared_ids):
        raise ContractError("正文行内引用与[引用知识ID]字段不一致")

    # 验证引用来源：确保都在知识列表的来源中
    valid_sources = set()
    for item in knowledge:
        source = item.get('来源', '')
        if isinstance(source, str) and source.strip():
            valid_sources.add(source.strip())
    declared_sources = set(content.get('引用来源', []))
    invalid_sources = declared_sources - valid_sources
    if invalid_sources:
        raise ContractError(
            '生成内容引用了知识列表之外的来源：' + '、'.join(sorted(invalid_sources))
        )
    if not declared_sources:
        raise ContractError('生成内容的引用来源不能为空')

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
            f"本资源面向'{profile['岗位']}'，重点补强：{target_skills}。\n\n"
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
    '''接入真实 LLM API 生成培训内容（第 3 周核心实现）。

    提示词设计要求：
    1. 明确制造业培训师角色
    2. 逐项展示学员技能水平（含具体分数）
    3. 难度与内容风格严格适配（入门→大白话+比喻/应用→步骤+案例/进阶→开放问题）
    4. 锁定知识范围，禁止自由发挥
    5. 每条事实标注 [知识ID]
    '''
    expected_type = _resource_type(profile)
    difficulty_label = profile.get('推荐难度', '入门')

    # 逐项展示技能水平，让模型真正理解学员强弱项
    skill_lines: list[str] = []
    for skill_name, level in sorted(
        profile.get('技能掌握度', {}).items(), key=lambda x: x[1]
    ):
        if level < 0.4:
            tag = '【薄弱→需入门辅导】'
        elif level < 0.7:
            tag = '【一般→需实操强化】'
        else:
            tag = '【较好→可挑战进阶】'
        skill_lines.append(f'  - {skill_name}：掌握度 {level:.2f} {tag}')

    # 学习路径中的目标技能
    target_skills = profile.get('目标技能', [])
    learning_path = profile.get('学习路径', [])

    # 知识领域覆盖
    knowledge_domains = profile.get('知识领域覆盖', [])

    material = [
        {
            '知识ID': item['知识ID'],
            '内容': item['内容'],
            '来源': item['来源'],
        }
        for item in knowledge
    ]

    # 根据难度级别确定写作风格（第5周：降维/进阶差异化）
    if difficulty_label == "入门":
        style_guide = (
            "【入门风格】用大白话解释每个概念，多用生活中的比喻（如「就像……这样」），"
            "每段不超过 5 行。所有专业术语第一次出现时必须加粗并附解释。"
            "末尾加「学习检查」环节：3 个简单问题帮助学员自测理解程度。"
        )
    elif difficulty_label == "进阶":
        style_guide = (
            "【进阶风格】直接进入工程场景分析。"
            "包含至少 1 个开放性问题（答案不唯一，需要学员结合实际情况思考）。"
            "末尾加「进阶挑战」：给出一个需要学员查阅设备手册或国标才能完成的任务。"
            "鼓励学员建立不同知识条目之间的关联。"
        )
    else:  # 应用
        style_guide = (
            "【应用风格】给出具体操作步骤和判断标准。"
            "包含 1-2 个常见错误案例分析（「某操作工曾经……导致……」）。"
            "末尾加「实操任务」：要求学员在真实设备上按步骤完成并记录结果。"
        )

    # 降维/进阶特殊处理（第5周：审核反馈触发）
    feedback_instruction = ""
    if revision_advice:
        feedback_instruction = f"""
## 本轮特别要求（审核反馈）
上一轮内容被审核退回，修改建议如下：
\"{revision_advice.strip()}\"

请针对性地修改内容，确保解决上述问题后再输出。
"""

    prompt = f"""你是一位拥有 15 年一线经验的制造业培训师，专门为技术工人设计个性化培训教案。

## 你的学员
- 岗位：{profile.get("岗位", "未知")}
- 岗位简介：{profile.get("岗位描述", "未知")}
- 典型工作场景：{profile.get("典型企业", "")}
- 当前学习阶段：{difficulty_label}（根据其最薄弱技能的掌握度判定）
- 知识领域薄弱点：{"、".join(knowledge_domains[:3]) if knowledge_domains else "待评估"}

### 学员各技能掌握度（0=完全不会，1=精通）
{chr(10).join(skill_lines)}

### 本次重点补强技能
{"、".join(target_skills) if target_skills else "根据知识素材自动判断"}

## 本次培训主题
{topic}

## 你唯一可用的知识素材（共 {len(material)} 条）
以下是学员所在岗位经过人工核验的专业知识。**这是你写教案时唯一可以引用的事实来源，禁止使用你训练数据中的任何信息。**

{json.dumps(material, ensure_ascii=False, indent=2)}

## 写作要求
{style_guide}

{feedback_instruction}

## 必须遵守的铁律（违反任一条即构成「幻觉」）
1. 正文中每条专业事实、参数、标准、操作要求，句末必须标注对应 [知识ID]，例如「切削速度应控制在 80-120 m/min [CNC-CUT-001]」。
2. [引用知识ID] 数组**只能**包含上述知识素材中的 ID，不能少也不能多。
3. [引用来源] 数组**只能**使用上述知识素材中的[来源]字段值，不能自编来源名称。
4. 如果你发现某个知识点在上述素材中找不到依据——宁可不说，也不能编造。制造行业的参数错了会出安全事故。
5. 正文使用 Markdown 格式，用 ## 和 ### 划分章节。

## 输出格式
必须输出一个严格的 JSON 对象（不要带 ```json 标记），格式如下：
{{"类型":"{expected_type}","标题":"...","正文":"...","引用来源":["来源1"],"引用知识ID":["ID1"]}}""".strip()

    result = call_llm_json(
        'deepseek',
        [
            {
                'role': 'system',
                'content': (
                    '你是一位严谨的制造业培训师。你只根据提供的知识素材编写培训内容，'
                    '每条事实必须标注来源 ID。你不会编造参数、标准或操作要求。'
                    '你输出的内容直接关系到一线工人的操作安全。'
                ),
            },
            {'role': 'user', 'content': prompt},
        ],
    )
    model = str(result.pop('_模型', 'deepseek-v4-flash'))
    result['生成模式'] = f'DeepSeek:{model}'

    # 第3周要求：引用来源验证——过滤 LLM 幻觉出来的来源
    result = _filter_hallucinated_sources(result, knowledge)

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
    from .profile import build_profile
    from .retrieval import search_knowledge

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
