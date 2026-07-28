# 智策育训

制造业个性化培训内容自动生成平台，采用：

`岗位画像 → 可溯源检索 → 受约束生成 → 断言审核 → 内容诊断 → 动态决策`

产品架构是 1 Orchestrator + 4 Agent；P1–P4 是成员编号，不是四个固定技术领域。

## 当前状态

- 已有 39 条带来源定位的“已验证”制造业知识。
- 已实现三个岗位画像、严格拒答、三类培训资源、L1/L2 审核、重生成闭环和 Streamlit 可视化。
- 已有 52 条 QA 机器初标案例，但尚未完成双人复核，不能作为正式指标。
- DeepSeek、Qwen、GLM 已有适配代码；真实生成和异构投票仍取决于本机 Key 与实际 smoke test。

当前开工入口：`docs/当前状态与下一步执行方案.md`。

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

# 三个代表场景；任一失败会返回非零退出码
python test_run.py

# Streamlit 界面
streamlit run app.py

# 仅验证评测管线；输出不是正式指标
python knowledge_base/evaluate_benchmark.py --include-draft
```

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

## 文档

- `docs/当前状态与下一步执行方案.md` — 当前任务、两轮冲刺、P1–P4 提示词
- `docs/阶段制分工与互验计划.md` — 宏观阶段、轮换与互验规则
- `docs/分工_P1_编排与集成.md` 至 `docs/分工_P4_审核与评估.md` — 四名成员任务书
- `docs/接口约定.md` — 模块间 JSON 契约和状态定义
- `docs/项目背景.md` — 项目定位、边界和评分维度
- `docs/项目研究方案.md` — 完整研究方案
- `docs/新成员培训_环境工具搭建.md` — Windows 环境、Git、VS Code 和 API 配置

## 可信度边界

- 单份内容的事实性、匹配度等是透明诊断值，不等于正式测试集准确率。
- “幻觉率 <5% / 适配准确率 ≥85% / 覆盖率 ≥90%”只能在人工复核评测集上实测后使用。
- 离线确定性生成不等于真实大模型生成。
- 制造业安全内容必须结合具体设备型号和现场规程，由专业人员复核后用于实际培训。

接口与状态定义见 `docs/接口约定.md`，项目规则见 `AGENTS.md` 与 `CLAUDE.md`。
