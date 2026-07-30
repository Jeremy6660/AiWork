"""智策育训 Streamlit 界面：展示可信状态、证据与动态反馈闭环。"""

from __future__ import annotations

import streamlit as st

from .agents.profile import get_position_skills, get_stable_positions
from .orchestrator import run


st.set_page_config(page_title="智策育训", page_icon="🏭", layout="wide")


def _run_with_status(position, records, topic, feedback_mode=""):
    status = st.status("多智能体协同执行中…", expanded=True)

    def on_progress(line: str) -> None:
        status.write(line)

    result = run(
        position,
        records,
        topic,
        反馈模式=feedback_mode,
        progress_callback=on_progress,
    )
    state = "error" if result["流程状态"] == "失败" else "complete"
    status.update(label=f"流程结束：{result['流程状态']}", state=state, expanded=False)
    return result


def _path_dot(path: list[dict]) -> str:
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
    }
    st.session_state["result"] = _run_with_status(position, records, topic)

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
    if not content:
        st.info("没有生成内容。系统在知识不足时会安全停止。")
    else:
        st.subheader(content["标题"])
        st.caption(
            f"资源类型：{content['类型']}｜生成模式：{content['生成模式']}｜"
            f"引用知识：{len(content['引用知识ID'])} 条"
        )
        st.markdown(content["正文"])
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
                )
                st.rerun()
        with right:
            if st.button("已经掌握，进阶挑战", width="stretch"):
                st.session_state["result"] = _run_with_status(
                    request.get("position", position),
                    request.get("records", records),
                    request.get("topic", topic),
                    "进阶挑战",
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
            for p in problems:
                st.warning(p)
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
