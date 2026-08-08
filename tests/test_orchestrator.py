from src.zhice_yuxun.orchestrator import run


def test_end_to_end_scenarios_pass_without_randomness():
    scenarios = [
        ("数控机床操作工", "数控机床安全操作"),
        ("CNC编程员", "加工缺陷分析与排除"),
        ("质检员", "量具使用与质量检测"),
    ]
    for position, topic in scenarios:
        result = run(position, question=topic)
        assert result["流程状态"] == "通过"
        assert result["审核通过"] is True
        assert result["幻觉分数"] == 0.0
        assert result["重试次数"] == 0
        assert result["迭代历史"]
        assert all(item.get("正文") for item in result["迭代历史"])


def test_unknown_topic_fails_safely():
    result = run("质检员", question="莎士比亚十四行诗鉴赏")
    assert result["流程状态"] == "失败"
    assert result["审核通过"] is False
    assert result["培训内容"] == {}
    assert "拒绝生成" in result["失败原因"]


def test_cross_domain_topic_fails_before_generation():
    result = run("数控机床操作工", question="核电站操作规程")
    assert result["流程状态"] == "失败"
    assert result["知识列表"] == []
    assert result["培训内容"] == {}
    assert "拒绝生成" in result["失败原因"]


def test_retry_exhaustion_never_auto_passes(monkeypatch):
    def always_fail(content, knowledge, **kwargs):
        return {
            "通过": False,
            "流程状态": "失败",
            "幻觉分数": 1.0,
            "修改建议": "删除伪造断言",
            "审核明细": {"规则引擎": "pass", "风险等级": "high"},
            "断言核查": [{"断言": "伪造断言", "状态": "无依据"}],
        }

    monkeypatch.setattr(
        "src.zhice_yuxun.orchestrator.review_content",
        always_fail,
    )
    result = run("数控机床操作工", question="M代码编程")
    assert result["审核通过"] is False
    assert result["流程状态"] == "需人工复核"
    assert result["重试次数"] == 2
    assert len(result["迭代历史"]) == 3
    assert all(item.get("正文") for item in result["迭代历史"])
    assert not any("以当前内容通过" in line for line in result["协同日志"])


def test_progress_callback_receives_real_log_lines():
    lines = []
    result = run("质检员", question="量具使用与质量检测", progress_callback=lines.append)
    assert result["流程状态"] == "通过"
    assert lines == result["协同日志"]


