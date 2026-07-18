import pytest

from agents.profile import apply_feedback, build_profile


def test_quality_inspector_profile_has_no_operator_mcode_fallback():
    profile = build_profile("质检员")
    assert "量具使用与检测" in profile["技能掌握度"]
    assert "M代码与编程" not in profile["技能掌握度"]


def test_repeated_answers_update_mastery_continuously():
    base = build_profile("数控机床操作工")["技能掌握度"]["M代码与编程"]
    correct = build_profile(
        "数控机床操作工",
        [
            {"技能": "M代码与编程", "正确": True},
            {"技能": "M代码与编程", "正确": True},
        ],
    )["技能掌握度"]["M代码与编程"]
    wrong = build_profile(
        "数控机床操作工",
        [{"技能": "M代码与编程", "正确": False}],
    )["技能掌握度"]["M代码与编程"]
    assert correct > base > wrong


def test_invalid_answer_record_is_rejected():
    with pytest.raises(ValueError, match="布尔值"):
        build_profile("数控机床操作工", [{"技能": "M代码与编程", "正确": "是"}])


def test_feedback_changes_recommended_difficulty():
    profile = build_profile("质检员")
    assert apply_feedback(profile, "降维解释")["推荐难度"] == "入门"
    assert apply_feedback(profile, "进阶挑战")["推荐难度"] == "进阶"

