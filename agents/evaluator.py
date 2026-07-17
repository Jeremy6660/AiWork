"""
效果评估模块 (P4)
对最终培训内容做多维度量化评估，输出综合分和优化建议。

接口契约（来自 docs/接口约定.md）：
    输入: 培训内容 (dict), 知识列表 (list), 画像 (dict)
    输出: {"事实性": 0~1, "专业性": 0~1, "可读性": 0~1, "匹配度": 0~1,
           "综合分": 0~1, "优化建议": str}
"""


def evaluate(培训内容: dict, 知识列表: list, 画像: dict) -> dict:
    """
    对培训内容做多维度评估。

    当前为 stub 版本，用启发式规则打分。
    后续替换为 LLM 评估 + 仿真学员测试。

    参数:
        培训内容: generate_content 的输出
        知识列表: search_knowledge 的输出
        画像: build_profile 的输出

    返回:
        {"事实性": float, "专业性": float, "可读性": float,
         "匹配度": float, "综合分": float, "优化建议": str}
    """
    正文 = 培训内容.get("正文", "")
    引用 = 培训内容.get("引用来源", [])
    skills = 画像.get("技能掌握度", {})

    # ---- 事实性：基于知识锚定（引用来源越多越可靠） ----
    事实性 = min(1.0, len(引用) * 0.30)
    事实性 = round(事实性, 2)

    # ---- 专业性：正文含专业术语的密度 ----
    专业术语 = [
        "切削", "主轴", "进给", "转速", "工件", "夹具", "M代码",
        "G代码", "公差", "粗糙度", "淬火", "回火", "数控", "CNC",
        "对刀", "补偿", "走刀", "余量", "精度", "导轨",
    ]
    term_count = sum(1 for t in 专业术语 if t in 正文)
    专业性 = min(1.0, 0.4 + term_count * 0.04)
    专业性 = round(专业性, 2)

    # ---- 可读性：基于 Markdown 结构 & 长度适中 ----
    可读性 = 0.5
    if "##" in 正文:      # 有二级标题
        可读性 += 0.10
    if "###" in 正文:     # 有三级标题
        可读性 += 0.05
    if "|" in 正文:       # 有表格
        可读性 += 0.10
    if "```" in 正文:     # 有代码块
        可读性 += 0.05
    if "- " in 正文:      # 有列表
        可读性 += 0.10
    if 300 < len(正文) < 3000:  # 长度适中
        可读性 += 0.10
    可读性 = round(min(1.0, 可读性), 2)

    # ---- 匹配度：内容是否覆盖弱项技能 ----
    weak_skills = sorted(skills, key=skills.get)[:2]  # 最弱两项
    match_count = sum(1 for sk in weak_skills if any(
        kw in 正文 for kw in [sk, sk.replace("与", ""), sk.replace("与", "")]
    ))
    # 简化：根据弱项技能的匹配数打分
    if match_count >= 2:
        匹配度 = 0.90
    elif match_count >= 1:
        匹配度 = 0.70
    else:
        匹配度 = 0.50
    匹配度 = round(匹配度, 2)

    # ---- 综合分 = 加权平均 ----
    综合分 = round(事实性 * 0.25 + 专业性 * 0.30 + 可读性 * 0.20 + 匹配度 * 0.25, 2)

    # ---- 优化建议 ----
    建议 = []
    if 事实性 < 0.7:
        建议.append("引用来源偏少，建议补充更多知识库来源支撑内容")
    if 专业性 < 0.7:
        建议.append("专业术语密度偏低，建议补充领域概念和规范术语")
    if 可读性 < 0.7:
        建议.append("可读性有提升空间，建议增加标题层级、表格或列表")
    if 匹配度 < 0.7:
        建议.append("内容与学习者弱项技能匹配不足，建议调整内容方向")
    if not 建议:
        建议.append("各项指标良好，无需优化")

    return {
        "事实性": 事实性,
        "专业性": 专业性,
        "可读性": 可读性,
        "匹配度": 匹配度,
        "综合分": 综合分,
        "优化建议": "；".join(建议),
    }


# ============================================================
# 独立运行示例
# ============================================================
if __name__ == "__main__":
    from retrieval import search_knowledge
    from profile import build_profile
    from generator import generate_content

    profile = build_profile("数控机床操作工")
    knowledge = search_knowledge("数控机床操作")
    content = generate_content(profile, knowledge)

    result = evaluate(content, knowledge, profile)
    print("===== 效果评估 =====")
    print(f"事实性:  {result['事实性']}")
    print(f"专业性:  {result['专业性']}")
    print(f"可读性:  {result['可读性']}")
    print(f"匹配度:  {result['匹配度']}")
    print(f"综合分:  {result['综合分']}")
    print(f"优化建议: {result['优化建议']}")