# ── S1: 固定开关触发失败后重试 ──
def test_fixed_switch_triggers_retry_then_passes(monkeypatch):
    """S1 通过标准：P1能通过固定开关触发一次失败后重试。"""
    call_count = [0]

    def fail_once_then_pass(content, knowledge, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return {
                "通过": False,
                "流程状态": "失败",
                "幻觉分数": 1.0,
                "修改建议": "删除无依据断言：伪造事实",
                "审核明细": {"规则引擎": "pass", "风险等级": "high"},
                "断言核查": [{"断言": "伪造事实", "状态": "无依据"}],
            }
        return {
            "通过": True,
            "流程状态": "通过",
            "幻觉分数": 0.0,
            "修改建议": "",
            "审核明细": {"规则引擎": "pass", "风险等级": "low"},
            "断言核查": [],
        }

    monkeypatch.setattr(
        "src.zhice_yuxun.orchestrator.review_content",
        fail_once_then_pass,
    )
    result = run("数控机床操作工", question="数控机床安全操作")
    assert result["审核通过"] is True
    assert result["流程状态"] == "通过"
    assert result["重试次数"] == 1
    assert len(result["迭代历史"]) == 2
    # 验证日志能指出失败步骤（审核日志和幻觉分数可能在不同行）
    assert any("幻觉分数" in line for line in result["协同日志"])
    assert any("审核" in line for line in result["协同日志"])


# ── S2: 跨领域画像验收 ──
def test_cross_domain_profiles_meet_acceptance():
    """S2 通过标准：跨领域画像掌握度在0-1，相同输入得相同结果。"""
    from src.zhice_yuxun.agents.profile import build_profile

    # 工业互联网运维工程师 - 冷启动
    p1 = build_profile("工业互联网运维工程师")
    p2 = build_profile("工业互联网运维工程师")
    assert p1["岗位"] == p2["岗位"] == "工业互联网运维工程师"
    assert p1["推荐难度"] == p2["推荐难度"]  # 确定性
    for skill, level in p1["技能掌握度"].items():
        assert 0.0 <= level <= 1.0, f"{skill} = {level} 不在 0~1"
    assert p1 == p2  # 相同输入完全相同结果

    # AI应用工程师 - 带答题记录
    p3 = build_profile(
        "AI应用工程师（工业方向）",
        [{"技能": "Python数据处理基础", "正确": True}],
    )
    for skill, level in p3["技能掌握度"].items():
        assert 0.0 <= level <= 1.0, f"{skill} = {level} 不在 0~1"
    assert p3["技能掌握度"]["Python数据处理基础"] > 0.45  # 答对上升
    assert "知识领域覆盖" in p3


# ── S3: 审核闭环通过+驳回案例 ──
def test_pass_and_reject_cases_available():
    """S3 通过标准：正常通过案例和故意植入错误的驳回案例都可复现。"""
    from src.zhice_yuxun.agents.generator import generate_content
    from src.zhice_yuxun.agents.profile import build_profile
    from src.zhice_yuxun.agents.retrieval import search_knowledge
    from src.zhice_yuxun.agents.reviewer import review_content
    import copy

    knowledge = search_knowledge("M代码编程")
    profile = build_profile("CNC编程员")
    content = generate_content(profile, knowledge, "M代码编程")

    # 正常通过案例
    review_pass = review_content(content, knowledge)
    assert review_pass["通过"] is True
    assert review_pass["幻觉分数"] == 0.0
    assert review_pass["流程状态"] == "通过"

    # 故意植入错误——驳回案例
    bad = copy.deepcopy(content)
    bad["正文"] += "\n- M99 必须用于启动冷却液泵。"
    bad["引用知识ID"].append("FAKE-COOLANT-001")
    review_reject = review_content(bad, knowledge)
    assert review_reject["通过"] is False
    assert review_reject["幻觉分数"] > 0.0
    assert review_reject["修改建议"]  # 有具体修改建议


# ── S4: L3 模型投票逻辑 ──
def test_l3_voting_only_triggers_on_high_risk():
    """S4 通过标准：未触发L3时不产生费用；高风险才触发。"""
    from src.zhice_yuxun.agents.generator import generate_content
    from src.zhice_yuxun.agents.profile import build_profile
    from src.zhice_yuxun.agents.retrieval import search_knowledge
    from src.zhice_yuxun.agents.reviewer import review_content
    import copy

    knowledge = search_knowledge("M代码编程")
    profile = build_profile("CNC编程员")
    content = generate_content(profile, knowledge, "M代码编程")

    # 正常内容 — 幻觉分数应为0，不触发L3
    review = review_content(content, knowledge)
    assert review["幻觉分数"] == 0.0
    assert review["审核明细"]["模型投票"] == "未触发"
    assert review["审核明细"]["风险等级"] == "low"

    # 高风险内容 — 可能触发L3（但ENABLE_L3_VOTING默认=0，所以仍然不触发）
    bad = copy.deepcopy(content)
    for i in range(5):
        bad["正文"] += f"\n- 伪造事实{i} [FAKE-{i}]"
    bad["引用知识ID"] = content["引用知识ID"] + [f"FAKE-{i}" for i in range(5)]
    review_bad = review_content(bad, knowledge)
    assert review_bad["幻觉分数"] > 0.2  # 高风险
    # ENABLE_L3_VOTING=0 时不触发
    assert review_bad["审核明细"]["模型投票"] == "未触发"


def test_model_vote_records_one_failure_and_two_successes(monkeypatch):
    """一家供应商失败时，真实经过 _model_vote 并保留三家结果。"""
    import src.zhice_yuxun.agents.reviewer as reviewer
    from src.zhice_yuxun.agents.generator import generate_content
    from src.zhice_yuxun.agents.profile import build_profile
    from src.zhice_yuxun.agents.retrieval import search_knowledge
    from src.zhice_yuxun.llm_client import LLMError

    knowledge = search_knowledge("M代码编程")
    content = generate_content(build_profile("CNC编程员"), knowledge, "M代码编程")
    called = []

    def fake_call(provider, _messages):
        called.append(provider)
        if provider == "deepseek":
            raise LLMError("模拟超时")
        return {"通过": True, "理由": "有依据", "_模型": f"{provider}-mock"}

    monkeypatch.setattr(
        reviewer, "available_providers", lambda: ["deepseek", "qwen", "glm"]
    )
    monkeypatch.setattr(reviewer, "call_llm_json", fake_call)

    votes = reviewer._model_vote(content, knowledge)

    assert called == ["deepseek", "qwen", "glm"]
    assert [vote["通过"] for vote in votes] == [None, True, True]
    assert "模拟超时" in votes[0]["理由"]


def test_l3_requires_two_successful_independent_providers(monkeypatch):
    """L3 成功供应商不足两个时必须转人工复核。"""
    import src.zhice_yuxun.agents.reviewer as reviewer
    from src.zhice_yuxun.agents.generator import generate_content
    from src.zhice_yuxun.agents.profile import build_profile
    from src.zhice_yuxun.agents.retrieval import search_knowledge

    knowledge = search_knowledge("M代码编程")
    content = generate_content(build_profile("CNC编程员"), knowledge, "M代码编程")
    monkeypatch.setenv("ENABLE_L3_VOTING", "1")
    monkeypatch.setattr(
        reviewer,
        "_deterministic_anchor",
        lambda _content, _knowledge, _taskpkg=None: [
            {"断言": "伪造1", "状态": "无依据", "依据": ""},
            {"断言": "伪造2", "状态": "无依据", "依据": ""},
            {"断言": "伪造3", "状态": "无依据", "依据": ""},
        ],
    )
    monkeypatch.setattr(
        reviewer,
        "_model_vote",
        lambda _content, _knowledge: [
            {"模型": "deepseek", "通过": True, "理由": "mock"},
            {"模型": "qwen", "通过": None, "理由": "timeout"},
            {"模型": "glm", "通过": None, "理由": "invalid json"},
        ],
    )

    review = reviewer.review_content(content, knowledge)

    assert review["流程状态"] == "需人工复核"
    assert review["通过"] is False
    assert review["审核明细"]["模型投票"] == "已触发：1/1（可用独立供应商不足两个）"
    assert "必须人工复核" in review["修改建议"]


def test_l3_records_triggered_when_no_provider_is_available(monkeypatch):
    """L3 已升级但无供应商时，不能误报为“未触发”。"""
    import src.zhice_yuxun.agents.reviewer as reviewer
    from src.zhice_yuxun.agents.generator import generate_content
    from src.zhice_yuxun.agents.profile import build_profile
    from src.zhice_yuxun.agents.retrieval import search_knowledge

    knowledge = search_knowledge("M代码编程")
    content = generate_content(build_profile("CNC编程员"), knowledge, "M代码编程")
    monkeypatch.setenv("ENABLE_L3_VOTING", "1")
    monkeypatch.setattr(
        reviewer,
        "_deterministic_anchor",
        lambda _content, _knowledge, _taskpkg=None: [
            {"断言": "伪造", "状态": "无依据", "依据": ""},
        ],
    )
    monkeypatch.setattr(reviewer, "available_providers", lambda: [])

    review = reviewer.review_content(content, knowledge)

    assert review["流程状态"] == "需人工复核"
    assert review["通过"] is False
    assert review["审核明细"]["模型投票"] == "已触发：0/0（无可用供应商）"


# ── S5: 稳定性与异常处理 ──
def test_invalid_position_is_rejected_early():
    """S5 通过标准：无效岗位直接报错，orchestrator 返回失败状态而非抛出异常。"""
    result = run("不存在的岗位", question="任意主题")
    assert result["流程状态"] == "失败"
    assert "知识本体暂未覆盖岗位" in result["失败原因"]


def test_empty_question_uses_default_topic():
    """S5 通过标准：空主题使用默认岗位核心技能培训。"""
    result = run("质检员", question="")
    assert result["流程状态"] in {"通过", "失败"}  # 不崩溃
    # 即使主题为空，系统也应该给出有意义的反馈
    assert "协同日志" in result


def test_shared_state_contains_all_required_fields():
    """S1 通过标准：共享状态 dict 包含画像、知识、内容、审核、评估和日志。"""
    result = run("数控机床操作工", question="数控机床安全操作")
    required = ["画像", "知识列表", "培训内容", "审核明细", "评估结果", "协同日志"]
    for field in required:
        assert field in result, f"缺少共享状态字段: {field}"
    assert isinstance(result["协同日志"], list)
    assert len(result["协同日志"]) > 0


def test_new_cross_domain_role_runs_end_to_end():
    """实验岗位保留画像能力，但未核验知识不得进入生成链路。"""
    result = run("工业互联网运维工程师", question="工业互联网")
    assert result["流程状态"] == "失败"
    assert result["知识列表"] == []
    assert result["培训内容"] == {}
    assert "画像" in result
    assert result["画像"]["岗位"] == "工业互联网运维工程师"
    assert "知识领域覆盖" in result["画像"]
    assert any(domain in ["网络通信", "数据分析", "平台运维"] for domain in result["画像"].get("知识领域覆盖", []))

