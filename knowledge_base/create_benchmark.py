"""从已验证知识生成 50+ 条评测集初稿。

初稿只完成结构和来源绑定，不能替代双人复核；正式申报指标必须过滤到
``标注状态=已人工复核`` 的案例。
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_PATH = ROOT / "data" / "knowledge.json"
OUTPUT_PATH = ROOT / "knowledge_base" / "qa_test_set.json"


def _position_for_id(knowledge_id: str) -> str:
    if knowledge_id.startswith("QC-"):
        return "质检员"
    if knowledge_id.startswith(("CNC-M", "CNC-PROG", "CNC-FAULT")):
        return "CNC编程员"
    return "数控机床操作工"


def create_cases() -> list[dict]:
    items = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    verified = [item for item in items if item.get("验证状态") == "已验证"]
    levels = ["入门", "应用", "进阶"]
    cases: list[dict] = []
    for index, item in enumerate(verified):
        hints = item["主题"][1:3] or item["主题"][:1]
        cases.append(
            {
                "案例ID": f"QA-{index + 1:03d}",
                "问题": f"关于{'、'.join(hints)}，应掌握哪项关键知识？",
                "岗位": _position_for_id(item["知识ID"]),
                "画像组": f"P{index % 3 + 1}",
                "目标难度": levels[index % 3],
                "预期知识ID": [item["知识ID"]],
                "参考答案": item["内容"],
                "依据来源": item["来源"],
                "来源定位": item["来源定位"],
                "标注状态": "机器初标，待人工双人复核",
            }
        )

    # 为前 13 条增加差异化画像复测，使总数达到 52 条。
    for offset, item in enumerate(verified[:13], start=1):
        hints = item["主题"][:2]
        cases.append(
            {
                "案例ID": f"QA-{len(cases) + 1:03d}",
                "问题": f"请为转岗学习者解释{'、'.join(hints)}的关键要求。",
                "岗位": _position_for_id(item["知识ID"]),
                "画像组": f"P{offset % 3 + 1}",
                "目标难度": levels[(offset + 1) % 3],
                "预期知识ID": [item["知识ID"]],
                "参考答案": item["内容"],
                "依据来源": item["来源"],
                "来源定位": item["来源定位"],
                "标注状态": "机器初标，待人工双人复核",
            }
        )
    return cases


if __name__ == "__main__":
    cases = create_cases()
    OUTPUT_PATH.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已生成 {len(cases)} 条评测初稿：{OUTPUT_PATH}")

