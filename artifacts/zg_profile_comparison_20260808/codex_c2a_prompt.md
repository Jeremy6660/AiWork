你是智策育训项目的 Python 工程师。任务：为「培训任务包驱动的岗位微课」整改实现**输入侧**两个 Agent 的兼容扩展：任务包检索 + 画像学习场景。

## 背景
整改主线：基于 `data/training_tasks.json` 中的完整培训任务包生成岗位微课（15-30 分钟任务卡）。上一阶段已完成契约层（`src/zhice_yuxun/contracts.py` 新增 `LearningScene`/`TrainingTask` TypedDict、`validate_learning_scene`/`validate_training_task` 校验函数，`docs/接口约定.md` 第 8 章）。你负责实现：

1. `src/zhice_yuxun/agents/retrieval.py`：新增 `search_training_task(position: str, question: str) -> dict | None`
2. `src/zhice_yuxun/agents/profile.py`：`build_profile` 接收可选 `学习场景` 参数

## 涉及文件（只允许改这两个 + 对应测试）
- `src/zhice_yuxun/agents/retrieval.py`
- `src/zhice_yuxun/agents/profile.py`
- `tests/test_training_retrieval.py`（新建）与 `tests/test_training_profile.py`（新建）

## 需求

### 1. retrieval.py: search_training_task(position, question)
- 从 `data/training_tasks.json` 加载任务包列表（用 `src/zhice_yuxun/paths.py` 推导路径，参考现有代码如何定位 `data/` 目录）。
- 匹配逻辑（第一版用最简规则，不建向量库）：
  - 岗位必须完全匹配 `任务包.岗位`（同岗位才可能命中）；
  - 问题与 `任务名称`、任务包内步骤关键词、`主题`（若任务包有）做包含匹配：将 question 分词后，任一分词出现在任务名称或 3 个以上步骤的"操作"文本中即视为命中；
  - 同义改写支持：至少内置一组别名映射（如"开机安全检查"→"开机前安全检查与门联锁验证"、"门锁"→"门联锁"、"点检"→"检查"），对 question 做别名归一后再匹配；
  - 多任务包命中时取"步骤命中数最多"的；
  - 无匹配返回 `None`（绝不返回错误岗位或低相关任务包）。
- 只返回 `验证状态 == "已核验"` 的任务包？**不**——第一版返回任何状态的任务包，但把 `验证状态` 原样带出，由下游决定是否可用（这样草稿任务包也能跑通开发调试）。同时把 `验证状态` 写入返回字典。
- 返回完整任务包字典（原样返回，不做裁剪）。
- 对非法输入（position/question 非字符串或空白）抛 `ValueError`。

### 2. profile.py: build_profile(岗位, 答题记录=None, 学习场景=None)
- 签名扩展为 `def build_profile(岗位: str, 答题记录: list | None = None, 学习场景: dict | None = None) -> dict`（保持旧参数顺序）。
- `学习场景` 为 None 或空 dict 时：行为与旧版完全一致（不得有任何新字段），保证旧调用零破坏。
- `学习场景` 非空时：
  - 用 `validate_learning_scene` 校验（contracts.py 已提供），非法抛 `ContractError`；
  - 画像输出新增可选字段：`学习场景: dict`（原样放入）、`本次学习目标: list[str]`（从学习场景的"本次任务"生成 1-2 条目标表述，如"本次任务"为"开机前安全检查"→"能按检查表独立完成开机前安全检查"）、`内容约束: list[str]`（若"设备或工具"为空或含"未知"，加入"设备型号未知，不得生成型号专属参数"；若"经验水平"存在，可加入对应教学脚手架说明）。
- 画像中已有的"推荐难度"不应被学习场景直接覆盖（保留原有难度推导逻辑）；学习场景只增加上下文字段。

### 3. 测试（tests/test_training_retrieval.py、tests/test_training_profile.py）
- 检索：岗位+任务名命中返回正确任务包；同义改写命中（如"开机安全检查"）；相似但未覆盖任务返回 None；跨领域问题返回 None；不返回其他岗位任务包；非法输入抛 ValueError。
- 画像：缺省学习场景时输出与旧版字段集合一致（断言不含"学习场景"键）；传入合法学习场景时新增三字段；非法学习场景（如"经验水平":"专家"）抛 ContractError。
- 测试中读取真实 `data/training_tasks.json`（已存在黄金任务包草稿 TASK-CNC-SAFE-CHECK-001，岗位=数控机床操作工）。

## 验证命令（完成后必须跑）
```bash
cd /Users/xuyunze/Documents/AiWork && source venv/bin/activate && unset PYTHONPATH
python -m pytest tests/test_training_retrieval.py tests/test_training_profile.py -q
python -m compileall -q src/zhice_yuxun/agents/retrieval.py src/zhice_yuxun/agents/profile.py
# 全量回归必须全过（含旧 88 项）
python -m pytest -q 2>&1 | tail -3
# 手工冒烟：确认黄金任务可命中
python -c "
from src.zhice_yuxun.agents.retrieval import search_training_task
t = search_training_task('数控机床操作工', '开机前安全检查怎么做')
print('命中:', t['任务包ID'] if t else None)
t2 = search_training_task('数控机床操作工', '核电站操作规程')
print('跨领域:', t2)
"
```

## 禁止事项
- 不改 `data/training_tasks.json`、不改 generator/reviewer/orchestrator、不改 contracts.py。
- 不建分支、不 commit、不 push。
- 不得为了命中任务包而放宽岗位匹配（跨岗位命中=失败）。
- 不引入第三方依赖、不建向量库、不用 ChromaDB。
- 旧调用方式零破坏：任何"没传学习场景就报错"的改动都是失败。
