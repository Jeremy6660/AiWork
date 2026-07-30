"""第6周提交物：3组画像测试用例 + 对应生成结果对比。

演示"同一培训主题 → 3 组不同画像 → 3 种不同资源类型"的个性化引擎效果。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.generator import generate_content
from agents.profile import apply_feedback, build_profile
from agents.retrieval import search_knowledge

OUTPUT = Path(__file__).resolve().parents[1] / "tests" / "3_profile_comparison.json"


def build_three_profiles():
    """构建3组差异化画像：入门 / 应用 / 进阶"""

    # Profile 1: 新入职质检员（冷启动）→ 推荐难度: 入门
    beginner = build_profile("质检员")

    # Profile 2: 有经验质检员 —— 通过答题把弱技能推到 0.4+ → 推荐难度: 应用
    intermediate = build_profile(
        "质检员",
        [
            {"技能": "不合格品处理与8D报告", "正确": True},
            {"技能": "不合格品处理与8D报告", "正确": True},
            {"技能": "抽样检验标准应用", "正确": True},
            {"技能": "质量记录与可追溯管理", "正确": True},
        ],
    )

    # Profile 3: 熟练质检员 —— 进阶反馈模式 → 推荐难度: 进阶
    advanced = apply_feedback(intermediate, "进阶挑战")

    return [
        {"画像编号": 1, "难度层级": "入门", "画像": beginner},
        {"画像编号": 2, "难度层级": "应用", "画像": intermediate},
        {"画像编号": 3, "难度层级": "进阶", "画像": advanced},
    ]


def main():
    topic = "量具使用"
    knowledge = search_knowledge(topic)

    print(f"知识库命中: {len(knowledge)} 条")
    print(f"知识ID: {[k['知识ID'] for k in knowledge]}")

    profiles = build_three_profiles()
    results = []

    for entry in profiles:
        idx = entry["画像编号"]
        level = entry["难度层级"]
        profile = entry["画像"]

        content = generate_content(profile, knowledge, topic)

        result = {
            "用例编号": idx,
            "难度层级": level,
            "资源类型": content["类型"],
            "标题": content["标题"],
            "推荐难度": profile["推荐难度"],
            "目标技能": profile["目标技能"],
            "技能掌握度摘要": {
                skill: round(val, 2)
                for skill, val in sorted(
                    profile["技能掌握度"].items(), key=lambda x: x[1]
                )[:4]
            },
            "培训内容摘要": content["正文"][:300] + "...",
            "引用知识ID": content["引用知识ID"],
            "生成模式": content["生成模式"],
            "知识领域覆盖": profile.get("知识领域覆盖", []),
        }
        results.append(result)

        print(f"\n{'='*60}")
        print(f"画像 #{idx} | 难度: {level} | 类型: {content['类型']}")
        print(f"标题: {content['标题']}")
        print(f"目标技能: {profile['目标技能']}")
        print(f"最弱4项: {result['技能掌握度摘要']}")

    # 验证：三个画像应该产出三种不同资源类型
    types = {r["资源类型"] for r in results}
    print(f"\n{'='*60}")
    if types == {"定制讲义", "实操指南", "分阶测试题"}:
        print("✅ 3组画像成功生成3种不同资源类型，差异化验证通过！")
    else:
        print(f"⚠️ 资源类型集合: {types}（期望: 定制讲义 + 实操指南 + 分阶测试题）")

    comparison = {
        "提交物说明": "3组差异化画像测试用例与对应生成结果对比——智策育训 P3 画像与生成 Agent",
        "测试主题": topic,
        "测试日期": "2026-08-27",
        "对比维度": [
            "同一培训主题（量具使用）",
            "同一岗位（质检员）",
            "3组不同掌握度水平 → 3种资源类型",
        ],
        "个性化验证": {
            "入门画像": "新入职冷启动，推荐定制讲义（大白话+比喻+学习检查）",
            "应用画像": "有经验学员，推荐实操指南（操作步骤+案例+实操任务）",
            "进阶画像": "熟练学员反馈'进阶挑战'，推荐分阶测试题（基础/应用/挑战）",
        },
        "对比结果": results,
    }

    OUTPUT.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📄 对比结果已写入: {OUTPUT}")


if __name__ == "__main__":
    main()
