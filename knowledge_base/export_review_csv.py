"""校验评测集结构，并导出不含人工结论的双人复核 CSV。

本脚本只准备人工复核材料，不会填写标注者结论，也不会修改
``qa_test_set.json`` 的标注状态。
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_PATH = ROOT / "knowledge_base" / "qa_test_set.json"
DEFAULT_KNOWLEDGE_PATH = ROOT / "data" / "knowledge.json"
DEFAULT_OUTPUT_PATH = ROOT / "data" / "review" / "qa_pilot_12_review.csv"

CASE_FIELDS = [
    "案例ID",
    "问题",
    "岗位",
    "画像组",
    "目标难度",
    "预期知识ID",
    "参考答案",
    "依据来源",
    "来源定位",
    "标注状态",
]

REVIEW_FIELDS = [
    "标注者A编号",
    "A复核日期",
    "A问题与岗位匹配",
    "A预期知识ID正确",
    "A参考答案正确完整",
    "A来源定位有效且支持答案",
    "A结论",
    "A修改建议",
    "标注者B编号",
    "B复核日期",
    "B问题与岗位匹配",
    "B预期知识ID正确",
    "B参考答案正确完整",
    "B来源定位有效且支持答案",
    "B结论",
    "B修改建议",
    "一致性结论",
    "分歧原因",
    "仲裁者编号",
    "仲裁日期",
    "仲裁结论",
    "仲裁说明",
    "最终标注状态",
]

ALLOWED_STATUSES = {
    "机器初标，待人工双人复核",
    "人工复核中",
    "待仲裁",
    "已人工复核",
}
PENDING_STATUSES = ALLOWED_STATUSES - {"已人工复核"}


def load_json_list(path: Path, label: str) -> list[dict[str, Any]]:
    """读取顶层为对象列表的 JSON 文件。"""
    if not path.exists():
        raise FileNotFoundError(f"{label}文件不存在：{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{label}文件顶层必须是列表")
    if not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{label}文件中的每一项都必须是对象")
    return data


def validate_cases(
    cases: list[dict[str, Any]],
    knowledge_items: list[dict[str, Any]],
) -> None:
    """校验案例唯一性、来源定位、状态和知识绑定。"""
    knowledge_by_id: dict[str, dict[str, Any]] = {}
    for item in knowledge_items:
        knowledge_id = item.get("知识ID")
        if not isinstance(knowledge_id, str) or not knowledge_id.strip():
            raise ValueError("知识条目缺少有效知识ID")
        if knowledge_id in knowledge_by_id:
            raise ValueError(f"知识ID重复：{knowledge_id}")
        if not isinstance(item.get("来源定位"), str) or not item["来源定位"].strip():
            raise ValueError(f"知识 {knowledge_id} 缺少来源定位")
        knowledge_by_id[knowledge_id] = item

    seen_case_ids: set[str] = set()
    for index, case in enumerate(cases, start=1):
        missing_fields = [field for field in CASE_FIELDS if field not in case]
        if missing_fields:
            raise ValueError(
                f"第 {index} 条案例缺少字段：{', '.join(missing_fields)}"
            )

        case_id = case["案例ID"]
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"第 {index} 条案例缺少有效案例ID")
        if case_id in seen_case_ids:
            raise ValueError(f"案例ID重复：{case_id}")
        seen_case_ids.add(case_id)

        source_location = case["来源定位"]
        if not isinstance(source_location, str) or not source_location.strip():
            raise ValueError(f"案例 {case_id} 缺少来源定位")

        status = case["标注状态"]
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"案例 {case_id} 使用非法标注状态：{status}")

        expected_ids = case["预期知识ID"]
        if (
            not isinstance(expected_ids, list)
            or not expected_ids
            or not all(
                isinstance(knowledge_id, str) and knowledge_id.strip()
                for knowledge_id in expected_ids
            )
        ):
            raise ValueError(f"案例 {case_id} 的预期知识ID必须是非空字符串列表")

        missing_ids = [
            knowledge_id
            for knowledge_id in expected_ids
            if knowledge_id not in knowledge_by_id
        ]
        if missing_ids:
            raise ValueError(
                f"案例 {case_id} 引用了不存在的知识ID：{', '.join(missing_ids)}"
            )

        bound_items = [knowledge_by_id[knowledge_id] for knowledge_id in expected_ids]
        if not any(
            item.get("来源") == case["依据来源"]
            and item.get("来源定位") == source_location
            for item in bound_items
        ):
            raise ValueError(
                f"案例 {case_id} 的依据来源或来源定位与预期知识ID不一致"
            )


def select_pending_cases(
    cases: list[dict[str, Any]],
    *,
    case_ids: list[str] | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """按指定 ID 或原始顺序选择尚未完成人工复核的案例。"""
    pending = {
        case["案例ID"]: case
        for case in cases
        if case["标注状态"] in PENDING_STATUSES
    }

    if case_ids:
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("命令行指定的案例ID不能重复")
        missing = [case_id for case_id in case_ids if case_id not in pending]
        if missing:
            raise ValueError(
                "以下案例不存在或已完成人工复核：" + ", ".join(missing)
            )
        return [pending[case_id] for case_id in case_ids]

    if limit <= 0:
        raise ValueError("limit 必须大于 0")
    return list(pending.values())[:limit]


def export_review_csv(
    cases_path: Path = DEFAULT_CASES_PATH,
    knowledge_path: Path = DEFAULT_KNOWLEDGE_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    *,
    case_ids: list[str] | None = None,
    limit: int = 12,
) -> int:
    """导出复核表并返回行数；所有人工填写列均为空。"""
    cases = load_json_list(cases_path, "评测集")
    knowledge_items = load_json_list(knowledge_path, "知识库")
    validate_cases(cases, knowledge_items)
    selected = select_pending_cases(cases, case_ids=case_ids, limit=limit)
    if not selected:
        raise ValueError("没有待人工复核案例可导出")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASE_FIELDS + REVIEW_FIELDS)
        writer.writeheader()
        for case in selected:
            row = {field: case[field] for field in CASE_FIELDS}
            row["预期知识ID"] = "|".join(case["预期知识ID"])
            row.update({field: "" for field in REVIEW_FIELDS})
            writer.writerow(row)
    return len(selected)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="校验评测集并导出不代填人工结论的双人复核 CSV"
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--knowledge", type=Path, default=DEFAULT_KNOWLEDGE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        help="指定待导出的案例ID；可重复传入以保持指定顺序",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="未指定 --case-id 时按原始顺序导出的数量（默认 12）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = export_review_csv(
        cases_path=args.cases,
        knowledge_path=args.knowledge,
        output_path=args.output,
        case_ids=args.case_ids,
        limit=args.limit,
    )
    print(f"已导出 {count} 条空白人工复核记录：{args.output}")
    print("人工填写列均为空；本脚本未修改 qa_test_set.json 的标注状态。")


if __name__ == "__main__":
    main()
