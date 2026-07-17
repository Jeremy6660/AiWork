"""
智策育训 · Streamlit 主界面 (P1)
制造业个性化培训内容自动生成平台

使用方法:
    streamlit run app.py
"""

import streamlit as st
from orchestrator import run

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="智策育训",
    page_icon="🏭",
    layout="wide",
)

# ============================================================
# 侧边栏：参数输入
# ============================================================
st.sidebar.title("🏭 智策育训")
st.sidebar.caption("制造业个性化培训内容自动生成平台")

岗位 = st.sidebar.selectbox(
    "选择岗位",
    ["数控机床操作工", "CNC编程员", "质检员"],
)

question = st.sidebar.text_input(
    "培训主题（留空则自动匹配）",
    value="",
    placeholder="如：数控机床安全操作",
)

st.sidebar.divider()

st.sidebar.markdown("### 学员答题记录（可选）")
st.sidebar.caption("填写已有的答题记录，用于画像构建")

# 答题记录输入
skills = [
    "安全操作规程",
    "切削参数选择",
    "M代码与编程",
    "工件装夹与找正",
    "量具使用与检测",
    "设备维护保养",
    "缺陷识别与排除",
]

答题记录 = []
for skill in skills:
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        st.caption(skill)
    with col2:
        # 用 radio 代替 checkbox 让布局更紧凑
        status = st.radio(
            f"{skill}_radio",
            ["?", "✅", "❌"],
            key=f"q_{skill}",
            horizontal=True,
            label_visibility="collapsed",
        )
        if status == "✅":
            答题记录.append({"技能": skill, "正确": True})
        elif status == "❌":
            答题记录.append({"技能": skill, "正确": False})

st.sidebar.divider()
生成按钮 = st.sidebar.button("🚀 生成培训内容", type="primary", use_container_width=True)

st.sidebar.caption("当前为骨架测试版本，使用 stub 数据")

# ============================================================
# 主区域
# ============================================================
st.title("智策育训")
st.markdown("**制造业个性化培训内容自动生成平台** — 1 Orchestrator + 4 Agent 架构")

if not 生成按钮:
    st.info("👈 在左侧选择岗位和答题记录，点击「生成培训内容」开始")
    st.stop()

# ============================================================
# 执行全流程
# ============================================================
with st.spinner("🚀 全流程执行中..."):

    # ---- 调 orchestrator ----
    result = run(岗位=岗位, 答题记录=答题记录, question=question)

# ============================================================
# 展示结果 —— 用多个 Tab 分区域
# ============================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 培训内容",
    "👤 学员画像",
    "📚 知识检索",
    "🔎 审核详情",
    "📊 效果评估",
])

# ====== Tab 1: 培训内容 ======
with tab1:
    content = result["培训内容"]
    st.subheader(content["标题"])
    st.caption(f"类型: {content['类型']} | 引用来源: {', '.join(content['引用来源'])}")

    st.divider()
    st.markdown(content["正文"])

# ====== Tab 2: 学员画像 ======
with tab2:
    profile = result["画像"]
    st.subheader(f"岗位: {profile['岗位']}")

    cols = st.columns(len(profile["技能掌握度"]))
    for i, (skill, level) in enumerate(profile["技能掌握度"].items()):
        with cols[i]:
            color = "🟢" if level >= 0.7 else "🟡" if level >= 0.4 else "🔴"
            st.metric(label=skill, value=f"{color} {level:.0%}")

    st.divider()
    st.markdown("### 技能雷达（条形图模拟）")
    for skill, level in profile["技能掌握度"].items():
        st.markdown(f"**{skill}**")
        st.progress(level, text=f"{level:.0%}")

# ====== Tab 3: 知识检索 ======
with tab3:
    st.subheader(f"检索到 {len(result['知识列表'])} 条相关知识")
    for i, k in enumerate(result["知识列表"], 1):
        with st.expander(f"[{i}] {k['内容'][:50]}...", expanded=(i == 1)):
            st.markdown(k["内容"])
            st.caption(f"📖 来源: {k['来源']}")

# ====== Tab 4: 审核详情 ======
with tab4:
    audit = result["审核明细"]
    passed = result["审核通过"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("审核结果", "✅ 通过" if passed else "❌ 未通过")
    with col2:
        st.metric("幻觉分数", f"{result['幻觉分数']:.0%}")
    with col3:
        st.metric("重试次数", result["重试次数"])

    st.divider()

    if audit:
        st.markdown(f"**规则引擎**: {audit.get('规则引擎', 'N/A')}")
        st.markdown(f"**知识锚定**: {audit.get('知识锚定', 'N/A')}")
        st.markdown(f"**模型投票**: {audit.get('模型投票', 'N/A')}")

        if "投票明细" in audit:
            st.divider()
            st.caption("投票明细")
            cols = st.columns(len(audit["投票明细"]))
            for i, v in enumerate(audit["投票明细"]):
                with cols[i]:
                    icon = "✅" if v["通过"] else "❌"
                    st.metric(label=v["模型"], value=icon)

# ====== Tab 5: 效果评估 ======
with tab5:
    eval_r = result["评估结果"]

    cols = st.columns(5)
    metrics = [
        ("事实性", eval_r["事实性"]),
        ("专业性", eval_r["专业性"]),
        ("可读性", eval_r["可读性"]),
        ("匹配度", eval_r["匹配度"]),
        ("综合分", eval_r["综合分"]),
    ]
    for i, (label, val) in enumerate(metrics):
        with cols[i]:
            emoji = "🟢" if val >= 0.8 else "🟡" if val >= 0.6 else "🔴"
            st.metric(label=label, value=f"{emoji} {val:.0%}")

    st.divider()
    st.markdown(f"**优化建议**: {eval_r['优化建议']}")

# ============================================================
# 底部：协同日志
# ============================================================
st.divider()
with st.expander("🔧 协同日志（orchestrator 编排记录）", expanded=False):
    for line in result["协同日志"]:
        st.code(line, language=None)
