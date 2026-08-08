"""智策育训 Streamlit 界面：展示可信状态、证据与动态反馈闭环。"""

from __future__ import annotations

from typing import Any

from .agents.profile import get_position_skills, get_stable_positions
from .orchestrator import run


def _as_display_list(value: Any) -> list[Any]:
    """把结构化字段统一成展示列表，不修改编排层返回值。"""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _build_microcourse_sections(
    result: dict[str, Any],
) -> list[tuple[str, list[Any]]]:
    """从 ``run`` 结果构造结构化微课展示数据。

    提示始终排在第一位；只有任务包实际生成了结构化内容时才追加微课章节。
    该函数不依赖 Streamlit，便于离线冒烟测试。
    """

    sections: list[tuple[str, list[Any]]] = []
    hint = result.get("任务包提示")
    if isinstance(hint, str) and hint.strip():
        sections.append(("任务包提示", [hint.strip()]))

    taskpkg = result.get("任务包")
    content = result.get("培训内容")
    if not isinstance(taskpkg, dict) or not isinstance(content, dict):
        return sections
    if not any(field in content for field in ("学习目标", "教学步骤", "考核")):
        return sections

    sections.extend(
        [
            ("培训任务", _as_display_list(taskpkg.get("任务名称"))),
            ("学习目标", _as_display_list(content.get("学习目标"))),
            (
                "分步操作与判断标准",
                _as_display_list(content.get("教学步骤")),
            ),
            ("常见错误", _as_display_list(content.get("常见错误"))),
            ("练习任务", _as_display_list(content.get("练习任务"))),
            ("考核与合格标准", _as_display_list(content.get("考核"))),
            ("错后补学", _as_display_list(content.get("补学建议"))),
        ]
    )
    return sections


