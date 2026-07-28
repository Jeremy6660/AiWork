"""画像 Agent：岗位能力先验 + 可解释的交互更新与学习路径。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contracts import validate_profile


ONTOLOGY_PATH = (
    Path(__file__).resolve().parents[1] / "knowledge_base" / "skill_ontology.json"
)
LEARNING_RATE = 0.15


def load_ontology(path: Path = ONTOLOGY_PATH) -> dict[str, Any]:
    ontology = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(ontology, dict) or not ontology:
        raise ValueError("技能本体必须是非空对象")
    return ontology


def get_position_skills(岗位: str) -> list[str]:
    ontology = load_ontology()
    position = ontology.get(岗位)
    if not position:
        return []
    return list(position["技能"].keys())


def _difficulty_for_mastery(level: float) -> str:
    if level < 0.4:
        return "入门"
    if level < 0.7:
        return "应用"
    return "进阶"


def _build_learning_path(
    definitions: dict[str, Any], skills: dict[str, float]
) -> list[dict[str, Any]]:
    path: list[dict[str, Any]] = []
    for skill, definition in definitions.items():
        prerequisites = definition.get("先修", [])
        prerequisite_ready = all(skills.get(item, 0.0) >= 0.6 for item in prerequisites)
        if skills[skill] < 0.75:
            if not prerequisites:
                reason = "基础技能，当前掌握度需要提升"
            elif prerequisite_ready:
                reason = "先修技能已满足，可进入本技能学习"
            else:
                missing = [item for item in prerequisites if skills.get(item, 0.0) < 0.6]
                reason = "先补足先修技能：" + "、".join(missing)
            path.append(
                {
                    "技能": skill,
                    "当前掌握度": round(skills[skill], 4),
                    "先修技能": list(prerequisites),
                    "先修已满足": prerequisite_ready,
                    "推荐资源类型": {
                        "入门": "定制讲义",
                        "应用": "实操指南",
                        "进阶": "分阶测试题",
                    }[_difficulty_for_mastery(skills[skill])],
                    "推荐原因": reason,
                }
            )
    path.sort(
        key=lambda item: (
            not item["先修已满足"],
            item["当前掌握度"],
        )
    )
    return path


def build_profile(岗位: str, 答题记录: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not isinstance(岗位, str) or not 岗位.strip():
        raise ValueError("岗位必须是非空字符串")
    ontology = load_ontology()
    if 岗位 not in ontology:
        raise ValueError(f"知识本体暂未覆盖岗位：{岗位}")
    if 答题记录 is None:
        答题记录 = []
    if not isinstance(答题记录, list):
        raise ValueError("答题记录必须是列表")

    definitions = ontology[岗位]["技能"]
    skills = {
        skill: float(definition["初始先验"])
        for skill, definition in definitions.items()
    }
    evidence = [f"使用“{岗位}”岗位能力模型作为冷启动先验"]
    ignored_skills: set[str] = set()

    for index, record in enumerate(答题记录, 1):
        if not isinstance(record, dict):
            raise ValueError(f"第 {index} 条答题记录必须是字典")
        skill = record.get("技能")
        correct = record.get("正确")
        if not isinstance(skill, str) or not skill.strip():
            raise ValueError(f"第 {index} 条答题记录缺少有效技能名")
        if not isinstance(correct, bool):
            raise ValueError(f"第 {index} 条答题记录的“正确”必须是布尔值")
        if skill not in skills:
            ignored_skills.add(skill)
            continue
        previous = skills[skill]
        target = 1.0 if correct else 0.0
        updated = previous + LEARNING_RATE * (target - previous)
        skills[skill] = round(min(0.99, max(0.05, updated)), 4)
        evidence.append(
            f"{skill}：依据答题{'正确' if correct else '错误'}，"
            f"掌握度由 {previous:.2f} 更新为 {skills[skill]:.2f}"
        )

    if ignored_skills:
        evidence.append("忽略本岗位未定义技能：" + "、".join(sorted(ignored_skills)))

    weak_skills = sorted(skills, key=skills.get)[:2]
    weakest_level = skills[weak_skills[0]]
    profile = {
        "岗位": 岗位,
        "技能掌握度": skills,
        "目标技能": weak_skills,
        "推荐难度": _difficulty_for_mastery(weakest_level),
        "画像依据": evidence,
        "学习路径": _build_learning_path(definitions, skills),
    }
    validate_profile(profile)
    return profile


def apply_feedback(profile: dict[str, Any], mode: str) -> dict[str, Any]:
    """把“降维解释/进阶挑战”反馈转成下一次生成所需的难度信号。"""
    validate_profile(profile)
    updated = dict(profile)
    updated["画像依据"] = list(profile.get("画像依据", []))
    if mode == "降维解释":
        updated["推荐难度"] = "入门"
        updated["画像依据"].append("学员反馈内容偏难，下一轮采用降维解释")
    elif mode == "进阶挑战":
        updated["推荐难度"] = "进阶"
        updated["画像依据"].append("学员反馈已掌握，下一轮提供进阶挑战")
    elif mode:
        raise ValueError(f"不支持的反馈模式：{mode}")
    return updated


if __name__ == "__main__":
    print(json.dumps(build_profile("数控机床操作工"), ensure_ascii=False, indent=2))
