"""评测入口：历史管线自检与可信完整链路盲测。

``run_benchmark`` 保留为历史管线自检，已弃用为正式依据。
``run_full_chain_evaluation`` 从原始问题调用 Orchestrator，不使用预期知识 ID。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.zhice_yuxun.agents.generator import generate_content
from src.zhice_yuxun.agents.profile import build_profile
from src.zhice_yuxun.agents.reviewer import review_content
from src.zhice_yuxun import orchestrator


DEFAULT_BLIND_SET_PATH = ROOT / "knowledge_base" / "training_blind_test_set.json"


def run_benchmark(include_draft: bool = False) -> dict:
    """历史管线自检（已弃用为正式依据）。"""
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def _forced_offline_blind_environment() -> Iterator[None]:
    """盲测期间强制零费用模式，结束后恢复调用者环境。"""

    forced = {
        "GENERATION_MODE": "offline",
        "ALLOW_DRAFT_TASKPKG": "1",
        "ENABLE_LLM_REVIEW": "0",
        "ENABLE_L3_VOTING": "0",
    }
    previous = {name: os.environ.get(name) for name in forced}
    os.environ.update(forced)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _actual_outcome(result: dict) -> str:
    status = result.get("流程状态")
    taskpkg = result.get("任务包")
    content = result.get("培训内容")
    if status == "失败":
        return "拒绝"
    if isinstance(taskpkg, dict) and status == "通过":
        return "命中任务包"
    if taskpkg is None and isinstance(content, dict) and bool(content):
        return "知识说明"
    return "未满足约定"


def run_full_chain_evaluation(blind_set_path: str | Path | None = None) -> dict:
    """从冻结问题进入 Orchestrator 的离线完整链路评测。"""

    path = Path(blind_set_path) if blind_set_path is not None else DEFAULT_BLIND_SET_PATH
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("盲测集必须是非空 JSON 数组")

    details: list[dict] = []
    consistent = 0
    expected_taskpkg = 0
    taskpkg_hits = 0
    expected_rejections = 0
    correct_rejections = 0

    with _forced_offline_blind_environment():
        for case in cases:
            expected = case["期望"]
            result = orchestrator.run(
                case["岗位"],
                question=case["问题"],
                学习场景=case["学习场景"],
            )
            actual = _actual_outcome(result)
            status = result.get("流程状态", "失败")
            taskpkg = result.get("任务包")
            taskpkg_id = (
                taskpkg.get("任务包ID") if isinstance(taskpkg, dict) else None
            )

            is_consistent = actual == expected
            consistent += int(is_consistent)
            if expected == "命中任务包":
                expected_taskpkg += 1
                taskpkg_hits += int(
                    isinstance(taskpkg, dict) and status == "通过"
                )
            if expected == "拒绝":
                expected_rejections += 1
                correct_rejections += int(status == "失败")

            details.append(
                {
                    "案例ID": case["案例ID"],
                    "类别": case["类别"],
                    "期望": expected,
                    "实际": actual,
                    "流程状态": status,
                    "任务包ID": taskpkg_id,
                }
            )

    count = len(cases)
    return {
        "数据状态": "非正式（草稿任务包）",
        "盲测集": path.name,
        "盲测哈希": _sha256(path),
        "总体一致率": round(consistent / count, 4),
        "任务包检索命中率": round(taskpkg_hits / expected_taskpkg, 4)
        if expected_taskpkg
        else 0.0,
        "正确拒绝率": round(correct_rejections / expected_rejections, 4)
        if expected_rejections
        else 0.0,
        "案例数": count,
        "明细": details,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-draft", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--blind", action="store_true", help="运行离线完整链路盲测")
    mode.add_argument("--blind-hash", action="store_true", help="打印冻结盲测集 SHA-256")
    args = parser.parse_args()
    if args.blind_hash:
        print(_sha256(DEFAULT_BLIND_SET_PATH))
    elif args.blind:
        print(json.dumps(run_full_chain_evaluation(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(run_benchmark(args.include_draft), ensure_ascii=False, indent=2))
