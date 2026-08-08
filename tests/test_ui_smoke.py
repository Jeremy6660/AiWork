"""UI 结构化展示数据的离线冒烟测试，不启动 Streamlit。"""

from src.zhice_yuxun.ui import _build_microcourse_sections


def test_taskpackage_result_builds_structured_microcourse_sections():
    result = {
        "任务包": {
            "任务包ID": "TASK-CNC-SAFE-001",
            "任务名称": "开机前安全检查",
        },
        "任务包提示": "",
        "培训内容": {
            "学习目标": [{"行为": "完成安全检查"}],
            "教学步骤": [{"序号": 1, "操作": "检查急停按钮"}],
            "常见错误": [{"错误": "跳过检查"}],
            "练习任务": {"任务": "完成模拟检查"},
            "考核": {"题目": [], "合格线": "关键项无遗漏"},
            "补学建议": ["重新学习遗漏项"],
        },
    }

    sections = _build_microcourse_sections(result)
    titles = [title for title, _ in sections]

    assert "学习目标" in titles
    assert "分步操作与判断标准" in titles
    assert "考核与合格标准" in titles


def test_taskpackage_hint_is_first_section():
    hint = "当前可提供知识说明，但任务包尚未完成专业核验"
    result = {
        "任务包": {"任务名称": "开机前安全检查"},
        "任务包提示": hint,
        "培训内容": {"正文": "知识说明"},
    }

    sections = _build_microcourse_sections(result)

    assert sections == [("任务包提示", [hint])]


def test_taskpackage_miss_has_no_microcourse_sections():
    result = {
        "任务包": None,
        "任务包提示": "",
        "培训内容": {"正文": "旧链路知识说明"},
    }

    assert _build_microcourse_sections(result) == []
