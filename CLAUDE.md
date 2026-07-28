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
| 大模型 | 调 3 家不同厂商 API（DeepSeek / 通义 / Kimi / GLM / 豆包 任选 3） |
| 编排 | 纯 Python 函数调用 |

## 目录结构

```
AiWork/
├── CLAUDE.md              # 本文件（AI 规则手册）
├── README.md             # 人看的：怎么装、怎么跑
├── app.py                # Streamlit 主界面
├── orchestrator.py        # 编排：串起 4 个 Agent
├── requirements.txt
├── .env.example           # API key 模板（真实 key 放 .env，禁止提交）
├── agents/                # Agent 模块
│   ├── retrieval.py       # 知识检索 Agent
│   ├── profile.py         # 画像 Agent
│   ├── generator.py       # 内容生成 Agent
│   ├── reviewer.py        # 三层审核 Agent
│   ├── evaluator.py       # 效果评估模块
│   └── simulated_learner.py  # 仿真学员（仅评测用）
├── knowledge_base/        # 知识库
│   ├── build_chromadb.py  # 向量库建库脚本
│   ├── build_kg.py        # 知识图谱构建脚本
│   ├── skill_ontology.json # 岗位技能本体
│   └── qa_test_set.json   # QA 评测集
├── data/                  # 制造业原始/清洗后数据
└── docs/                  # 人看的文档
    ├── 项目背景.md         # vibe coding 时贴给 AI 的全局背景
    ├── 接口约定.md         # 模块间 JSON 契约（改前必读）
    ├── 阶段制分工与互验计划.md # 当前唯一有效的人员分工
    └── 分工_P1_* 至 P4_*   # 旧版模块技术参考
```

## 硬规则

- **密钥只放 `.env`，永不写进代码、永不提交。** 代码里用 `os.getenv()` 读。
- **改任何 Agent 前，先读 `docs/接口约定.md`。** 输入输出的 JSON 结构是全组约定，不能私自改；要改先由当阶段值班集成人和下游负责人确认。
- **先搭骨架再填肉**：新模块先写返回假数据的 stub，让全链路能跑通，再换真实实现。
- **按阶段而非按 Agent 固定分人。** 每阶段 4 人并行，每项交付物必须由另一名成员复现验收，详见 `docs/阶段制分工与互验计划.md`。
- 联网服务（Streamlit）默认无鉴权，仅本地 Demo 用，勿暴露公网。

## 深入文档

| 想了解 | 读这里 |
|---|---|
| 当前 4 人阶段制分工、时间表和互验规则 | `docs/阶段制分工与互验计划.md` |
| 项目背景、五大研究方向、评分维度 | `docs/项目背景.md` |
| 每个 Agent 的输入输出 JSON 契约 | `docs/接口约定.md` |
| 完整研究方案（含提示词技巧） | `智策育训_项目研究方案.md` |
| 比赛原始要求 | 根目录 PDF |
| 怎么安装运行 | `README.md` |
| 各模块技术细节（旧版人员分工，不再照此分人） | `docs/分工_P1_*` 至 `docs/分工_P4_*` |
