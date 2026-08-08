import pytest

from src.zhice_yuxun.agents.profile import build_profile
from src.zhice_yuxun.contracts import ContractError


POSITION = "数控机床操作工"
LEGACY_FIELDS = {
    "岗位",
    "岗位描述",
    "典型企业",
    "技能掌握度",
    "目标技能",
    "推荐难度",
    "知识领域覆盖",
    "画像依据",
    "学习路径",
}


@pytest.mark.parametrize("scene", [None, {}])
def test_missing_or_empty_learning_scene_keeps_legacy_output(scene):
    profile = build_profile(POSITION, 学习场景=scene)

    assert set(profile) == LEGACY_FIELDS
    assert "学习场景" not in profile


def test_valid_learning_scene_adds_context_without_overriding_difficulty():
    scene = {
        "经验水平": "首次上岗",
        "设备或工具": "未知型号数控机床",
        "本次任务": "开机前安全检查",
        "可用时长分钟": 20,
    }
    legacy_difficulty = build_profile(POSITION)["推荐难度"]

    profile = build_profile(POSITION, 学习场景=scene)

    assert profile["学习场景"] is scene
    assert profile["本次学习目标"] == [
        "能按检查表独立完成开机前安全检查"
    ]
    assert "设备型号未知，不得生成型号专属参数" in profile["内容约束"]
    assert any("分步示范" in item for item in profile["内容约束"])
    assert profile["推荐难度"] == legacy_difficulty


def test_invalid_learning_scene_raises_contract_error():
    with pytest.raises(ContractError, match="经验水平"):
        build_profile(POSITION, 学习场景={"经验水平": "专家"})
