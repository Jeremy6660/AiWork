"""P4 10-Minute Demo Script v1 — Offline Deterministic Path.

Demonstrates the complete "痛点 → 画像 → 检索证据 → 差异生成 →
审核驳回 → 自动修正 → 可信边界" flow.

Usage (offline, no API keys needed):
    python scripts/p4_demo_script.py

For replay from saved results:
    python scripts/p4_demo_script.py --replay

Output saved to: artifacts/p4_ablation_experiments_20260730/demo_output.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ── Offline-only; zero API calls ─────────────────────────────────
os.environ["GENERATION_MODE"] = "offline"
os.environ["ENABLE_LLM_REVIEW"] = "0"
os.environ["ENABLE_L3_VOTING"] = "0"
os.environ["ALLOW_OFFLINE_FALLBACK"] = "1"

from src.zhice_yuxun.agents.evaluator import evaluate
from src.zhice_yuxun.agents.generator import generate_content
from src.zhice_yuxun.agents.profile import (
    apply_feedback,
    build_profile,
    get_stable_positions,
)
from src.zhice_yuxun.agents.retrieval import search_knowledge
from src.zhice_yuxun.agents.reviewer import review_content

OUTPUT_DIR = Path(
    os.getenv(
        "P4_OUTPUT_DIR",
        str(ROOT / "artifacts" / "p4_ablation_experiments_20260730"),
    )
).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Demo timing constants (seconds) ──────────────────────────────
TIMING = {
    "痛点": 60,
    "画像": 120,
    "检索证据": 60,
    "差异生成": 120,
    "审核驳回": 120,
    "自动修正": 60,
    "可信边界": 60,
}

SEPARATOR = "\n" + "─" * 60


def print_section(segment: str, duration_sec: int) -> None:
    """Print a timed demo section header."""
    minutes = duration_sec // 60
    seconds = duration_sec % 60
    print(f"\n{'='*60}")
    print(f"  [{minutes}:{seconds:02d}]  {segment}")
    print(f"{'='*60}")


def demo_part1_痛点() -> dict[str, Any]:
    """Part 1: The Pain Point (1 min)."""
    print_section("Part 1: 痛点 — 制造业培训的三大挑战", TIMING["痛点"])

    pain_points = {
        "segment": "痛点",
        "duration_sec": TIMING["痛点"],
        "challenges": [
            {
                "challenge": "培训周期长",
                "detail": "新员工从入职到独立操作平均需要 3-6 个月，"
                         "培训材料更新滞后于设备升级速度。",
            },
            {
                "challenge": "缺个性化",
                "detail": "同一本操作手册发给所有人，不考虑学员已有的"
                         "技能基础。入门者看不懂，熟练工觉得浪费时间。",
            },
            {
                "challenge": "大模型幻觉",
                "detail": "通用 AI 回答制造业问题时可能编造参数、标准或"
                         "操作步骤，一线操作容错率极低。",
            },
        ],
        "solution_preview": (
            "智策育训：个性化画像 + 可溯源知识检索 + 三层审核闭环"
        ),
        "stable_positions": get_stable_positions(),
    }

    for cp in pain_points["challenges"]:
        print(f"\n  >> {cp['challenge']}")
        print(f"     {cp['detail']}")
    print(f"\n  >> 解决方向：{pain_points['solution_preview']}")
    print(f"  >> 当前覆盖岗位：{'、'.join(pain_points['stable_positions'])}")

    return pain_points


def demo_part2_画像() -> dict[str, Any]:
    """Part 2: Learner Profile Building (2 min)."""
    print_section("Part 2: 画像 — 从岗位能力模型到个性化画像", TIMING["画像"])

    # Build three differentiated profiles
    beginner = build_profile("质检员")
    intermediate = build_profile(
        "质检员",
        [
            {"技能": "不合格品处理与8D报告", "正确": True},
            {"技能": "不合格品处理与8D报告", "正确": True},
            {"技能": "抽样检验标准应用", "正确": True},
            {"技能": "质量记录与可追溯管理", "正确": True},
        ],
    )
    advanced = apply_feedback(intermediate, "进阶挑战")

    profiles = [
        {"label": "入门 — 新入职质检员（冷启动）", "profile": beginner},
        {"label": "应用 — 有经验质检员（答题更新）", "profile": intermediate},
        {"label": "进阶 — 熟练质检员（反馈进阶挑战）", "profile": advanced},
    ]

    print("\n  岗位能力模型来源：")
    print("    - 《机械产品检验员行业评价规范》")
    print("    - GB/T 2828.1-2012 计数抽样检验标准")
    print("    - 8 项技能 × 4 个难度层级（入门/基础/进阶/专家）")

    for entry in profiles:
        p = entry["profile"]
        print(f"\n  --- {entry['label']} ---")
        print(f"  推荐难度: {p['推荐难度']}")
        print(f"  目标技能: {'、'.join(p['目标技能'])}")
        print(f"  最弱4项技能掌握度:")
        for skill, level in sorted(p["技能掌握度"].items(), key=lambda x: x[1])[:4]:
            bar = "#" * int(level * 20) + "-" * (20 - int(level * 20))
            print(f"    [{bar}] {skill}: {level:.2f}")
        # Show learning path top 3
        if p.get("学习路径"):
            print(f"  学习路径 (Top 3):")
            for lp in p["学习路径"][:3]:
                print(
                    f"    {lp['优先级']}. {lp['技能']} "
                    f"-> {lp['推荐资源类型']} "
                    f"({'先修已满足' if lp['先修已满足'] else '先修未满足'})"
                )

    return {
        "segment": "画像",
        "duration_sec": TIMING["画像"],
        "profiles": [
            {
                "label": entry["label"],
                "推荐难度": entry["profile"]["推荐难度"],
                "目标技能": entry["profile"]["目标技能"],
                "技能掌握度": entry["profile"]["技能掌握度"],
                "学习路径": entry["profile"].get("学习路径", [])[:3],
            }
            for entry in profiles
        ],
    }


def demo_part3_检索证据() -> dict[str, Any]:
    """Part 3: Knowledge Retrieval with Evidence (1 min)."""
    print_section("Part 3: 检索证据 — 可溯源知识检索", TIMING["检索证据"])

    topic = "量具使用与质量检测"
    knowledge = search_knowledge(topic)

    print(f"\n  检索主题: {topic}")
    print(f"  命中知识: {len(knowledge)} 条（来自 ChromaDB，39条已验证知识）")
    print(f"  检索方式: 中文字符 n-gram 哈希向量 + 相似度阈值过滤")

    for item in knowledge:
        print(f"\n  [{item['知识ID']}] (score={item['检索分数']:.2f})")
        print(f"  内容: {item['内容']}")
        print(f"  来源: {item['来源']}")
        print(f"  定位: {item['来源定位']}")
        print(f"  验证状态: {item['验证状态']}")

    print(f"\n  >> 只有'已验证'状态的知识才能进入生成环节")
    print(f"  >> 每条知识必须标注来源和可定位的出处")

    return {
        "segment": "检索证据",
        "duration_sec": TIMING["检索证据"],
        "topic": topic,
        "knowledge_count": len(knowledge),
        "knowledge_items": [
            {
                "知识ID": item["知识ID"],
                "内容": item["内容"],
                "来源": item["来源"],
                "来源定位": item["来源定位"],
                "检索分数": item["检索分数"],
            }
            for item in knowledge
        ],
    }


def demo_part4_差异生成() -> dict[str, Any]:
    """Part 4: Differentiated Generation (2 min)."""
    print_section("Part 4: 差异生成 — 同一主题，三种画像，三种输出", TIMING["差异生成"])

    topic = "量具使用与质量检测"
    knowledge = search_knowledge(topic)
    if not knowledge:
        raise RuntimeError(f"No knowledge for: {topic}")

    beginner = build_profile("质检员")
    intermediate = build_profile(
        "质检员",
        [
            {"技能": "不合格品处理与8D报告", "正确": True},
            {"技能": "不合格品处理与8D报告", "正确": True},
            {"技能": "抽样检验标准应用", "正确": True},
            {"技能": "质量记录与可追溯管理", "正确": True},
        ],
    )
    advanced = apply_feedback(intermediate, "进阶挑战")

    profiles = [
        ("入门", beginner),
        ("应用", intermediate),
        ("进阶", advanced),
    ]

    results = []
    for label, profile in profiles:
        content = generate_content(profile, knowledge, topic)
        evaluation = evaluate(content, knowledge, profile)

        print(f"\n  --- {label} 画像 ---")
        print(f"  推荐难度: {profile['推荐难度']}")
        print(f"  资源类型: {content['类型']}")
        print(f"  标题: {content['标题']}")
        print(f"  生成模式: {content['生成模式']}")
        print(f"  引用知识ID: {content['引用知识ID']}")
        print(f"  内容预览:")
        for line in content["正文"].split("\n")[:10]:
            print(f"    {line}")
        if len(content["正文"].split("\n")) > 10:
            print(f"    ... (共 {len(content['正文'].splitlines())} 行)")

        results.append(
            {
                "label": label,
                "推荐难度": profile["推荐难度"],
                "资源类型": content["类型"],
                "标题": content["标题"],
                "引用知识ID": content["引用知识ID"],
                "正文全文": content["正文"],
                "评估结果": evaluation,
            }
        )

    # Summary comparison
    print(f"\n  --- 差异化对比总结 ---")
    print(f"  {'画像':<8} {'资源类型':<12} {'推荐难度':<8}")
    print(f"  {'-'*30}")
    for r in results:
        print(f"  {r['label']:<8} {r['资源类型']:<12} {r['推荐难度']:<8}")

    types = {r["资源类型"] for r in results}
    expected = {"定制讲义", "实操指南", "分阶测试题"}
    print(f"\n  >> 三种画像产出三种不同资源类型: {types == expected}")

    return {
        "segment": "差异生成",
        "duration_sec": TIMING["差异生成"],
        "topic": topic,
        "results": results,
        "three_distinct_types": types == expected,
    }


def demo_part5_审核驳回() -> dict[str, Any]:
    """Part 5: Review & Rejection (2 min)."""
    print_section("Part 5: 审核驳回 — 三层审核拦截问题内容", TIMING["审核驳回"])

    topic = "M代码编程"
    knowledge = search_knowledge(topic)
    if not knowledge:
        raise RuntimeError(f"No knowledge for: {topic}")

    profile = build_profile("CNC编程员")
    content = generate_content(profile, knowledge, topic)

    print(f"\n  原始内容: {content['标题']}")
    print(f"  引用知识ID: {content['引用知识ID']}")

    # Implant a baseless assertion
    import copy
    bad_content = copy.deepcopy(content)
    fake_assertion = "\n- 伪造断言：主轴转速必须固定在 1000 rpm。 [FAKE-002]"
    bad_content["正文"] += fake_assertion
    bad_content["引用知识ID"] = bad_content["引用知识ID"] + ["FAKE-002"]

    print(f"\n  >> 植入无依据断言: {fake_assertion.strip()}")
    print(f"  >> 修改后引用知识ID: {bad_content['引用知识ID']}")

    # Review the bad content
    review = review_content(bad_content, knowledge)

    print(f"\n  --- L1 规则检查 ---")
    print(f"  结果: {review['审核明细']['规则引擎']}")
    problems = review["审核明细"].get("规则问题", [])
    if problems:
        for p in problems:
            print(f"    - {p}")
    else:
        print(f"  (L1 规则通过)")

    print(f"\n  --- L2 知识锚定 ---")
    print(f"  结果: {review['审核明细']['知识锚定']}")
    print(f"  幻觉分数: {review['幻觉分数']:.2%}")
    print(f"  风险等级: {review['审核明细']['风险等级']}")
    if review.get("断言核查"):
        for claim in review["断言核查"]:
            print(f"    [{claim['状态']}] {claim['断言'][:60]}...")

    print(f"\n  --- 审核结论 ---")
    print(f"  流程状态: {review['流程状态']}")
    print(f"  审核通过: {review['通过']}")
    print(f"  修改建议: {review.get('修改建议', 'N/A')}")

    # Also demonstrate uncovered topic rejection
    print(f"\n  --- 未覆盖主题的安全拒答 ---")
    reject_result = search_knowledge("工业互联网网关配置")
    print(f"  主题: 工业互联网网关配置")
    print(f"  知识命中: {len(reject_result)} 条")
    print(f"  系统行为: {'拒答（知识库未覆盖）' if not reject_result else '正常生成'}")

    return {
        "segment": "审核驳回",
        "duration_sec": TIMING["审核驳回"],
        "original_content_title": content["标题"],
        "implanted_assertion": fake_assertion.strip(),
        "review_result": {
            "流程状态": review["流程状态"],
            "通过": review["通过"],
            "幻觉分数": review["幻觉分数"],
            "修改建议": review.get("修改建议", ""),
            "审核明细": review["审核明细"],
            "断言核查": review.get("断言核查", []),
        },
        "uncovered_rejection": {
            "topic": "工业互联网网关配置",
            "knowledge_hits": len(reject_result),
            "behavior": "拒答" if not reject_result else "正常生成",
        },
    }


def demo_part6_自动修正() -> dict[str, Any]:
    """Part 6: Auto-correction (1 min)."""
    print_section("Part 6: 自动修正 — 根据审核建议重新生成", TIMING["自动修正"])

    topic = "M代码编程"
    knowledge = search_knowledge(topic)
    if not knowledge:
        raise RuntimeError(f"No knowledge for: {topic}")

    profile = build_profile("CNC编程员")
    content = generate_content(profile, knowledge, topic)

    # Implant bad assertion
    import copy
    bad_content = copy.deepcopy(content)
    bad_content["正文"] += "\n- 伪造断言：主轴转速必须固定在 1000 rpm。 [FAKE-002]"
    bad_content["引用知识ID"] = bad_content["引用知识ID"] + ["FAKE-002"]

    # Review -> get advice -> regenerate
    review_before = review_content(bad_content, knowledge)
    advice = review_before.get("修改建议", "删除无依据断言")

    print(f"\n  Step 1: 审核发现无依据断言")
    print(f"  修改建议: {advice}")

    # Regenerate with advice
    regenerated = generate_content(profile, knowledge, topic, advice)

    print(f"\n  Step 2: 根据建议重新生成")
    print(f"  新标题: {regenerated['标题']}")
    print(f"  新引用知识ID: {regenerated['引用知识ID']}")
    # Verify FAKE-002 is gone
    has_fake = "FAKE-002" in regenerated.get("引用知识ID", [])
    print(f"  FAKE-002 残留: {has_fake}")

    # Re-review
    review_after = review_content(regenerated, knowledge)

    print(f"\n  Step 3: 重新审核")
    print(f"  流程状态: {review_after['流程状态']}")
    print(f"  审核通过: {review_after['通过']}")
    print(f"  幻觉分数: {review_after['幻觉分数']:.2%}")

    print(f"\n  >> 修正成功: {review_after.get('通过', False)}")
    print(f"  >> 闭环: 生成 -> 审核 -> 驳回 -> 修改建议 -> 重生成 -> 再审核")

    return {
        "segment": "自动修正",
        "duration_sec": TIMING["自动修正"],
        "before": {
            "had_fake_id": "FAKE-002" in bad_content["引用知识ID"],
            "review_failed": not review_before["通过"],
            "advice": advice,
        },
        "after": {
            "had_fake_id": "FAKE-002" in regenerated.get("引用知识ID", []),
            "review_passed": review_after.get("通过", False),
            "hallucination_score": review_after.get("幻觉分数", 1.0),
            "new_content_title": regenerated["标题"],
            "new_content_ids": regenerated["引用知识ID"],
        },
        "correction_successful": review_after.get("通过", False),
    }


def demo_part7_可信边界() -> dict[str, Any]:
    """Part 7: Trust Boundary (1 min)."""
    print_section("Part 7: 可信边界 — 系统的能力与限制", TIMING["可信边界"])

    boundaries = {
        "segment": "可信边界",
        "duration_sec": TIMING["可信边界"],
        "can_do": [
            "基于已验证知识生成三种难度级别的培训内容",
            "确定性 L1 规则检查（格式、引用、来源验证）",
            "确定性 L2 知识锚定（逐断言核查知识依据）",
            "自动闭环修正（审核驳回 → 修改建议 → 重生成）",
            "未覆盖主题的安全拒答",
            "离线运行（无需 API Key 即可验证核心逻辑）",
        ],
        "cannot_do": [
            "L3 异构模型投票（需要 DeepSeek/Qwen/GLM 的真实 Key）",
            "人工双人复核替代（机器初标 ≠ 人工结论）",
            "覆盖知识库之外的专业领域",
            "实时更新知识库（当前为静态构建）",
        ],
        "limitations": [
            "52 条 QA 评测集均为机器初标，待人工双人复核",
            "离线生成内容为确定性模板，不如真实 LLM 丰富",
            "L3 无 Key 时转'需人工复核'，不伪造投票结果",
            "3 个扩展岗位（焊接/工业互联网/AI）知识未核验",
        ],
    }

    print(f"\n  --- 系统能力 ---")
    for item in boundaries["can_do"]:
        print(f"  [+] {item}")

    print(f"\n  --- 当前限制 ---")
    for item in boundaries["cannot_do"]:
        print(f"  [-] {item}")

    print(f"\n  --- 可信边界总结 ---")
    for item in boundaries["limitations"]:
        print(f"  [!] {item}")

    print(f"\n  >> 可信边界 = 已验证知识 + 离线审核闭环 + 确定性规则")
    print(f"  >> 不把机器初标当正式指标，不伪造模型调用证据")

    return boundaries


def run_demo(replay: bool = False) -> int:
    """Run the full 10-minute demo."""
    demo_start = datetime.now(timezone.utc)

    print("=" * 60)
    print("  智策育训 — 10分钟演示脚本 v1")
    print("  个性化培训内容自动生成平台")
    print(f"  模式: {'REPLAY (from saved)' if replay else 'OFFLINE (deterministic)'}")
    print(f"  时间: {demo_start.isoformat()}")
    print("=" * 60)

    total_duration = sum(TIMING.values())
    print(f"\n  总时长: {total_duration // 60}:{total_duration % 60:02d}")
    print(f"  7 个段落: 痛点 -> 画像 -> 检索 -> 生成 -> 审核 -> 修正 -> 边界")

    # Run all 7 parts
    parts = []
    start_time = time.perf_counter()

    # Part 1: Pain Point
    parts.append(demo_part1_痛点())

    # Part 2: Profile
    parts.append(demo_part2_画像())

    # Part 3: Knowledge Retrieval
    parts.append(demo_part3_检索证据())

    # Part 4: Differentiated Generation
    parts.append(demo_part4_差异生成())

    # Part 5: Review & Rejection
    parts.append(demo_part5_审核驳回())

    # Part 6: Auto-correction
    parts.append(demo_part6_自动修正())

    # Part 7: Trust Boundary
    parts.append(demo_part7_可信边界())

    elapsed = time.perf_counter() - start_time

    # ── Final summary ──
    print(f"\n{'='*60}")
    print(f"  Demo Complete")
    print(f"{'='*60}")
    print(f"  Actual execution time: {elapsed:.2f}s")
    print(f"  Target presentation time: {total_duration // 60}:{total_duration % 60:02d}")
    print(f"  Parts completed: {len(parts)}/7")

    # Save full output for replay
    demo_output = {
        "demo_version": "v1",
        "run_at": demo_start.isoformat(),
        "mode": "offline" if not replay else "replay",
        "total_duration_target_sec": total_duration,
        "actual_execution_sec": round(elapsed, 3),
        "timing": TIMING,
        "parts": parts,
    }

    output_path = OUTPUT_DIR / "demo_output.json"
    output_path.write_text(
        json.dumps(demo_output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  Demo output saved: {output_path}")
    return 0


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="P4 10-minute demo script v1")
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Replay from saved demo output (offline/no-compute mode)",
    )
    args = parser.parse_args()

    if args.replay:
        replay_path = OUTPUT_DIR / "demo_output.json"
        if not replay_path.exists():
            print(f"[ERROR] No saved demo output at: {replay_path}")
            print(f"        Run without --replay first to generate demo output.")
            return 1
        data = json.loads(replay_path.read_text(encoding="utf-8"))
        print("=" * 60)
        print("  REPLAY MODE — Reading from saved demo output")
        print(f"  Original run: {data.get('run_at', 'unknown')}")
        print(f"  Parts: {len(data.get('parts', []))}")
        print("=" * 60)
        for i, part in enumerate(data.get("parts", []), 1):
            segment = part.get("segment", f"Part {i}")
            duration = part.get("duration_sec", 60)
            print_section(f"Part {i}: {segment}", duration)
            print(f"\n  (Saved output — {len(json.dumps(part, ensure_ascii=False))} bytes)")
            # Print key findings from each part
            if segment == "痛点":
                for cp in part.get("challenges", []):
                    print(f"  >> {cp['challenge']}: {cp['detail'][:80]}...")
            elif segment == "差异生成":
                for r in part.get("results", []):
                    print(f"  {r['label']}: {r['资源类型']} — {r['标题']}")
            elif segment == "审核驳回":
                rev = part.get("review_result", {})
                print(f"  Status: {rev.get('流程状态')}, Hallucination: {rev.get('幻觉分数', 0):.2%}")
            elif segment == "自动修正":
                print(f"  Correction successful: {part.get('correction_successful')}")
            elif segment == "可信边界":
                for item in part.get("can_do", [])[:3]:
                    print(f"  [+] {item}")
                for item in part.get("limitations", [])[:2]:
                    print(f"  [!] {item}")
        print(f"\n  [REPLAY COMPLETE] Full data in: {replay_path}")
        return 0

    return run_demo(replay=False)


if __name__ == "__main__":
    raise SystemExit(main())
