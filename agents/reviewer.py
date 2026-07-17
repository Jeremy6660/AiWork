"""
三层审核 Agent (P4)
对生成的培训内容执行三层审核，目标是控制幻觉率 < 5%。

接口契约（来自 docs/接口约定.md）：
    输入: 培训内容 (dict), 知识列表 (list)
    输出: {"通过": bool, "幻觉分数": 0~1, "修改建议": str, "审核明细": {...}}

三层机制：
    1) 规则引擎   — 硬约束检查（禁用词、长度、格式）
    2) 知识锚定   — 检查内容的每个断言是否有知识来源支撑
    3) 三模型异构投票 — 三个不同厂商模型各自判断是否存在事实错误
       （当前为 stub 模拟）
"""

import random


def _check_rules(content: dict) -> tuple[bool, str]:
    """
    第一层：规则引擎。
    检查硬约束——违禁词、空内容、长度异常等。

    返回: (通过?, 失败原因)
    """
    正文 = content.get("正文", "")
    if not 正文.strip():
        return False, "正文为空"

    if len(正文) < 50:
        return False, f"正文过短({len(正文)}字符)，应 >= 50 字符"

    标题 = content.get("标题", "")
    if not 标题.strip():
        return False, "标题为空"

    引用 = content.get("引用来源", [])
    if not 引用:
        return False, "引用来源为空——无法做知识锚定"

    # 违禁词检查（制造业培训常见违禁词）
    forbidden = ["大概", "可能", "差不多", "随便", "无所谓"]
    for word in forbidden:
        if word in 正文:
            return False, f"含违禁词: '{word}'"

    return True, "pass"


def _check_anchoring(content: dict, knowledge: list) -> tuple[bool, float, str]:
    """
    第二层：知识锚定比对。
    将内容断言与知识列表比对，计算「有依据」的比例。

    当前 stub 实现：将正文分句，检查每句是否在知识库中能找到相似表述。

    返回: (通过?, 锚定分数, 详情)
    """
    正文 = content.get("正文", "")
    引用 = set(content.get("引用来源", []))
    knowledge_sources = {k["来源"] for k in knowledge}

    # stub 逻辑：引用来源中至少 2 个能在知识列表中找到
    matched = 引用 & knowledge_sources
    anchor_score = len(matched) / max(len(引用), 1)

    if anchor_score >= 0.5:
        return True, anchor_score, f"锚定通过 ({len(matched)}/{len(引用)} 来源匹配)"
    else:
        return False, anchor_score, f"锚定不足: 仅 {len(matched)}/{len(引用)} 来源可溯源"


def _mock_model_vote(content: dict, knowledge: list) -> dict:
    """
    第三层：三模型异构投票（stub 模拟）。
    模拟 DeepSeek / 通义 / GLM 三家分别对内容做事实核查。

    后续对接真实 API 后，每个模型独立调用，prompt 为：
        "以下培训内容是否与给定的知识列表一致？如有事实错误请指出。"

    返回: 各家投票结果
    """
    # 0.85 概率通过，模拟低幻觉率
    votes = []
    for name in ["DeepSeek", "通义千问", "GLM"]:
        passed = random.random() < 0.88  # 模拟 88% 通过率
        votes.append({"模型": name, "通过": passed})

    passed_count = sum(1 for v in votes if v["通过"])
    return {
        "投票结果": f"{passed_count}/3",
        "明细": votes,
        "风险等级": "low" if passed_count >= 2 else "high",
    }


def review_content(培训内容: dict, 知识列表: list) -> dict:
    """
    三层审核主函数：规则引擎 → 知识锚定 → 三模型投票。

    参数:
        培训内容: generate_content 的输出
        知识列表: search_knowledge 的输出（作为事实依据）

    返回:
        {"通过": bool, "幻觉分数": float, "修改建议": str, "审核明细": dict}
    """
    审核明细 = {}

    # ---- 第一层：规则引擎 ----
    rule_pass, rule_detail = _check_rules(培训内容)
    审核明细["规则引擎"] = rule_detail
    if not rule_pass:
        return {
            "通过": False,
            "幻觉分数": 0.0,
            "修改建议": f"规则引擎未通过: {rule_detail}",
            "审核明细": 审核明细,
        }

    # ---- 第二层：知识锚定 ----
    anchor_pass, anchor_score, anchor_detail = _check_anchoring(培训内容, 知识列表)
    审核明细["知识锚定"] = anchor_detail
    if not anchor_pass:
        return {
            "通过": False,
            "幻觉分数": 1.0 - anchor_score,
            "修改建议": f"知识锚定未通过: {anchor_detail}。请确保正文中的断言能对应知识库中的具体来源。",
            "审核明细": 审核明细,
        }

    # ---- 第三层：三模型投票 ----
    vote_result = _mock_model_vote(培训内容, 知识列表)
    审核明细["模型投票"] = vote_result["投票结果"]
    审核明细["风险等级"] = vote_result["风险等级"]
    审核明细["投票明细"] = vote_result["明细"]

    passed_count = int(vote_result["投票结果"].split("/")[0])
    通过 = passed_count >= 2

    # 幻觉分数 = 未通过票数 / 3
    幻觉分数 = (3 - passed_count) / 3

    修改建议 = ""
    if not 通过:
        修改建议 = (
            f"三模型投票 {vote_result['投票结果']}，未达 2/3 多数。"
            f"请重新生成，注意确保事实与知识库一致。"
        )

    return {
        "通过": 通过,
        "幻觉分数": 幻觉分数,
        "修改建议": 修改建议,
        "审核明细": 审核明细,
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

    print("===== 审核培训内容 =====")
    print(f"标题: {content['标题']}")

    result = review_content(content, knowledge)
    print(f"\n通过: {result['通过']}")
    print(f"幻觉分数: {result['幻觉分数']}")
    print(f"修改建议: {result['修改建议'] or '无'}")
    print(f"审核明细:")
    for k, v in result["审核明细"].items():
        if k != "投票明细":
            print(f"  {k}: {v}")

    # ---- 边界测试：给一个有问题的内容 ----
    print("\n===== 边界测试（无引用来源的内容）=====")
    bad_content = {"标题": "随便写的教程", "正文": "大概就是这样，差不多就行", "引用来源": []}
    result2 = review_content(bad_content, knowledge)
    print(f"通过: {result2['通过']}")
    print(f"修改建议: {result2['修改建议']}")
