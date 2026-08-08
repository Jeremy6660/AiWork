你是智策育训项目的 Python 工程师。任务：实现「教学完整性审核」与「Orchestrator 任务包串接」。

## 背景
整改主线：基于培训任务包生成可执行、可考核、可追溯的岗位微课。已完成：
- C1：`data/training_tasks.json` 黄金任务包草稿 + 契约层（contracts.py 的 ReviewResult 可选字段：事实审核/教学完整性/教学问题/教学完整率/目标考核对齐率/关键步骤可判定率）
- C2a：`search_training_task(position, question)` 任务包检索（retrieval.py）
- C2b-1（并行中）：`generate_content(..., *, 任务包=None)` 任务包驱动生成（generator.py）—— 生成结果含 学习目标/适用条件/教学步骤/常见错误/练习任务/考核/补学建议 结构化字段 + 渲染后的 Markdown 正文

你的任务分两块：

## 涉及文件
- `src/zhice_yuxun/agents/reviewer.py`（教学完整性审核）
- `src/zhice_yuxun/orchestrator.py`（串接任务包）
- `tests/test_training_reviewer.py`（新建）
- `tests/test_training_orchestrator.py`（新建）

## 需求

### 1. reviewer.py：教学完整性检查 `_check_teaching_completeness(content) -> tuple[bool, list[str], dict]`

纯 Python 确定性规则（不用模型），对**结构化微课**（含 学习目标/教学步骤/考核 等新字段的内容）检查。旧式内容（无这些字段）直接返回 `(True, [], {})` 表示"未启用"——**绝不能让旧内容因缺新字段而审核失败**。

检查项（依据整改方案 7.1）：
1. 至少 1 个学习目标，且每个含 行为/条件/标准 三键；
2. 教学步骤 ≥ 4 条；
3. 每个教学步骤含 判定标准 或 异常处理（安全关键步骤两个都要有）；
4. 每个教学步骤的 引用知识ID 非空；
5. 至少 1 个练习任务；
6. 考核含 题目（≥2）且（标准答案 或 评分规则 非空）且 合格线 非空；
7. 考核题目能映射到学习目标（题目文本或考核内"关联目标"字段与学习目标的行为有重合；第一版可放宽为：考核存在即算映射，但"考核为空"直接失败）；
8. 设备型号未知（适用条件.设备 含"未指定"或"未知"）时，正文与教学步骤不得出现型号专属参数（检测规则：正文或步骤中出现 `[A-Za-z]+[- ]?\d{3,}` 形式的型号模式，如 HAAS-VF2、Fanuc 0i 的 0i 等——用简单正则，宁可漏报不可误伤，只查明显型号串）；
9. 补学建议非空（错后补学）。

返回 `(passed: bool, problems: list[str], metrics: dict)`，metrics 含：
- `教学完整率`: 通过项/总检查项（第 1-9 项，未启用时=1.0）
- `目标考核对齐率`: 考核与目标映射比例（简单：有考核且有目标=1.0，缺任一=0.0）
- `关键步骤可判定率`: 含判定标准或异常处理的步骤数/总步骤数

### 2. reviewer.py：review_content 集成
- 在现有 `review_content(培训内容, 知识列表)` 中，**现有事实审核逻辑完全不动**；
- 新增返回字段（全部可选，旧调用方不受影响）：
  - `事实审核`: "pass"（现有规则通过时）或 "fail"
  - `教学完整性`: "pass" / "fail" / "未启用"（内容无结构化字段时）
  - `教学问题`: list[str]（教学完整性未通过时的具体问题，如"考核缺少合格线"、"第3个教学步骤缺少判定标准"）
  - `教学完整率` / `目标考核对齐率` / `关键步骤可判定率`: float
- 最终 `通过` 与 `流程状态` 的判定规则：**教学完整性 fail 时整体不得判"通过"**——即事实审核 pass 但教学完整性 fail → `通过=False`、`流程状态="失败"`，修改建议中合并教学问题（"教学不完整：" + 具体问题）。"未启用"不影响原判定。
- 幻觉分数保持原定义不变（不混入教学分）。

### 3. orchestrator.py：任务包串接
- `run()` 签名扩展：`run(岗位, 答题记录=None, question="", *, 学习场景=None, 反馈模式="", progress_callback=None)`；
- 新流程（在现有画像→检索之间插入）：
  1. `build_profile(岗位, 答题记录, 学习场景)`（传学习场景）；
  2. 若 `question` 非空：先 `search_training_task(岗位, question)`；命中任务包且 `验证状态=="已核验"` → 用任务包的知识ID从知识库加载知识（过滤"已验证"条目），走任务包生成：`generate_content(profile, knowledge, topic, advice, 任务包=taskpkg)`，生成结果带结构化字段，审核走事实+教学完整性双审核；
  3. 命中草稿任务包 → 不直接生成完整微课，走旧知识检索生成路径，并在返回结果加 `"任务包提示": "当前可提供知识说明，但该任务包尚未完成专业核验，不能生成完整培训微课"`；
  4. 未命中任务包 → 完全走旧路径（知识检索→旧生成→旧审核）；
  5. 新返回字段（全部可选）：`"任务包": taskpkg 或 None`、`"任务包提示": str`（未命中时为空串）。
- 所有旧调用（不传学习场景）行为必须与现在完全一致（105 项旧测试不能挂）。
- 注意：`question` 为空时（默认 topic 场景）跳过任务包检索，走旧流程。

### 4. 测试
- reviewer：删除学习目标→fail；删除关键步骤判定标准→fail（对应教学问题能指出步骤号）；插入明显型号参数且设备未知→fail；结构化内容齐全→pass；旧式内容（无结构化字段）→"未启用"且不影响通过；教学问题能指出具体字段。
- orchestrator：传学习场景+命中已核验任务包（测试用 ALLOW_DRAFT_TASKPKG=1 + 临时把黄金任务包状态标为已核验的方式，或构造最小已核验任务包写入临时 data 目录——用 monkeypatch 指向临时文件更安全）→ 返回含 任务包 字段、教学步骤、审核通过；未命中任务包→返回 任务包=None 且行为同旧路径；question 为空→旧路径；教学完整性失败时整体不通过。
- 全量回归 105+ 全过。

## 验证命令（完成后必须跑）
```bash
cd /Users/xuyunze/Documents/AiWork && source venv/bin/activate && unset PYTHONPATH
python -m pytest tests/test_training_reviewer.py tests/test_training_orchestrator.py -q
python -m compileall -q src/zhice_yuxun/agents/reviewer.py src/zhice_yuxun/orchestrator.py
# 全量回归（当前 105 项 + C2b-1 新增，必须全过）
python -m pytest -q 2>&1 | tail -3
python test_run.py 2>&1 | tail -3
```

## 禁止事项
- 不改 contracts.py、retrieval.py、profile.py、generator.py、data/training_tasks.json。
- 不建分支、不 commit、不 push。
- 旧调用方式零破坏：不传学习场景/无任务包时行为与现在完全一致。
- 教学完整性与事实审核是**两套独立检查**，不得混成一个分数。
- 不引入第三方依赖。
- 测试不得调用真实模型（强制离线）。
