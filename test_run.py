"""
命令行快速测试脚本
不用启动 Streamlit 也能跑全链路，验证骨架是否跑通。
"""

from orchestrator import run


def test_all_scenarios():
    """测试多种场景，确保全链路跑通"""

    # ---- 场景 1：冷启动（无答题记录） ----
    print("=" * 60)
    print("场景 1：冷启动 — 数控机床操作工（无答题记录）")
    print("=" * 60)
    result = run(岗位="数控机床操作工", question="数控机床安全操作")
    _print_result(result)

    # ---- 场景 2：有答题记录 — 弱项在 M 代码 ----
    print("\n" + "=" * 60)
    print("场景 2：有答题记录 — CNC 编程员")
    print("=" * 60)
    result = run(
        岗位="CNC编程员",
        答题记录=[
            {"技能": "缺陷识别与排除", "正确": False},
            {"技能": "缺陷识别与排除", "正确": False},
            {"技能": "切削参数选择", "正确": True},
        ],
        question="加工缺陷分析与排除",
    )
    _print_result(result)

    # ---- 场景 3：质检员 ----
    print("\n" + "=" * 60)
    print("场景 3：质检员")
    print("=" * 60)
    result = run(岗位="质检员", question="量具使用与质量检测")
    _print_result(result)

    print("\n" + "=" * 60)
    print("✅ 所有场景测试完成！骨架跑通！")
    print("=" * 60)


def _print_result(result):
    """打印结果摘要"""
    print(f"画像: {result['画像']['岗位']}")
    弱项 = sorted(result["画像"]["技能掌握度"], key=result["画像"]["技能掌握度"].get)[:2]
    print(f"  弱项技能: {', '.join(弱项)}")

    print(f"知识: {len(result['知识列表'])} 条")

    print(f"培训: [{result['培训内容']['类型']}] {result['培训内容']['标题']}")

    status = "✅ 通过" if result["审核通过"] else "❌ 未通过"
    print(f"审核: {status} | 幻觉分数={result['幻觉分数']} | 重试={result['重试次数']}")

    print(f"评估: 综合分={result['评估结果']['综合分']} "
          f"(事实性={result['评估结果']['事实性']}, "
          f"专业性={result['评估结果']['专业性']}, "
          f"可读性={result['评估结果']['可读性']}, "
          f"匹配度={result['评估结果']['匹配度']})")


if __name__ == "__main__":
    test_all_scenarios()
