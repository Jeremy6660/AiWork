from orchestrator import run


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


def test_unknown_topic_fails_safely():
    result = run("质检员", question="量子纠缠与超导计算")
    assert result["流程状态"] == "失败"
    assert result["审核通过"] is False
    assert result["培训内容"] == {}
    assert "拒绝生成" in result["失败原因"]


def test_retry_exhaustion_never_auto_passes(monkeypatch):
    def always_fail(content, knowledge):
        return {
            "通过": False,
            "流程状态": "失败",
            "幻觉分数": 1.0,
            "修改建议": "删除伪造断言",
            "审核明细": {"规则引擎": "pass", "风险等级": "high"},
            "断言核查": [{"断言": "伪造断言", "状态": "无依据"}],
        }

    monkeypatch.setattr("orchestrator.review_content", always_fail)
    result = run("数控机床操作工", question="M代码编程")
    assert result["审核通过"] is False
    assert result["流程状态"] == "需人工复核"
    assert result["重试次数"] == 2
    assert len(result["迭代历史"]) == 3
    assert not any("以当前内容通过" in line for line in result["协同日志"])


def test_progress_callback_receives_real_log_lines():
    lines = []
    result = run("质检员", question="量具使用与质量检测", progress_callback=lines.append)
    assert result["流程状态"] == "通过"
    assert lines == result["协同日志"]

