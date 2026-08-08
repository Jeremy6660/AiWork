import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

from knowledge_base.embedding import normalize_text
from knowledge_base.evaluate_benchmark import run_full_chain_evaluation


ROOT = Path(__file__).resolve().parents[1]
BLIND_SET_PATH = ROOT / "knowledge_base" / "training_blind_test_set.json"
DEV_SET_PATH = ROOT / "knowledge_base" / "qa_test_set.json"
KNOWLEDGE_PATH = ROOT / "data" / "knowledge.json"
HASH_RECORD_PATH = (
    ROOT
    / "artifacts"
    / "zg_profile_comparison_20260808"
    / "blind_test_sha256.txt"
)

EXPECTED_CATEGORIES = {
    "正常表达",
    "同义改写",
    "场景问题",
    "近领域负例",
    "跨领域负例",
}
EXPECTED_OUTCOMES = {"命中任务包", "知识说明", "拒绝"}
FORBIDDEN_ANSWER_KEYS = {"参考答案", "预期知识ID"}


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_blind_set_has_thirty_cases_and_balanced_categories():
    cases = _load_json(BLIND_SET_PATH)

    assert len(cases) == 30
    assert Counter(case["类别"] for case in cases) == {
        category: 6 for category in EXPECTED_CATEGORIES
    }
    assert len({case["案例ID"] for case in cases}) == 30
    assert len({case["问题"] for case in cases}) == 30
    assert {case["期望"] for case in cases} <= EXPECTED_OUTCOMES


def test_at_least_ten_questions_do_not_contain_a_complete_topic_field():
    cases = _load_json(BLIND_SET_PATH)
    knowledge = _load_json(KNOWLEDGE_PATH)
    topics = {
        normalize_text(topic)
        for item in knowledge
        for topic in item.get("主题", [])
        if isinstance(topic, str) and normalize_text(topic)
    }

    topic_free_questions = [
        case["案例ID"]
        for case in cases
        if all(topic not in normalize_text(case["问题"]) for topic in topics)
    ]

    assert len(topic_free_questions) >= 10


def test_no_question_copies_a_knowledge_body():
    cases = _load_json(BLIND_SET_PATH)
    knowledge = _load_json(KNOWLEDGE_PATH)
    bodies = [normalize_text(item["内容"]) for item in knowledge]

    for case in cases:
        question = normalize_text(case["问题"])
        assert all(question not in body for body in bodies), case["案例ID"]
        assert all(body not in question for body in bodies), case["案例ID"]


def test_blind_set_and_full_chain_code_have_no_answer_leakage_fields():
    cases = _load_json(BLIND_SET_PATH)
    assert all(FORBIDDEN_ANSWER_KEYS.isdisjoint(case) for case in cases)

    source = inspect.getsource(run_full_chain_evaluation)
    assert "orchestrator.run(" in source
    assert "qa_test_set.json" not in source
    assert all(key not in source for key in FORBIDDEN_ANSWER_KEYS)


def test_blind_set_sha256_is_frozen():
    current_hash = hashlib.sha256(BLIND_SET_PATH.read_bytes()).hexdigest()
    if not HASH_RECORD_PATH.exists():
        HASH_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
        HASH_RECORD_PATH.write_text(current_hash + "\n", encoding="utf-8")

    assert HASH_RECORD_PATH.exists()
    assert HASH_RECORD_PATH.read_text(encoding="utf-8").strip() == current_hash


def test_development_and_blind_sets_are_separate_files():
    assert DEV_SET_PATH.resolve() != BLIND_SET_PATH.resolve()
    assert DEV_SET_PATH.exists()
    assert BLIND_SET_PATH.exists()
