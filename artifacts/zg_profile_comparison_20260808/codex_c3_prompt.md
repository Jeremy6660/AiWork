你是智策育训项目的 Python 工程师。任务：建立「可信盲测与完整链路评测」——打破"用同一份数据出题、给答案和判卷"的自证闭环。

## 背景
整改主线：基于培训任务包生成可执行、可考核、可追溯的岗位微课。已完成：
- C1：黄金任务包草稿 + 契约层（`contracts.validate_training_task` 等）
- C2a：`search_training_task(position, question)` 任务包检索（含同义改写、岗位严格匹配）
- C2b：`generate_content(..., *, 任务包=None)` 任务包驱动生成、`review_content(..., *, 任务包=None)` 双审核（事实+教学完整性）、`orchestrator.run(岗位, 答题记录=None, question="", *, 学习场景=None, 反馈模式="", progress_callback=None)` 全链路串接
- 现有评测：`knowledge_base/evaluate_benchmark.py`（**旧入口，直接按预期知识ID取知识喂生成器——这就是要打破的自证闭环**）

## 涉及文件
1. `knowledge_base/training_blind_test_set.json`（新建，30 条冻结盲测）
2. `knowledge_base/evaluate_benchmark.py`（新增完整链路评测入口，**不删除旧入口**）
3. `tests/test_blind_test_leakage.py`（新建，防泄漏测试）
4. `docs/接口约定.md`（第 9 章，记录盲测与评测约定——只追加）

## 需求

### 1. 盲测集：knowledge_base/training_blind_test_set.json（30 条冻结）
结构（每条）：
```json
{
  "案例ID": "BLIND-001",
  "类别": "正常表达 | 同义改写 | 场景问题 | 近领域负例 | 跨领域负例",
  "问题": "原始用户问题",
  "岗位": "数控机床操作工",
  "学习场景": {"经验水平": "首次上岗", "设备或工具": "", "本次任务": "开机前安全检查", "可用时长分钟": 20},
  "期望": "命中任务包 | 知识说明 | 拒绝",
  "备注": "为什么这样设计"
}
```

类别分布（必须严格遵守）：
- 正常表达 6 条：直接询问黄金任务（如"开机前安全检查怎么做"、"门联锁怎么验证"）
- 同义改写 6 条：口语/简称/不同表述（如"开机要检查啥"、"门锁好使吗怎么确认"、"上机前点检"）
- 场景问题 6 条：带异常现象或任务上下文（如"防护门关上了但机器报警，怎么排查"、"今天开机发现联锁钥匙有点弯"）
- 近领域负例 6 条：同为数控机床但任务包未覆盖（如"怎么换刀"、"主轴转速怎么设"、"G代码怎么编"）→ 期望"拒绝"或"知识说明"
- 跨领域负例 6 条：核电、医疗、焊接等明显未覆盖（如"核电站操作规程"、"心电监护仪操作"）→ 期望"拒绝"

**冻结纪律（红线）**：
- 问题**不得**从知识条目主题字段机械拼接；
- 问题**不得**直接复制知识正文；
- 不写参考答案（避免评测时按答案反推）；
- 每条给出"期望"类别（任务包命中/知识说明/拒绝），供评测对照。

### 2. 完整链路评测入口：evaluate_benchmark.py 新增 `run_full_chain_evaluation(blind_set_path=None)`
- **必须从原始问题进入 `orchestrator.run()`**，不得按预期知识ID直接取知识喂生成器；
- 对每条盲测样例：
  - 调 `run(岗位, question=问题, 学习场景=学习场景)`（强制离线：设 `GENERATION_MODE=offline`、`ALLOW_DRAFT_TASKPKG=1`——因为黄金任务包目前是草稿，盲测要能跑通全链路；输出必须标注"非正式（草稿任务包）"）；
  - 判定结果：
    - `期望=命中任务包` → 结果含任务包且 流程状态=通过 → 命中成功；
    - `期望=知识说明` → 结果无任务包但有培训内容（旧路径生成）→ 成功；
    - `期望=拒绝` → 流程状态=失败 → 成功（安全拒绝）。
- 汇总指标（必须能从明细复算）：
  - 任务包检索命中率（期望命中任务包的样例中实际命中的比例）
  - 正确拒绝率（期望拒绝的样例中实际拒绝的比例）
  - 总体一致率（期望与实际判定一致的比例）
  - 明细：每条 案例ID/类别/期望/实际/流程状态/任务包ID（若有）
- 输出结构：`{"数据状态": "非正式（草稿任务包）", "盲测集": "training_blind_test_set.json", "盲测哈希": "sha256", "总体一致率": x, "任务包检索命中率": x, "正确拒绝率": x, "案例数": 30, "明细": [...]}`
- 命令行参数：`--blind` 走完整链路入口，`--blind-hash` 打印盲测文件哈希。

### 3. 防泄漏测试：tests/test_blind_test_leakage.py
- 盲测集 30 条、五类各 6 条；
- 盲测问题**不包含**任何知识条目主题字段的机械拼接（抽查：至少 10 条问题与 knowledge.json 中任一条的"主题"字段没有完全相同的字符串）；
- 盲测问题**不包含**知识正文（抽查：任一条问题不是任何知识条目的内容子串）；
- 评测代码不读取盲测集中的"参考答案/预期知识ID"（盲测集根本没有这些字段——测试断言文件里没有这些键）；
- 盲测集冻结：测试记录当前 sha256 哈希到 `artifacts/zg_profile_comparison_20260808/blind_test_sha256.txt`，第二次运行比对一致（先断言文件存在且内容等于重新计算的哈希；若文件不存在则创建）；
- 开发集（qa_test_set.json）与盲测集（training_blind_test_set.json）是不同文件。

### 4. 接口约定.md 第 9 章
记录：盲测集结构、类别分布、冻结哈希机制、完整链路评测入口命令、指标定义、旧评测入口标记为"历史管线自检（已弃用为正式依据）"。

## 验证命令（完成后必须跑）
```bash
cd /Users/xuyunze/Documents/AiWork && source venv/bin/activate && unset PYTHONPATH
python -m pytest tests/test_blind_test_leakage.py -q
python -m compileall -q knowledge_base/evaluate_benchmark.py
# 完整链路评测（应能跑通30条，离线、草稿任务包放行）
python knowledge_base/evaluate_benchmark.py --blind 2>&1 | tail -20
# 全量回归（当前 124 项必须全过）
python -m pytest -q 2>&1 | tail -3
```

## 禁止事项
- 不删除旧评测入口 `run_benchmark`（保留并标记历史）；
- 评测代码**不得**按预期知识ID直接构造生成输入（盲测集没有这个字段，也禁止从 qa_test_set 借）；
- 不改 orchestrator/generator/reviewer/retrieval 业务逻辑（如确需小改动，先说明理由，禁止静默改）；
- 不调真实模型（强制离线）；
- 不建分支、不 commit、不 push。
- 盲测问题必须原创编写（中文口语化），不得从知识库机械复制。
