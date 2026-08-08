你是智策育训项目的 Python 工程师。任务：为「培训任务包驱动的岗位微课」整改做**接口与契约层**的兼容扩展（只改契约与文档，不实现生成/审核业务逻辑）。

## 背景
项目要新增"基于完整培训任务包生成岗位微课"能力。本次整改红线：**旧字段全部保留、新字段全部可选、旧调用方式继续可运行**。你只负责契约层（TypedDict + 校验函数 + 接口文档 + 契约测试），业务实现留待后续阶段。

## 涉及文件（只允许改这些）
1. `src/zhice_yuxun/contracts.py` —— 新增可选 TypedDict 与轻量校验
2. `docs/接口约定.md` —— 新增章节记录新字段
3. `tests/test_contracts.py`（若不存在则新建 `tests/test_training_contracts.py`）—— 契约测试

## 需求

### 1. contracts.py 新增（全部 total=False 可选）
- `LearningScene`：`经验水平: str`（首次上岗|有基础|熟练）、`设备或工具: str`、`本次任务: str`、`可用时长分钟: int`
- `TrainingTask`：`任务包ID: str`、`岗位: str`、`任务名称: str`、`适用范围: dict`、`前置技能: list[str]`、`知识ID: list[str]`、`学习目标: list[dict]`、`操作步骤: list[dict]`、`常见错误: list[dict]`、`练习任务: dict`、`考核: dict`、`验证状态: str`、`版本: str`、`来源缺口: list[dict]`
- `TrainingContent` 扩展可选字段：`学习目标: list[dict]`、`适用条件: dict`、`教学步骤: list[dict]`、`常见错误: list[dict]`、`练习任务: dict`、`考核: dict`、`补学建议: list[str]`
- `LearnerProfile` 扩展可选字段：`学习场景: dict`、`本次学习目标: list[str]`、`内容约束: list[str]`
- `ReviewResult`（若已有则扩展；否则新增 TypedDict 可选字段）：`事实审核: str`（pass|fail）、`教学完整性: str`（pass|fail）、`教学问题: list[str]`、`教学完整率: float`、`目标考核对齐率: float`、`关键步骤可判定率: float`

### 2. 新增校验函数（轻量、纯 Python、无框架）
- `validate_training_task(task: dict) -> TrainingTask`：校验 任务包ID 非空、岗位非空、知识ID 全为非空字符串、学习目标每项含 行为/条件/标准、操作步骤每项含 序号/操作/判定标准/异常处理/引用知识ID、验证状态 ∈ {草稿, 已核验}。不满足抛 `ContractError`。
- `validate_learning_scene(scene: dict) -> LearningScene`：经验水平 ∈ {首次上岗, 有基础, 熟练}（可空），可用时长分钟 > 0（可空）。
- 兼容性校验函数 `validate_training_content_optional(content: dict) -> dict`：对可选字段做存在性检查（存在即校验结构），旧字段不变，缺失新字段不报错。

### 3. docs/接口约定.md 新增章节（第 8 章，标题建议「任务包与结构化微课（整改扩展，可选）」）
- 记录 `search_training_task(position: str, question: str) -> dict | None`（第一版用岗位/主题/任务别名匹配，无匹配返回 None）
- 记录 `build_profile(岗位, 答题记录=None, 学习场景=None)` 新可选参数与新增输出字段
- 记录 `generate_content(..., *, 任务包=None)` 新关键字参数与结构化输出字段
- 记录 `review_content` 输出新增 事实审核/教学完整性/教学问题 字段
- 记录 `run(岗位, 答题记录=None, question="", *, 学习场景=None, 反馈模式="", progress_callback=None)` 新可选参数
- 明确标注：所有新字段**可选**，旧调用方式不传新参数必须完全兼容；未命中任务包时沿用旧流程。

### 4. 契约测试（tests/test_training_contracts.py）
- 合法任务包通过 `validate_training_task`
- 缺 行为/条件/标准 的学习目标被拒绝
- 缺 判定标准 的操作步骤被拒绝
- 验证状态="已核验" 之外的非法值被拒绝
- 旧 `TrainingContent`（只有 类型/标题/正文/引用来源/引用知识ID/生成模式）通过 `validate_training_content_optional` 不报错
- 新可选字段存在时按结构校验

## 验证命令（完成后必须跑）
```bash
cd /Users/xuyunze/Documents/AiWork && source venv/bin/activate && unset PYTHONPATH
python -m pytest tests/test_training_contracts.py -q
python -m compileall -q src/zhice_yuxun/contracts.py
# 回归：全量测试必须仍然全过
python -m pytest -q 2>&1 | tail -3
```

## 禁止事项
- 不改 `data/training_tasks.json`、不改 5 个 Agent 的业务逻辑、不动 orchestrator 主流程。
- 不建分支、不 commit、不 push。
- 新字段必须可选：任何"因为缺少新字段而抛异常"的改动都是失败。
- 不引入第三方依赖（不用 pydantic）。
- 接口约定.md 是团队合同，只做**新增**章节，不删改既有章节措辞。
