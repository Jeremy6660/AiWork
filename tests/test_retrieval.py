import pytest

from src.zhice_yuxun.agents.retrieval import search_knowledge


@pytest.mark.parametrize(
    ("question", "prefix"),
    [
        ("数控机床安全操作", "CNC-SAFE"),
        ("M代码编程", "CNC-M"),
        ("加工缺陷分析与排除", "CNC-FAULT"),
        ("量具使用与质量检测", "QC-MEASURE"),
    ],
)
def test_chinese_retrieval_returns_traceable_relevant_items(question, prefix):
    results = search_knowledge(question)
    assert results
    assert results[0]["知识ID"].startswith(prefix)
    assert all(item["来源定位"].startswith("https://") for item in results)
    assert all(item["验证状态"] == "已验证" for item in results)


def test_unknown_topic_returns_empty_instead_of_fallback():
    assert search_knowledge("莎士比亚哈姆雷特戏剧鉴赏") == []


def test_cross_domain_generic_operation_terms_do_not_match_manufacturing_safety():
    assert search_knowledge("核电站操作规程") == []


def test_unverified_experimental_topics_do_not_pollute_stable_retrieval():
    assert search_knowledge("ONNX模型部署") == []
    assert search_knowledge("焊接安全与劳动防护") == []


@pytest.mark.parametrize("value", ["", "   ", None, 3])
def test_invalid_question_is_rejected(value):
    with pytest.raises(ValueError):
        search_knowledge(value)

