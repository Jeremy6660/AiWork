"""P4 消融实验脚本：个性化、审核强度、覆盖/拒答、审核修正对比。

本脚本严格使用离线确定性模式，不读取或调用任何外部 API。结果保存到
artifacts/p4_ablation_experiments_20260730/ 目录。

执行方式：
    python scripts/p4_ablation_experiments.py
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ── 离线确定性实验环境 ──────────────────────────────────────────
os.environ["GENERATION_MODE"] = "offline"
os.environ["ENABLE_LLM_REVIEW"] = "0"
os.environ["ENABLE_L3_VOTING"] = "0"
os.environ["ALLOW_OFFLINE_FALLBACK"] = "1"

from src.zhice_yuxun.agents.evaluator import evaluate
from src.zhice_yuxun.agents.generator import generate_content
from src.zhice_yuxun.agents.profile import apply_feedback, build_profile
from src.zhice_yuxun.agents.retrieval import search_knowledge
from src.zhice_yuxun.agents.reviewer import review_content
from src.zhice_yuxun.llm_client import available_providers
from src.zhice_yuxun.orchestrator import run

OUTPUT_DIR = Path(
    os.getenv(
        "P4_OUTPUT_DIR",
        str(ROOT / "artifacts" / "p4_ablation_experiments_20260730"),
    )
).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 工具函数 ────────────────────────────────────────────────────


def git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def run_timed(fn: Any, *args: Any, **kwargs: Any) -> tuple[Any, float]:
    start = time.perf_counter()
    output = fn(*args, **kwargs)
    return output, time.perf_counter() - start


def save_experiment(filename: str, data: dict[str, Any]) -> None:
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {path.name}")


def log_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 实验 A：画像差异化 ──────────────────────────────────────────


def make_profiles() -> list[dict[str, Any]]:
    """构造入门/应用/进阶三组画像。"""
    base = build_profile("质检员")
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
    return [
        {"label": "入门", "profile": base},
        {"label": "应用", "profile": intermediate},
        {"label": "进阶", "profile": advanced},
    ]


def experiment_personalization(
    topic: str, knowledge: list[dict[str, Any]]
) -> dict[str, Any]:
    """实验 A：同一问题下三种画像的资源类型和内容差异。"""
    log_section("实验 A：画像差异化")
    profiles = make_profiles()
    results: list[dict[str, Any]] = []

    for entry in profiles:
        profile = entry["profile"]
        content, elapsed = run_timed(generate_content, profile, knowledge, topic)
        evaluation = evaluate(content, knowledge, profile)
        result_entry = {
            "画像难度": entry["label"],
            "推荐难度": profile["推荐难度"],
            "资源类型": content["类型"],
            "标题": content["标题"],
            "生成模式": content["生成模式"],
            "目标技能": profile["目标技能"],
            "技能掌握度摘要": dict(
                sorted(profile["技能掌握度"].items(), key=lambda x: x[1])[:4]
            ),
            "正文全文": content["正文"],
            "引用知识ID": content["引用知识ID"],
            "引用来源": content["引用来源"],
            "耗时": round(elapsed, 4),
            "评估结果": evaluation,
        }
        results.append(result_entry)
        print(
            f"  {entry['label']}: type={content['类型']}, "
            f"skills={profile['目标技能']}, "
            f"time={elapsed:.4f}s"
        )

    # 验证三种画像产出不同资源类型
    types = {r["资源类型"] for r in results}
    expected = {"定制讲义", "实操指南", "分阶测试题"}
    print(f"  Resource types: {types} (expected: {expected})")

    exp_data = {
        "experiment_id": "A",
        "description": "同一问题下，入门/应用/进阶三种画像的生成资源对比",
        "topic": topic,
        "position": "质检员",
        "strategy": "generate_content(画像, 知识列表, 主题)",
        "validation": {
            "three_distinct_types": types == expected,
            "observed_types": sorted(types),
        },
        "results": results,
    }
    save_experiment("exp_A_personalization.json", exp_data)
    return exp_data


# ── 实验 B：审核强度对比 ────────────────────────────────────────


def experiment_audit_strength(
    topic: str, knowledge: list[dict[str, Any]]
) -> dict[str, Any]:
    """实验 B：无审核、L1+L2、L1+L2+L3（无Key）三种审核强度。"""
    log_section("实验 B：审核强度对比")
    profile = build_profile("数控机床操作工")
    base_content = generate_content(profile, knowledge, topic)
    results: list[dict[str, Any]] = []

    # ── B1: 无审核基线 ──
    no_review_eval, no_review_time = run_timed(
        evaluate, base_content, knowledge, profile
    )
    results.append(
        {
            "label": "无审核",
            "description": "直接生成内容，不进入审核流程；展示生成原始质量。",
            "流程状态": "未审核",
            "审核通过": None,
            "幻觉分数": None,
            "修改建议": None,
            "审核明细": None,
            "评估结果": no_review_eval,
            "耗时": round(no_review_time, 4),
        }
    )
    print(f"  No-review: score={no_review_eval['综合分']:.2%}, time={no_review_time:.4f}s")

    # ── B2: L1+L2（完整 orchestrator 流程）──
    os.environ["ENABLE_L3_VOTING"] = "0"
    l1l2_result, l1l2_time = run_timed(run, "数控机床操作工", [], topic)
    results.append(
        {
            "label": "L1+L2",
            "description": "默认审核链路：L1 规则检查 + L2 确定性知识锚定。",
            "流程状态": l1l2_result["流程状态"],
            "审核通过": l1l2_result["审核通过"],
            "幻觉分数": l1l2_result["幻觉分数"],
            "修改建议": l1l2_result.get("失败原因") or None,
            "审核明细": l1l2_result.get("审核明细"),
            "断言核查": l1l2_result.get("断言核查", []),
            "评估结果": l1l2_result.get("评估结果"),
            "迭代历史": l1l2_result.get("迭代历史", []),
            "耗时": round(l1l2_time, 4),
        }
    )
    print(
        f"  L1+L2: status={l1l2_result['流程状态']}, "
        f"hallucination={l1l2_result['幻觉分数']:.2%}, "
        f"time={l1l2_time:.4f}s"
    )

    # ── B3: L1+L2+L3（无 Key，触发外部阻塞）──
    # 策略：用有效知识ID但写入矛盾断言，使 L1 规则通过但 L2 锚定产生
    # 高幻觉分数（>0.2），从而触发 L3 投票代码路径。
    # L3 无可用 Key 时 → available_providers=[] → 转"需人工复核"。
    old_keys = {}
    for env_key in ("DEEPSEEK_API_KEY", "QWEN_API_KEY", "GLM_API_KEY"):
        old_keys[env_key] = os.environ.get(env_key, "")
        os.environ[env_key] = ""
    os.environ["ENABLE_L3_VOTING"] = "1"

    # 构建矛盾内容：使用真实知识ID但写不同的事实
    real_ids = [item["知识ID"] for item in knowledge]
    l3_content = copy.deepcopy(base_content)
    contradictory_lines = [
        f"\n- 安全门打开时主轴应继续旋转以便观察。 [{real_ids[0]}]",
        f"\n- 切削液可直接排入下水道处理。 [{real_ids[1]}]",
    ]
    l3_content["正文"] += "".join(contradictory_lines)
    # 保持引用ID列表不变（矛盾行用的ID已在其中）

    l3_review, l3_time = run_timed(review_content, l3_content, knowledge)
    providers = available_providers()
    external_block = not providers
    l3_notes = [
        f"available_providers={providers}",
        "无可用模型 Key 时 L3 投票无法执行，转'需人工复核'。",
        "矛盾断言使用真实知识ID但写入相反内容，L2锚定判为无依据。",
    ]

    results.append(
        {
            "label": "L1+L2+L3（无 Key）",
            "description": (
                "向合规内容植入2条矛盾断言（有效知识ID但相反事实），"
                "L2锚定检出无依据→幻觉分>0.2→触发L3投票，无Key→转人工复核。"
            ),
            "流程状态": l3_review["流程状态"],
            "审核通过": l3_review["通过"],
            "幻觉分数": l3_review["幻觉分数"],
            "修改建议": l3_review.get("修改建议"),
            "审核明细": l3_review.get("审核明细"),
            "断言核查": l3_review.get("断言核查", []),
            "矛盾断言植入": contradictory_lines,
            "外部阻塞": external_block,
            "说明": "；".join(l3_notes),
            "耗时": round(l3_time, 4),
        }
    )
    print(
        f"  L1+L2+L3(no-key): status={l3_review['流程状态']}, "
        f"hallucination={l3_review['幻觉分数']:.2%}, "
        f"blocked={external_block}, time={l3_time:.4f}s"
    )

    # 恢复环境
    for env_key, value in old_keys.items():
        if value:
            os.environ[env_key] = value
        elif env_key in os.environ:
            del os.environ[env_key]
    os.environ["ENABLE_L3_VOTING"] = "0"

    exp_data = {
        "experiment_id": "B",
        "description": "三种审核强度对比：无审核、L1+L2、L1+L2+L3（无Key→外部阻塞）。",
        "topic": topic,
        "position": "数控机床操作工",
        "results": results,
    }
    save_experiment("exp_B_audit_strength.json", exp_data)
    return exp_data


# ── 实验 C：覆盖 vs 未覆盖 ───────────────────────────────────────


def experiment_coverage_vs_rejection() -> dict[str, Any]:
    """实验 C：正常覆盖问题与未覆盖问题的安全拒答对比。"""
    log_section("实验 C：覆盖 vs 未覆盖")
    test_cases = [
        ("数控机床安全操作", "覆盖问题", "期望：正常生成+审核通过"),
        ("工业互联网网关配置", "未覆盖问题", "期望：安全拒答，不生成专业内容"),
        ("核电站操作规程", "完全未覆盖", "期望：安全拒答，不越界生成"),
    ]
    results: list[dict[str, Any]] = []

    for topic, label, expectation in test_cases:
        result, elapsed = run_timed(run, "数控机床操作工", [], topic)
        entry = {
            "label": label,
            "topic": topic,
            "期望": expectation,
            "流程状态": result["流程状态"],
            "审核通过": result["审核通过"],
            "幻觉分数": result["幻觉分数"],
            "失败原因": result.get("失败原因", ""),
            "知识命中": len(result.get("知识列表", [])),
            "命中知识ID": [k["知识ID"] for k in result.get("知识列表", [])],
            "耗时": round(elapsed, 4),
        }
        results.append(entry)
        print(
            f"  {label}: status={result['流程状态']}, "
            f"knowledge_hits={len(result.get('知识列表', []))}, "
            f"time={elapsed:.4f}s"
        )

    exp_data = {
        "experiment_id": "C",
        "description": "覆盖问题与未覆盖问题的安全拒答对比。",
        "results": results,
    }
    save_experiment("exp_C_coverage_rejection.json", exp_data)
    return exp_data


# ── 实验 D：无依据断言 + 修正 ────────────────────────────────────


def experiment_bad_assertion_and_regen(
    topic: str, knowledge: list[dict[str, Any]]
) -> dict[str, Any]:
    """实验 D：植入无依据断言→审核发现→修改建议→重生成。"""
    log_section("实验 D：无依据断言 + 自动修正")
    profile = build_profile("CNC编程员")
    content = generate_content(profile, knowledge, topic)

    # 植入无依据断言（使用不存在的知识ID）
    bad_content = copy.deepcopy(content)
    bad_content["正文"] += "\n- 伪造断言：主轴转速必须固定在 1000 rpm。 [FAKE-002]"
    bad_content["引用知识ID"] = bad_content["引用知识ID"] + ["FAKE-002"]

    # Step 1: 审核发现
    review_before, before_time = run_timed(review_content, bad_content, knowledge)
    print(
        f"  Review before: passed={review_before['通过']}, "
        f"status={review_before['流程状态']}, "
        f"time={before_time:.4f}s"
    )
    print(f"  Problems: {review_before.get('修改建议', 'N/A')[:120]}")

    # Step 2: 根据审核建议重新生成
    advice = review_before.get("修改建议", "删除无依据断言")
    regenerated, regen_time = run_timed(
        generate_content, profile, knowledge, topic, advice
    )
    print(
        f"  Regenerated: type={regenerated['类型']}, "
        f"ids={regenerated['引用知识ID']}, "
        f"time={regen_time:.4f}s"
    )

    # Step 3: 重新审核
    review_after, after_time = run_timed(review_content, regenerated, knowledge)
    print(
        f"  Review after: passed={review_after['通过']}, "
        f"status={review_after['流程状态']}, "
        f"hallucination={review_after['幻觉分数']:.2%}, "
        f"time={after_time:.4f}s"
    )

    exp_data = {
        "experiment_id": "D",
        "description": "人工植入无依据断言，展示审核发现、修改建议和重生成结果。",
        "topic": topic,
        "position": "CNC编程员",
        "原始内容": {
            "标题": content["标题"],
            "类型": content["类型"],
            "正文全文": content["正文"],
            "引用知识ID": content["引用知识ID"],
        },
        "植入断言后": {
            "正文全文": bad_content["正文"],
            "引用知识ID": bad_content["引用知识ID"],
        },
        "审核发现": review_before,
        "审核发现耗时": round(before_time, 4),
        "修改建议": advice,
        "重生成结果": {
            "标题": regenerated["标题"],
            "类型": regenerated["类型"],
            "正文全文": regenerated["正文"],
            "引用知识ID": regenerated["引用知识ID"],
            "生成模式": regenerated["生成模式"],
        },
        "重生成耗时": round(regen_time, 4),
        "重审结果": review_after,
        "重审耗时": round(after_time, 4),
        "修正成功": review_after.get("通过", False),
    }
    save_experiment("exp_D_bad_assertion_fix.json", exp_data)
    return exp_data


# ── 主入口 ────────────────────────────────────────────────────────


def main() -> int:
    start = datetime.now(timezone.utc).isoformat()
    commit = git_commit_hash()

    print("=" * 60)
    print("  P4 Ablation Experiments")
    print(f"  Mode: OFFLINE (no API calls)")
    print(f"  Commit: {commit}")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60)

    # ── 实验 A：画像差异化 ──
    topic_a = "量具使用与质量检测"
    knowledge_a = search_knowledge(topic_a)
    if not knowledge_a:
        raise RuntimeError(f"Knowledge retrieval failed for: {topic_a}")
    print(f"\nExperiment A knowledge: {len(knowledge_a)} hits, "
          f"IDs: {[k['知识ID'] for k in knowledge_a]}")
    exp_a = experiment_personalization(topic_a, knowledge_a)

    # ── 实验 B：审核强度 ──
    topic_b = "数控机床安全操作"
    knowledge_b = search_knowledge(topic_b)
    if not knowledge_b:
        raise RuntimeError(f"Knowledge retrieval failed for: {topic_b}")
    print(f"\nExperiment B knowledge: {len(knowledge_b)} hits, "
          f"IDs: {[k['知识ID'] for k in knowledge_b]}")
    exp_b = experiment_audit_strength(topic_b, knowledge_b)

    # ── 实验 C：覆盖 vs 未覆盖 ──
    exp_c = experiment_coverage_vs_rejection()

    # ── 实验 D：无依据断言 + 修正 ──
    topic_d = "M代码编程"
    knowledge_d = search_knowledge(topic_d)
    if not knowledge_d:
        raise RuntimeError(f"Knowledge retrieval failed for: {topic_d}")
    print(f"\nExperiment D knowledge: {len(knowledge_d)} hits, "
          f"IDs: {[k['知识ID'] for k in knowledge_d]}")
    exp_d = experiment_bad_assertion_and_regen(topic_d, knowledge_d)

    # ── 汇总索引 ──
    summary = {
        "run_at": start,
        "git_commit": commit,
        "env": {
            "GENERATION_MODE": os.environ.get("GENERATION_MODE"),
            "ENABLE_LLM_REVIEW": os.environ.get("ENABLE_LLM_REVIEW"),
            "ENABLE_L3_VOTING": os.environ.get("ENABLE_L3_VOTING"),
            "ALLOW_OFFLINE_FALLBACK": os.environ.get("ALLOW_OFFLINE_FALLBACK"),
        },
        "experiments": [exp_a, exp_b, exp_c, exp_d],
        "per_experiment_files": [
            "exp_A_personalization.json",
            "exp_B_audit_strength.json",
            "exp_C_coverage_rejection.json",
            "exp_D_bad_assertion_fix.json",
        ],
    }
    index_path = OUTPUT_DIR / "p4_ablation_experiments.json"
    index_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    log_section("Summary")
    print(f"  Index: {index_path}")
    print(f"  Total experiments: {len(summary['experiments'])}")
    print(f"  Per-experiment files saved in: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
