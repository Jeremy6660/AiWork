# 智策育训

制造业个性化培训内容自动生成平台，采用：

`岗位画像 → 可溯源检索 → 受约束生成 → 断言审核 → 内容诊断 → 动态决策`

产品架构是 1 Orchestrator + 4 Agent；P1–P4 是成员编号，不是四个固定技术领域。

## 当前状态

- 已有 39 条带来源定位的“已验证”制造业知识；另有 9 条跨领域草稿处于“待人工核验”，不会进入 ChromaDB 正式索引。
- 主界面稳定支持数控机床操作工、CNC 编程员、质检员；焊接、工业互联网和工业 AI 画像仅保留为实验能力，不计入当前验收规模。
- 已有 52 条 QA 机器初标案例，但尚未完成双人复核，不能作为正式指标。
- 已准备双人复核规范、标准库 CSV 导出器和 12 条空白试标表；真实 A/B 标注、分歧仲裁和 P2 对 P1 流程的独立验收仍待完成。
- P2 的历史提交已由 P3 在独立 Windows venv 复验：建库 39 条、`pytest` 44 项通过、三个演示场景通过。
- 当前代码离线验收为 68 项测试通过；DeepSeek、Qwen、GLM 仅完成零费用 smoke 门禁和故障模拟，真实调用仍需操作者显式确认。
- 跨领域拒答、规范化证据哈希、L3 状态区分和 P4 非覆盖写入已修复并提交；E1 仍未通过，因为 12 条真人双人试标、P2→P1 与 P1→P4 两项独立互验、经授权的真实模型 smoke，以及与修复后提交一致的 P4 新证据包和独立复验仍未完成。

当前开工入口：`docs/当前状态与下一步执行方案.md`；全面验收记录见
`docs/验收记录_E1_全面验收.md`。

## 代码布局

- `src/zhice_yuxun/`：规范运行实现，包含编排、契约、模型客户端、界面和
  `agents/`。
- `knowledge_base/`：建库、评测与人工复核导出工具。
- `scripts/`：手动 smoke、消融和演示脚本。
- `tests/`：离线确定性测试。
- `data/`、`artifacts/`、`docs/`：数据、原始证据和文档。
- 根目录的 `app.py`、`test_run.py` 是稳定启动入口；
  `orchestrator.py`、`contracts.py`、`llm_client.py` 仅保留旧导入兼容，
  新代码应从 `src.zhice_yuxun` 导入。

## 环境要求

- Python 3.12 推荐
- Windows 11 为团队标准环境；macOS 也可运行
- 真实模型为可选项；无 Key 时可以运行离线确定性闭环

## 安装

Windows PowerShell：

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python knowledge_base/build_chromadb.py
```

macOS/Linux：

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python knowledge_base/build_chromadb.py
```

知识文件位于 `data/knowledge.json`。只有 `验证状态=已验证` 的条目会进入 ChromaDB。

## 运行与验收

先激活 `venv`，再执行：

```powershell
# 离线自动化验收
python -m pytest -q

# 全仓 Python 语法编译检查
python -m compileall -q app.py test_run.py orchestrator.py contracts.py llm_client.py src knowledge_base scripts tests

# 三个代表场景；任一失败会返回非零退出码
# 此命令强制离线，即使 .env 中配置了 Key 也不会调用模型
python test_run.py

# 真实模型 smoke 的零费用 dry-run（预计调用次数为 0）
python scripts/smoke_llm.py --provider deepseek --scenario generate

# Streamlit 界面
streamlit run app.py

# 仅验证评测管线；输出不是正式指标
python knowledge_base/evaluate_benchmark.py --include-draft

# 人工复核材料的结构与空白栏校验
python -m pytest -q tests/test_review_export.py
```

12 条试标的固定案例、导出命令和人工填写规则见
`docs/评测集人工复核规范.md`。空白表位于
`data/review/qa_pilot_12_review.csv`；脚本不会代填结论或修改评测集状态。

## 环境变量

完整模板见 `.env.example`。

| 变量 | 用途 | 默认/要求 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek 真实生成与可选 L2/L3 | 可空 |
| `DEEPSEEK_BASE_URL` | DeepSeek OpenAI 兼容地址 | 模板已提供 |
| `DEEPSEEK_MODEL` | DeepSeek 模型 | `deepseek-v4-flash` |
| `QWEN_API_KEY` / `QWEN_MODEL` / `QWEN_BASE_URL` | Qwen 异构审核 | 可空 |
| `GLM_API_KEY` / `GLM_MODEL` / `GLM_BASE_URL` | GLM 异构审核 | 可空 |
| `GENERATION_MODE` | `auto` / `llm` / `offline` | `auto` |
| `ALLOW_OFFLINE_FALLBACK` | LLM 失败时是否允许离线降级 | `1` |
| `ENABLE_LLM_REVIEW` | 是否开启付费 LLM L2 | `0` |
| `ENABLE_L3_VOTING` | 是否开启异构模型投票 | `0` |
| `CHROMA_DB_PATH` | 自定义本地 ChromaDB 路径 | `chroma_db` |

默认不会调用付费审核 API。开启 L3 后，如果成功响应的独立供应商不足两个，系统只能返回“需人工复核”，不得伪造投票。
`scripts/smoke_llm.py` 只有同时提供 `--execute` 并在终端输入 `EXECUTE` 才会发起真实调用。

## 文档

- `docs/当前状态与下一步执行方案.md` — 当前任务、两轮冲刺、P1–P4 提示词
- `docs/阶段制分工与互验计划.md` — 宏观阶段、轮换与互验规则
- `docs/分工_P1_编排与集成.md` 至 `docs/分工_P4_审核与评估.md` — 四名成员任务书
- `docs/接口约定.md` — 模块间 JSON 契约和状态定义
- `docs/项目背景.md` — 项目定位、边界和评分维度
- `docs/项目研究方案.md` — 完整研究方案
- `docs/新成员培训_环境工具搭建.md` — Windows 环境、Git、VS Code 和 API 配置
- `docs/评测集人工复核规范.md` — 双人独立复核、来源核对、分歧仲裁与 12 条试标
- `docs/验收记录_P1_人工复核流程.md` — P1 自检证据与交给 P2 的独立验收清单
- `docs/验收记录_P2_干净环境复现与离线基线.md` — P2 环境复现、离线结果与交给 P3 的验收清单
- `docs/验收记录_P3_整改与零费用门禁.md` — P3 整改、P2 独立复验与真实调用阻塞
- `docs/验收记录_E1_全面验收.md` — E1 全链路、四人证据和退出门槛的实际验收结论
- `docs/验收记录_2026-08-01_日报问题整改.md` — E1 代码侧整改、68 项门禁与仍需真人完成的事项
- `docs/验收记录_目录整理.md` — 源码归包、路径兼容与回归验收记录
- `artifacts/README.md` — 原始命令输出、实验和验收证据包索引

## 可信度边界

- 单份内容的事实性、匹配度等是透明诊断值，不等于正式测试集准确率。
- “幻觉率 <5% / 适配准确率 ≥85% / 覆盖率 ≥90%”只能在人工复核评测集上实测后使用。
- 离线确定性生成不等于真实大模型生成。
- 制造业安全内容必须结合具体设备型号和现场规程，由专业人员复核后用于实际培训。

接口与状态定义见 `docs/接口约定.md`，项目规则见 `AGENTS.md` 与 `CLAUDE.md`。
