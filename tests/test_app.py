from pathlib import Path

from streamlit.testing.v1 import AppTest

import orchestrator


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _button(app: AppTest, label: str):
    matches = [button for button in app.button if button.label == label]
    assert len(matches) == 1
    return matches[0]


def test_streamlit_app_starts_without_exception():
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()

    assert not app.exception
    assert app.title[0].value == "智策育训"
    assert "请在左侧选择岗位" in app.info[0].value


def test_failure_state_is_rendered_without_content():
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.text_input[0].input("量子计算")
    _button(app, "🚀 生成培训内容").click()
    app.run()

    assert not app.exception
    assert len(app.error) == 1
    assert "知识库未覆盖该主题" in app.error[0].value
    assert any("没有生成内容" in item.value for item in app.info)


def test_manual_review_state_is_rendered_as_warning():
    result = orchestrator.run("数控机床操作工", question="数控机床安全操作")
    result["流程状态"] = "需人工复核"
    result["审核通过"] = False
    result["失败原因"] = "自动审核未形成充分共识"

    app = AppTest.from_file(APP_PATH, default_timeout=10)
    app.session_state["result"] = result
    app.session_state["last_request"] = {
        "position": "数控机床操作工",
        "records": [],
        "topic": "数控机床安全操作",
    }
    app.run()

    assert not app.exception
    assert len(app.warning) == 1
    assert "必须由专业人员复核" in app.warning[0].value
    assert len(app.success) == 0


def test_session_state_prevents_unintended_regeneration(monkeypatch):
    original_run = orchestrator.run
    calls = []

    def counted_run(*args, **kwargs):
        calls.append(kwargs.get("反馈模式", ""))
        return original_run(*args, **kwargs)

    monkeypatch.setattr(orchestrator, "run", counted_run)
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.text_input[0].input("数控机床安全操作")
    _button(app, "🚀 生成培训内容").click()
    app.run()

    assert calls == [""]
    assert not app.exception
    assert len(app.get("graphviz_chart")) == 1

    app.run()
    assert calls == [""]

    _button(app, "看不懂，降维解释").click()
    app.run()
    assert calls == ["", "降维解释"]
    assert not app.exception