def _run_with_status(
    position: str,
    records: list[dict[str, Any]],
    topic: str,
    feedback_mode: str = "",
    learning_scene: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import streamlit as st

    status = st.status("多智能体协同执行中…", expanded=True)

    def on_progress(line: str) -> None:
        status.write(line)

    result = run(
        position,
        records,
        topic,
        学习场景=learning_scene,
        反馈模式=feedback_mode,
        progress_callback=on_progress,
    )
    state = "error" if result["流程状态"] == "失败" else "complete"
    status.update(label=f"流程结束：{result['流程状态']}", state=state, expanded=False)
    return result


def _path_dot(path: list[dict[str, Any]]) -> str:
    def quote(value: object) -> str:
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    lines = ["digraph learning_path {", 'rankdir="LR";', 'node [shape="box", style="rounded"];']
    seen: set[str] = set()
    for item in path:
        skill = item["技能"]
        if skill not in seen:
            color = "#b7e4c7" if item["先修已满足"] else "#ffe8a1"
            lines.append(
                f'{quote(skill)} [fillcolor="{color}", style="rounded,filled"];'
            )
            seen.add(skill)
        for prerequisite in item["先修技能"]:
            lines.append(f"{quote(prerequisite)} -> {quote(skill)};")
    lines.append("}")
    return "\n".join(lines)


def _display_value(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value)
    return str(value)


def _render_microcourse_section(st: Any, title: str, items: list[Any]) -> None:
    """用易读卡片渲染单个结构化章节。"""

    st.subheader(title)
    if not items:
        st.caption("本章节暂无内容。")
        return

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            st.write(item)
            continue

        if title == "学习目标":
            st.markdown(f"**目标 {index}：{item.get('行为', '未填写')}**")
            st.write(f"条件：{item.get('条件', '未填写')}")
            st.write(f"达标标准：{item.get('标准', '未填写')}")
        elif title == "分步操作与判断标准":
            step_number = item.get("序号", index)
            st.markdown(f"**步骤 {step_number}：{item.get('操作', '未填写')}**")
            st.write(f"判断标准：{item.get('判定标准', '未填写')}")
            if item.get("异常处理"):
                st.warning(f"异常处理：{item['异常处理']}")
        elif title == "常见错误":
            st.markdown(f"**错误 {index}：{item.get('错误', '未填写')}**")
            st.write(f"后果：{item.get('后果', '未填写')}")
            st.write(f"纠正：{item.get('纠正', '未填写')}")
        elif title == "练习任务":
            st.write(f"任务：{item.get('任务', '未填写')}")
            st.write(f"所需材料：{_display_value(item.get('所需材料', '未填写'))}")
            st.write(f"完成证据：{item.get('完成证据', '未填写')}")
        elif title == "考核与合格标准":
            questions = item.get("题目", [])
            for question_index, question in enumerate(questions, start=1):
                question_text = (
                    question.get("题目", "未填写")
                    if isinstance(question, dict)
                    else question
                )
                st.write(f"{question_index}. {question_text}")
            if item.get("评分规则"):
                st.write(f"评分规则：{_display_value(item['评分规则'])}")
            st.success(f"合格标准：{item.get('合格线', '未填写')}")
        else:
            st.json(item)

        references = item.get("引用知识ID", [])
        if references:
            st.caption("引用知识ID：" + "、".join(references))


def _render_review_cards(st: Any, result: dict[str, Any]) -> None:
    st.markdown("### 双审核结果")
    fact_column, teaching_column = st.columns(2)
    fact_status = result.get("事实审核")
    teaching_status = result.get("教学完整性")

    with fact_column:
        if fact_status == "pass":
            st.success("事实审核：pass")
        elif fact_status == "fail":
            st.error("事实审核：fail")
        else:
            st.info("事实审核：未执行")
    with teaching_column:
        if teaching_status == "pass":
            st.success("教学完整性：pass")
        elif teaching_status == "fail":
            st.error("教学完整性：fail")
        else:
            st.info(f"教学完整性：{teaching_status or '未启用'}")

    problems = result.get("教学问题", [])
    if problems:
        st.markdown("#### 教学问题")
        for problem in problems:
            st.warning(problem)

    metric_specs = [
        ("教学完整率", result.get("教学完整率")),
        ("目标考核对齐率", result.get("目标考核对齐率")),
        ("关键步骤可判定率", result.get("关键步骤可判定率")),
    ]
    metric_columns = st.columns(3)
    for column, (label, value) in zip(metric_columns, metric_specs):
        display = f"{value:.0%}" if isinstance(value, (int, float)) else "—"
        column.metric(label, display)


def main() -> None:
    """渲染 Streamlit 应用；导入本模块做纯函数测试时不会加载 Streamlit。"""

    import streamlit as st

    st.set_page_config(page_title="智策育训", page_icon="🏭", layout="wide")

    st.sidebar.title("🏭 智策育训")
    st.sidebar.caption("制造业个性化培训内容自动生成平台")

    position = st.sidebar.selectbox(
        "选择岗位",
        get_stable_positions(),
    )
    topic = st.sidebar.text_input(
        "培训主题",
        placeholder="如：数控机床安全操作",
    )

    st.sidebar.divider()
    st.sidebar.markdown("### 学员答题记录（可选）")
    records = []
    for skill in get_position_skills(position):
        status_value = st.sidebar.radio(
            skill,
            ["未作答", "答对", "答错"],
            horizontal=True,
            key=f"answer::{position}::{skill}",
        )
        if status_value == "答对":
            records.append({"技能": skill, "正确": True})
        elif status_value == "答错":
            records.append({"技能": skill, "正确": False})

    st.sidebar.divider()
    st.sidebar.markdown("### 本次学习场景")
    experience_level = st.sidebar.selectbox(
        "经验水平",
        ["首次上岗", "有基础", "熟练"],
        index=0,
    )
    equipment = st.sidebar.text_input(
        "设备或工具",
        placeholder="如：Haas VF-2；未知可留空",
    )
    current_task = st.sidebar.text_input(
        "本次真实任务",
        value="开机前安全检查",
    )
    duration_minutes = st.sidebar.number_input(
        "可用培训时长（分钟）",
        min_value=1,
        value=20,
        step=5,
    )
    learning_scene = {
        "经验水平": experience_level,
        "设备或工具": equipment,
        "本次任务": current_task,
        "可用时长分钟": int(duration_minutes),
    }

    generate_clicked = st.sidebar.button(
        "🚀 生成培训内容", type="primary", width="stretch"
    )
    st.sidebar.caption("默认严格模式：未覆盖主题会拒绝生成，不返回无关兜底内容。")

    st.title("智策育训")
    st.markdown("**画像诊断 → 可溯源检索 → 约束生成 → 断言审核 → 动态决策**")

    if generate_clicked:
        st.session_state["last_request"] = {
            "position": position,
            "records": records,
            "topic": topic,
            "learning_scene": learning_scene,
        }
        st.session_state["result"] = _run_with_status(
            position,
            records,
            topic,
            learning_scene=learning_scene,
        )

    if "result" not in st.session_state:
        st.info("请在左侧选择岗位、填写主题并生成内容。")
        st.stop()

    result = st.session_state["result"]
    flow_status = result["流程状态"]
    if flow_status == "通过":
        st.success("✅ 内容已通过当前审核链路，可以作为受知识库约束的培训草稿。")
    elif flow_status == "需人工复核":
        st.warning("⚠️ 内容未获自动发布许可，必须由专业人员复核。")
    else:
        st.error(f"⛔ 流程失败：{result.get('失败原因') or '请查看审核详情'}")

    tabs = st.tabs(
        [
            "📝 培训资源",
            "👤 学情画像",
            "📚 检索证据",
            "🔎 审核与迭代",
            "📊 内容诊断",
            "🧭 协同日志",
        ]
    )

    with tabs[0]:
        content = result["培训内容"]
        sections = _build_microcourse_sections(result)
        warning_sections = [item for item in sections if item[0] == "任务包提示"]
        microcourse_sections = [item for item in sections if item[0] != "任务包提示"]

        for _, warning_items in warning_sections:
            for warning in warning_items:
                st.warning(
                    "草稿任务包未核验；当前输出仅供知识说明或离线演示，"
                    f"不得作为正式微课发布。{warning}"
                )

        if not content:
            st.info("没有生成内容。系统在知识不足时会安全停止。")
        else:
            st.subheader(content["标题"])
            st.caption(
                f"资源类型：{content['类型']}｜生成模式：{content['生成模式']}｜"
                f"引用知识：{len(content['引用知识ID'])} 条"
            )

            if microcourse_sections:
                for section_title, section_items in microcourse_sections:
                    _render_microcourse_section(st, section_title, section_items)
                with st.expander("查看完整 Markdown 正文"):
                    st.markdown(content["正文"])
            else:
                st.markdown(content["正文"])

            with st.expander("来源与审计"):
                st.write("生成模式：", content.get("生成模式", "未记录"))
                st.write("引用知识ID：", content.get("引用知识ID", []))
                st.write("引用来源：", content.get("引用来源", []))
                taskpkg = result.get("任务包")
                if isinstance(taskpkg, dict):
                    st.write("任务包ID：", taskpkg.get("任务包ID", "未记录"))
                    st.write("任务包状态：", taskpkg.get("验证状态", "未记录"))

            _render_review_cards(st, result)
            st.divider()
            st.markdown("#### 学习反馈")
            st.caption("反馈会调整推荐难度并重新执行完整生成—审核链路。")
            left, right = st.columns(2)
            request = st.session_state.get("last_request", {})
            with left:
                if st.button("看不懂，降维解释", width="stretch"):
                    st.session_state["result"] = _run_with_status(
                        request.get("position", position),
                        request.get("records", records),
                        request.get("topic", topic),
                        "降维解释",
                        request.get("learning_scene"),
                    )
                    st.rerun()
            with right:
                if st.button("已经掌握，进阶挑战", width="stretch"):
                    st.session_state["result"] = _run_with_status(
                        request.get("position", position),
                        request.get("records", records),
                        request.get("topic", topic),
                        "进阶挑战",
                        request.get("learning_scene"),
                    )
                    st.rerun()

    with tabs[1]:
        profile = result["画像"]
        if not profile:
            st.info("画像构建未完成。")
        else:
            a, b, c = st.columns(3)
            a.metric("岗位", profile["岗位"])
            b.metric("推荐难度", profile["推荐难度"])
            c.metric("目标技能数", len(profile["目标技能"]))
            st.markdown("#### 知识盲区定位")
            for skill, level in profile["技能掌握度"].items():
                st.progress(level, text=f"{skill}：{level:.0%}")
            st.markdown("#### 资源难度匹配曲线")
            levels = list(profile["技能掌握度"].values())
            st.line_chart(
                {
                    "当前掌握度": levels,
                    "应用型资源阈值": [0.4] * len(levels),
                    "进阶型资源阈值": [0.7] * len(levels),
                }
            )
            st.markdown("#### 可解释学习路径")
            if result["学习路径"]:
                st.graphviz_chart(_path_dot(result["学习路径"]), width="stretch")
                st.dataframe(result["学习路径"], width="stretch", hide_index=True)
            with st.expander("画像依据"):
                for item in profile["画像依据"]:
                    st.write("-", item)

    with tabs[2]:
        if not result["知识列表"]:
            st.info("未检索到达到阈值的已验证知识。")
        for item in result["知识列表"]:
            with st.expander(
                f"{item['知识ID']}｜相关度 {item['检索分数']:.0%}｜{item['来源']}",
                expanded=True,
            ):
                st.write(item["内容"])
                st.caption("主题：" + "、".join(item["主题"]))
                st.markdown(f"[打开原始来源定位]({item['来源定位']})")

    with tabs[3]:
        a, b, c = st.columns(3)
        a.metric("审核状态", flow_status)
        b.metric("幻觉分数", f"{result['幻觉分数']:.2%}")
        c.metric("实际重新生成", result["重试次数"])

        st.divider()
        st.markdown("### 三层审核详情")
        detail = result["审核明细"]
        l1, l2, l3 = st.columns(3)
        with l1:
            st.markdown("**L1 规则引擎**")
            st.code(detail.get("规则引擎", "未执行"))
            problems = detail.get("规则问题", [])
            if problems:
                for problem in problems:
                    st.warning(problem)
            else:
                st.success("通过")
        with l2:
            st.markdown("**L2 知识锚定**")
            st.code(detail.get("知识锚定", "未执行"))
        with l3:
            st.markdown("**L3 模型投票**")
            st.code(detail.get("模型投票", "未触发"))
            risk = detail.get("风险等级", "unknown")
            color = "green" if risk == "low" else "orange" if risk == "medium" else "red"
            st.markdown(f"风险等级：:{color}[{risk}]")

        st.divider()
        st.markdown("### 修改前后对比")
        iterations = result.get("迭代历史", [])
        if len(iterations) >= 2:
            for previous, current in zip(iterations, iterations[1:]):
                with st.expander(
                    f"第 {previous['轮次']} 轮 → 第 {current['轮次']} 轮",
                    expanded=current is iterations[-1],
                ):
                    before, after = st.columns(2)
                    with before:
                        st.caption("修改前正文")
                        st.markdown(previous.get("正文", "未保存正文"))
                        st.warning(f"修改建议：{previous.get('修改建议') or '无'}")
                    with after:
                        st.caption("修改后正文")
                        st.markdown(current.get("正文", "未保存正文"))
                        st.metric("修改后幻觉分数", f"{current['幻觉分数']:.2%}")
                        st.write(f"通过：{'✅' if current['审核通过'] else '❌'}")
        elif iterations:
            current = iterations[0]
            st.success(f"✅ 首次生成即通过审核（幻觉分数：{current['幻觉分数']:.2%}）")
        else:
            st.info("没有迭代记录。")

        st.divider()
        st.markdown("### 逐条断言核查")
        if result.get("断言核查"):
            st.dataframe(result["断言核查"], width="stretch", hide_index=True)
        else:
            st.info("没有可展示的断言核查结果。")

        st.divider()
        st.markdown("### 迭代历史（JSON）")
        if iterations:
            st.dataframe(iterations, width="stretch", hide_index=True)

    with tabs[4]:
        evaluation = result["评估结果"]
        metric_names = ["事实性", "专业性", "可读性", "匹配度", "知识覆盖率", "综合分"]
        columns = st.columns(len(metric_names))
        for column, name in zip(columns, metric_names):
            column.metric(name, f"{evaluation[name]:.0%}")
        st.info("这些是单份内容诊断值，不等同于官方测试集上的总体准确率。")
        st.write("**优化建议：**", evaluation["优化建议"])
        with st.expander("指标计算依据"):
            st.json(evaluation.get("指标依据", {}))

    with tabs[5]:
        for line in result["协同日志"]:
            st.code(line, language=None)


if __name__ == "__main__":
    main()
