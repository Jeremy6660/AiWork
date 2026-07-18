# 智策育训

制造业个性化培训内容自动生成平台，采用“画像 → 可溯源检索 → 约束生成 → 断言审核 → 动态决策”的多 Agent 闭环。

当前版本默认采用严格知识边界：知识库未覆盖的问题会安全拒绝，不再返回无关兜底内容。

## 环境

- Python 3.10–3.14（当前验证环境：3.14）
- Streamlit、ChromaDB、NetworkX
- DeepSeek API Key 可选；无 Key 时可以运行确定性离线闭环

## 安装与初始化

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # 需要真实模型时再填写 Key
python knowledge_base/build_chromadb.py
```

知识文件位于 `data/knowledge.json`。只有 `验证状态=已验证` 的条目会进入 ChromaDB。

## 运行

```bash
source venv/bin/activate

# 自动化验收
pytest -q

# 人工命令行演示；任一场景失败会返回非零退出码
python test_run.py

# Streamlit 界面
streamlit run app.py
```

## 模型与审核开关

`.env` 中可配置：

- `GENERATION_MODE=auto|llm|offline`
- `ALLOW_OFFLINE_FALLBACK=1|0`
- `ENABLE_LLM_REVIEW=1|0`
- `ENABLE_L3_VOTING=1|0`
- `DEEPSEEK_MODEL=deepseek-v4-flash`

默认不会调用付费审核 API。开启 L3 后，如果可用独立供应商不足两个，系统只会给出“需人工复核”，不会伪造三模型投票。

## 可信度边界

- 当前单份内容的事实性、匹配度等是透明诊断值，不等于正式测试集准确率。
- “幻觉率 <5% / 适配准确率 ≥85% / 覆盖率 ≥90%”只能在人工复核的评测集上实测后使用。
- 制造业安全内容必须结合具体设备型号和现场规程，由专业人员复核后用于实际培训。

接口与状态定义见 `docs/接口约定.md`，项目规则见 `AGENTS.md` 与 `CLAUDE.md`。
