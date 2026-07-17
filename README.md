# 智策育训

制造业个性化培训内容自动生成平台（兴智杯参赛项目）。
采用 1 Orchestrator + 4 Agent 架构，覆盖画像构建、知识检索、内容生成、三层审核全流程。

## 环境要求

- Python 3.10+
- 3 家大模型 API key（DeepSeek / 通义千问 / Kimi / 智谱 GLM / 豆包 中任选 3 家）

## 安装

```bash
pip install -r requirements.txt
cp .env.example .env   # 然后把你的 API key 填进 .env
```

## 运行

```bash
streamlit run app.py
```

## 项目结构

见 `CLAUDE.md` 的「目录结构」一节。
开发前请先读 `docs/项目背景.md` 和 `docs/接口约定.md`。

## 文档

- `docs/项目背景.md` — 项目背景，vibe coding 时贴给 AI
- `docs/接口约定.md` — 模块间 JSON 契约
- `智策育训_项目研究方案.md` — 完整研究方案
