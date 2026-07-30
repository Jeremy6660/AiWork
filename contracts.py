"""项目公共数据契约与轻量校验。

不用 Pydantic 等额外框架，保持团队容易理解；所有 Agent 在边界处调用这些
校验函数，避免错误数据进入下游后才以 KeyError 的形式爆炸。
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


FlowStatus = Literal["通过", "需人工复核", "失败"]
ResourceType = Literal["定制讲义", "实操指南", "分阶测试题"]


class ContractError(ValueError):
    """输入或输出不符合项目公共契约。"""


class KnowledgeItem(TypedDict, total=False):
    知识ID: str
    内容: str
    来源: str
    来源定位: str
    主题: list[str]
    检索分数: float
    验证状态: str


class LearnerProfile(TypedDict, total=False):
    岗位: str
    技能掌握度: dict[str, float]
    目标技能: list[str]
    推荐难度: str
    画像依据: list[str]
    学习路径: list[dict[str, Any]]


class TrainingContent(TypedDict, total=False):
    类型: ResourceType
    标题: str
    正文: str
    引用来源: list[str]
    引用知识ID: list[str]
    生成模式: str


class IterationRecord(TypedDict, total=False):
    """编排迭代摘要；正文为新增可选字段，兼容既有记录。"""

    轮次: int
    内容标题: str
    正文: str
    资源类型: ResourceType
    生成模式: str
    流程状态: FlowStatus
    审核通过: bool
    幻觉分数: float
    修改建议: str
    断言核查: list[dict[str, Any]]


def _require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"字段“{key}”必须是非空字符串")
    return value.strip()


def validate_knowledge_item(item: dict[str, Any]) -> KnowledgeItem:
    if not isinstance(item, dict):
        raise ContractError("知识条目必须是字典")
    _require_string(item, "知识ID")
    _require_string(item, "内容")
    _require_string(item, "来源")
    _require_string(item, "来源定位")
    topics = item.get("主题")
    if not isinstance(topics, list) or not topics or not all(
        isinstance(topic, str) and topic.strip() for topic in topics
    ):
        raise ContractError("字段“主题”必须是非空字符串列表")
    return item  # type: ignore[return-value]


def validate_profile(profile: dict[str, Any]) -> LearnerProfile:
    if not isinstance(profile, dict):
        raise ContractError("画像必须是字典")
    _require_string(profile, "岗位")
    skills = profile.get("技能掌握度")
    if not isinstance(skills, dict) or not skills:
        raise ContractError("字段“技能掌握度”必须是非空字典")
    for skill, level in skills.items():
        if not isinstance(skill, str) or not skill.strip():
            raise ContractError("技能名必须是非空字符串")
        if not isinstance(level, (int, float)) or isinstance(level, bool):
            raise ContractError(f"技能“{skill}”的掌握度必须是数值")
        if not 0 <= float(level) <= 1:
            raise ContractError(f"技能“{skill}”的掌握度必须位于 0~1")
    return profile  # type: ignore[return-value]


def validate_training_content(content: dict[str, Any]) -> TrainingContent:
    if not isinstance(content, dict):
        raise ContractError("培训内容必须是字典")
    resource_type = _require_string(content, "类型")
    if resource_type not in {"定制讲义", "实操指南", "分阶测试题"}:
        raise ContractError(f"不支持的资源类型：{resource_type}")
    _require_string(content, "标题")
    _require_string(content, "正文")
    citations = content.get("引用知识ID")
    if not isinstance(citations, list) or not all(
        isinstance(item, str) and item.strip() for item in citations
    ):
        raise ContractError("字段“引用知识ID”必须是字符串列表")
    sources = content.get("引用来源")
    if not isinstance(sources, list) or not all(
        isinstance(item, str) and item.strip() for item in sources
    ):
        raise ContractError("字段“引用来源”必须是字符串列表")
    return content  # type: ignore[return-value]
