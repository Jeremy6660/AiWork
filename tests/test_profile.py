import pytest

from src.zhice_yuxun.agents.profile import (
    apply_feedback,
    build_profile,
    get_stable_positions,
)


def test_only_evidence_backed_positions_are_stable():
    assert get_stable_positions() == ["数控机床操作工", "CNC编程员", "质检员"]


def test_quality_inspector_profile_has_no_operator_mcode_fallback():
    profile = build_profile("质检员")
    assert "通用量具操作与校准" in profile["技能掌握度"]
    assert "G代码与M代码编程" not in profile["技能掌握度"]


def test_repeated_answers_update_mastery_continuously():
    base = build_profile("CNC编程员")["技能掌握度"]["G代码与M代码编程"]
    correct = build_profile(
        "CNC编程员",
        [
            {"技能": "G代码与M代码编程", "正确": True},
            {"技能": "G代码与M代码编程", "正确": True},
        ],
    )["技能掌握度"]["G代码与M代码编程"]
    wrong = build_profile(
        "CNC编程员",
        [{"技能": "G代码与M代码编程", "正确": False}],
    )["技能掌握度"]["G代码与M代码编程"]
    assert correct > base > wrong


def test_invalid_answer_record_is_rejected():
    with pytest.raises(ValueError, match="布尔值"):
        build_profile("CNC编程员", [{"技能": "G代码与M代码编程", "正确": "是"}])


def test_feedback_changes_recommended_difficulty():
    profile = build_profile("质检员")
    assert apply_feedback(profile, "降维解释")["推荐难度"] == "入门"
    assert apply_feedback(profile, "进阶挑战")["推荐难度"] == "进阶"

