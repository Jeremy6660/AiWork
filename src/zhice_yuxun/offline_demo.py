"""人工全链路演示脚本。

自动化验收请运行 ``pytest -q``。本脚本只展示三个代表场景；任何场景失败时
返回非零退出码，不再打印“失败但跑通”的假阳性结论。
"""

from __future__ import annotations

import os

# 本脚本是离线验收入口。即使本机 .env 配置了真实 Key，也绝不产生 API 请求。
os.environ["GENERATION_MODE"] = "offline"
os.environ["ENABLE_LLM_REVIEW"] = "0"
os.environ["ENABLE_L3_VOTING"] = "0"
os.environ["ALLOW_OFFLINE_FALLBACK"] = "1"

from .orchestrator import run


SCENARIOS = [
    {
        "名称": "冷启动：数控机床操作工",
        "岗位": "数控机床操作工",
        "答题记录": [],
        "主题": "数控机床安全操作",
    },
    {
        "名称": "答题更新：CNC编程员",
        "岗位": "CNC编程员",
        "答题记录": [
            {"技能": "程序仿真验证与首件试切", "正确": False},
            {"技能": "程序仿真验证与首件试切", "正确": False},
            {"技能": "切削参数优化与刀具路径规划", "正确": True},
        ],
        "主题": "加工缺陷分析与排除",
    },
    {
        "名称": "岗位差异：质检员",
        "岗位": "质检员",
        "答题记录": [],
        "主题": "量具使用与质量检测",
    },
]


def _print_result(result: dict) -> None:
    print(f"流程状态：{result['流程状态']}")
    print(f"目标技能：{'、'.join(result['画像'].get('目标技能', []))}")
    print(f"知识命中：{len(result['知识列表'])} 条")
    if result["培训内容"]:
        print(
            f"培训资源：[{result['培训内容']['类型']}] "
            f"{result['培训内容']['标题']}"
        )
        print(f"生成模式：{result['培训内容']['生成模式']}")
    print(
        f"审核：{'通过' if result['审核通过'] else '未通过'} | "
        f"幻觉分数={result['幻觉分数']:.2%} | 重新生成={result['重试次数']}"
    )
    print(f"单份内容综合诊断：{result['评估结果']['综合分']:.2%}")
    if result.get("失败原因"):
        print(f"失败原因：{result['失败原因']}")


def main() -> int:
    failures: list[str] = []
    for scenario in SCENARIOS:
        print("\n" + "=" * 68)
        print(scenario["名称"])
        print("=" * 68)
        result = run(
            scenario["岗位"],
            scenario["答题记录"],
            scenario["主题"],
        )
        _print_result(result)
        if result["流程状态"] != "通过" or not result["审核通过"]:
            failures.append(scenario["名称"])

    print("\n" + "=" * 68)
    if failures:
        print("[FAIL] 全链路验收失败：" + "、".join(failures))
        return 1
    print("[PASS] 三个演示场景均通过；完整自动化结果请以 pytest 为准。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
