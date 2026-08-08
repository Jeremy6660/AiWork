你是智策育训项目的 Python 工程师。任务：完成整改 C4b——Streamlit UI 增加任务包场景输入与结构化微课展示，并更新演示脚本与证据包。

## 背景
整改主线：基于培训任务包生成可执行、可考核、可追溯的岗位微课。已完成：
- 数据层：`data/training_tasks.json` 现为 3 个任务包数组（黄金/CNC编程/质检，均"草稿"状态）
- 契约层：`LearningScene`（经验水平/设备或工具/本次任务/可用时长分钟）、`TrainingContent` 结构化字段
- 链路：`orchestrator.run(岗位, 答题记录=None, question="", *, 学习场景=None, 反馈模式="", progress_callback=None)` 已支持任务包检索→生成→双审核；`ALLOW_DRAFT_TASKPKG=1` 时草稿任务包可生成（标注"非正式（草稿任务包）"），未设置时命中草稿→知识说明+提示
- 评测：`knowledge_base/evaluate_benchmark.py --blind` 完整链路评测已落地

## 涉及文件
1. `src/zhice_yuxun/ui.py`（Streamlit 界面：加场景输入 + 结构化展示）
2. `scripts/p4_demo_script.py`（更新演示脚本，展示黄金微课整改效果）
3. `tests/test_ui_smoke.py`（新建：UI 层最小冒烟，不启动 Streamlit 服务器，只测纯函数）
4. `docs/当前状态与下一步执行方案.md`（更新当前状态——**只追加"整改执行记录"章节，不改既有内容**）

## 需求

### 1. ui.py：输入区新增四项场景字段（方案 9.1）
在岗位/问题/答题记录输入区下方新增（用 st.selectbox/st.text_input/st.number_input，带默认值）：
- 经验水平：首次上岗 / 有基础 / 熟练（默认首次上岗）
- 设备或工具：文本输入（placeholder "如：Haas VF-2；未知可留空"）
- 本次真实任务：文本输入（默认"开机前安全检查"）
- 可用培训时长：数字输入（默认 20，单位分钟）

收集为 `学习场景` dict 传入 `run(..., 学习场景=学习场景)`。

### 2. ui.py：输出区优先展示结构化微课（方案 9.2/9.3）
调用 `run()` 后，返回结果新增了 `任务包`/`任务包提示`/`事实审核`/`教学完整性`/`教学问题`/`教学完整率`/`目标考核对齐率`/`关键步骤可判定率`。界面按以下优先级展示：
1. 若 `任务包提示` 非空：醒目展示提示（st.warning），说明"当前仅提供知识说明/草稿任务包未核验"；
2. 若命中任务包且生成成功：用 st.subheader 展示 培训任务/学习目标/分步操作与判断标准/常见错误/练习任务/考核与合格标准/错后补学（从结构化字段渲染，**不要重复渲染整段 Markdown 正文**，正文用 st.markdown 折叠展示）；
3. 审核结果卡片：事实审核 pass/fail（st.success/st.error）、教学完整性 pass/fail/未启用、教学问题列表、三项比率（st.metric 或 st.caption）；
4. 旧字段（引用知识ID/来源/生成模式）仍展示在"来源与审计"折叠区。

**旧界面元素不得删除**：学习路径图、画像展示、迭代历史等保留。新字段展示区加在旧内容之前或之后均可，但旧调用（不填学习场景）必须完全兼容——`学习场景=None` 时界面行为与现在一致。

### 3. scripts/p4_demo_script.py：更新演示（方案 13.3 演示门槛）
- 保留现有脚本结构（它已经有 7 段演示框架），新增/更新一段"任务包驱动的黄金微课"演示：
  - 设 `ALLOW_DRAFT_TASKPKG=1`（演示草稿态微课，明确标注"非正式（草稿任务包）"）；
  - 用 `run('数控机床操作工', question='开机前安全检查怎么做', 学习场景={'经验水平':'首次上岗','设备或工具':'','本次任务':'开机前安全检查','可用时长分钟':20})`；
  - 打印：流程状态/任务包ID/事实审核/教学完整性/教学完整率/结构化字段列表/标题；
  - 再演示两个对照：
    a. 未设置 ALLOW_DRAFT_TASKPKG 时同一问题 → 应显示"任务包尚未完成专业核验，不能生成完整培训微课"（草稿拒绝）；
    b. 跨领域问题（如"核电站操作规程"）→ 拒绝。
  - 输出保存到 `artifacts/zg_profile_comparison_20260808/c4_demo_微课演示.txt`。
- 脚本保持离线（强制 GENERATION_MODE=offline），不调真实模型。

### 4. tests/test_ui_smoke.py（不启动 Streamlit 服务器）
- 测试 ui.py 中提取的纯函数（如"从 run 结果构造结构化展示区数据"的函数——如果 ui.py 没有可测纯函数，把展示数据组装逻辑抽成纯函数 `_build_microcourse_sections(result) -> list[tuple[str, list]]` 供测试）；
- 覆盖：命中任务包→sections 含 学习目标/分步操作/考核 等章节；任务包提示非空→优先返回提示；未命中→空列表；
- 不 import streamlit（测试环境不要求有 streamlit UI 运行时；若 ui.py 顶部 import streamlit 导致测试无法导入，则把纯函数放到单独模块或测试内联构造）。

### 5. docs/当前状态与下一步执行方案.md：追加"整改执行记录"
只追加章节（不改既有内容），记录：整改方案文档链接、C0-C4 各阶段完成情况、当前证据（124→130 passed、盲测一致率 0.8667、哈希）、遗留事项（4 个盲测失败案例、任务包待人工核验）。

## 验证命令（完成后必须跑）
```bash
cd /Users/xuyunze/Documents/AiWork && source venv/bin/activate && unset PYTHONPATH
python -m pytest tests/test_ui_smoke.py -q
python -m compileall -q src/zhice_yuxun/ui.py scripts/p4_demo_script.py
# 演示脚本离线运行（应产出 c4_demo_微课演示.txt）
python scripts/p4_demo_script.py 2>&1 | tail -15
# 全量回归（当前 130 项必须全过）
python -m pytest -q 2>&1 | tail -3
```

## 禁止事项
- 不改 orchestrator/generator/reviewer/retrieval/contracts、不改 data/*.json、不改测试业务逻辑。
- 不建分支、不 commit、不 push。
- 不启动真实 Streamlit 服务器做测试（离线 pytest 即可）。
- 不调真实模型。
- 旧界面元素与旧调用方式零破坏。
- 脚本输出不得伪造结果（如实打印实际返回值）。
