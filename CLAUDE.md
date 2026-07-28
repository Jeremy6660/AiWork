# CLAUDE.md — 智策育训项目规则手册

> 本文件是给 AI（下次会话的自己）看的规则手册，不是变更日志。
> 项目背景、研究方向请读 `docs/项目背景.md`；模块接口读 `docs/接口约定.md`。

## 项目一句话

智策育训——制造业个性化培训内容自动生成平台，兴智杯参赛项目，架构 = 1 Orchestrator + 4 Agent。

## 团队约束（红线，违反即翻车）

- **4 人小组，vibe coding，编码水平有限。** 一切方案选「最简单能跑通」的路径。
- **禁止训练大模型。** 全程调 API + RAG + 提示词工程。
- **禁止引入重框架**：不用 LangGraph、不用 Neo4j。能用一个 Python 函数解决，就不上框架。
- **只用 Python 一门语言。** 界面用 Streamlit，不写 HTML/CSS/JS。

## 技术栈速查

| 用途 | 选型 |
|---|---|
| 语言 | Python |
| 界面 | Streamlit |
| 向量库 | ChromaDB（本地） |
| 知识图谱 | NetworkX 或纯 JSON |
| 大模型 | DeepSeek / Qwen / GLM（当前适配器；真实异构投票需配置对应 Key） |
| 编排 | 纯 Python 函数调用 |

## 目录结构

```
AiWork/
├── CLAUDE.md              # 本文件（AI 规则手册）
├── README.md             # 人看的：怎么装、怎么跑
├── app.py                # Streamlit 主界面（按阶段轮换负责）
├── orchestrator.py        # 编排：串起 4 个 Agent（按阶段轮换负责）
├── test_run.py            # 命令行全链路测试（不用装 streamlit 也能跑）
├── requirements.txt
├── .env.example           # API key 模板（真实 key 放 .env，禁止提交）
├── agents/                # Agent 模块
│   ├── retrieval.py       # 知识检索 Agent（P2）
│   ├── profile.py         # 画像 Agent（P3）
│   ├── generator.py       # 内容生成 Agent（P3）
│   ├── reviewer.py        # 三层审核 Agent（P4）
│   └── evaluator.py       # 效果评估模块（P4）
├── knowledge_base/       # 知识库（P2 + P3 共建）
│   ├── build_chromadb.py # 向量库建库脚本
│   ├── embedding.py      # 中文 n-gram 哈希向量
│   ├── create_benchmark.py # 生成机器初标评测初稿
│   ├── evaluate_benchmark.py # 可复现评测管线
│   ├── skill_ontology.json # 岗位技能本体（P3）
│   └── qa_test_set.json  # QA 评测集（P2）
├── data/knowledge.json   # 已验证、可溯源的制造业知识切片
├── contracts.py          # 公共 TypedDict 契约与轻量校验
├── llm_client.py         # DeepSeek/Qwen/GLM 兼容调用层
├── tests/                # 离线确定性自动化测试
└── docs/                  # 人看的文档
    ├── 项目背景.md         # vibe coding 时贴给 AI 的全局背景
    ├── 接口约定.md         # 模块间 JSON 契约（改前必读）
    ├── 分工_P1_编排与集成.md # 成员 P1 的 S0–S6 任务书
    ├── 分工_P2_数据与检索.md # 成员 P2 的 S0–S6 任务书
    ├── 分工_P3_画像与生成.md # 成员 P3 的 S0–S6 任务书
    ├── 分工_P4_审核与评估.md # 成员 P4 的 S0–S6 任务书
    └── 新成员培训_环境工具搭建.md  # 新人入组环境配置指南
```

`knowledge_base/build_kg.py` 与 `agents/simulated_learner.py` 仍是规划项，当前工作区不存在，不能描述为已完成。

## 硬规则

- **运行任何 Python 前先激活 venv**：`source venv/bin/activate`（macOS）或 `venv\Scripts\activate`（Windows），否则找不到依赖。VS Code 已配好 `.vscode/settings.json` 自动激活。
- **密钥只放 `.env`，永不写进代码、永不提交。** 代码里用 `os.getenv()` 读。
- **改任何 Agent 前，先读 `docs/接口约定.md`。** 输入输出的 JSON 结构是全组约定，不能私自改；要改先由当阶段值班集成人和下游成员确认。
- **先搭骨架再填肉**：新模块可先用最小 stub 验证契约；当前主链路以真实实现和测试为准。
- **按阶段而非按 Agent 固定分人。** 每阶段 4 人并行，每项交付物必须由另一名成员复现验收，详见 `docs/阶段制分工与互验计划.md`。
- 联网服务（Streamlit）默认无鉴权，仅本地 Demo 用，勿暴露公网。

## 深入文档

| 想了解 | 读这里 |
|---|---|
| 当前 4 人阶段制分工、时间表和互验规则 | `docs/阶段制分工与互验计划.md` |
| 项目背景、五大研究方向、评分维度 | `docs/项目背景.md` |
| 每个 Agent 的输入输出 JSON 契约 | `docs/接口约定.md` |
| 完整研究方案（含提示词技巧） | `docs/项目研究方案.md` |
| 比赛原始要求 | `docs/比赛方案.pdf` |
| 怎么安装运行 | `README.md` |
| 成员 P1 的逐阶段任务、交付和互验要求 | `docs/分工_P1_编排与集成.md` |
| 成员 P2 的逐阶段任务、交付和互验要求 | `docs/分工_P2_数据与检索.md` |
| 成员 P3 的逐阶段任务、交付和互验要求 | `docs/分工_P3_画像与生成.md` |
| 成员 P4 的逐阶段任务、交付和互验要求 | `docs/分工_P4_审核与评估.md` |
| 新人入组：装环境、配工具、Git/VS Code/API 申请 | `docs/新成员培训_环境工具搭建.md` |
