"""在固定知识与画像上计算可复现的三项指标。

默认拒绝把机器初标数据当成正式结果；传 ``--include-draft`` 仅用于验证评测
管线是否能运行，输出会明确标注“非正式”。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.zhice_yuxun.agents.generator import generate_content
from src.zhice_yuxun.agents.profile import build_profile
from src.zhice_yuxun.agents.reviewer import review_content


def run_benchmark(include_draft: bool = False) -> dict:
    knowledge = json.loads((ROOT / "data" / "knowledge.json").read_text(encoding="utf-8"))
    by_id = {item["知识ID"]: item for item in knowledge if item.get("验证状态") == "已验证"}
    cases = json.loads(
        (ROOT / "knowledge_base" / "qa_test_set.json").read_text(encoding="utf-8")
    )
    selected = [
        case
        for case in cases
        if include_draft or case.get("标注状态") == "已人工复核"
    ]
    if not selected:
        raise ValueError("没有已人工复核案例；仅验证管线时可使用 --include-draft")

    previous_mode = os.environ.get("GENERATION_MODE")
    os.environ["GENERATION_MODE"] = "offline"
    total_claims = 0
    invalid_claims = 0
    adapted = 0
    covered = 0
    details = []
    try:
        for case in selected:
            expected_ids = case["预期知识ID"]
            case_knowledge = [by_id[item] for item in expected_ids]
            profile = build_profile(case["岗位"])
            profile["推荐难度"] = case["目标难度"]
            content = generate_content(profile, case_knowledge, case["问题"])
            review = review_content(content, case_knowledge)
            checks = review.get("断言核查", [])
            invalid = sum(1 for item in checks if item["状态"] in {"无依据", "矛盾"})
            total_claims += len(checks)
            invalid_claims += invalid
            expected_type = {
                "入门": "定制讲义",
                "应用": "实操指南",
                "进阶": "分阶测试题",
            }[case["目标难度"]]
            type_ok = content["类型"] == expected_type
            coverage_ok = set(expected_ids).issubset(content["引用知识ID"])
            adapted += int(type_ok)
            covered += int(coverage_ok)
            details.append(
                {
                    "案例ID": case["案例ID"],
                    "幻觉断言": invalid,
                    "难度适配": type_ok,
                    "知识覆盖": coverage_ok,
                }
            )
    finally:
        if previous_mode is None:
            os.environ.pop("GENERATION_MODE", None)
        else:
            os.environ["GENERATION_MODE"] = previous_mode

    count = len(selected)
    return {
        "数据状态": "非正式：包含机器初标" if include_draft else "正式：仅人工复核",
        "案例数": count,
        "幻觉率": round(invalid_claims / total_claims, 4) if total_claims else 1.0,
        "难度适配准确率": round(adapted / count, 4),
        "核心知识覆盖率": round(covered / count, 4),
        "断言总数": total_claims,
        "明细": details,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-draft", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_benchmark(args.include_draft), ensure_ascii=False, indent=2))

