你是智策育训项目的 Python 工程师。任务：实现「任务包驱动的结构化离线生成」——当调用方传入培训任务包时，`generate_content` 输出可执行、可考核、可追溯的岗位微课（学习目标/适用条件/教学步骤/常见错误/练习任务/考核/补学建议 + 渲染 Markdown 正文）。

## 背景
整改主线：基于 `data/training_tasks.json` 的完整培训任务包生成 15-30 分钟岗位微课。数据层已完成：黄金任务包草稿 `TASK-CNC-SAFE-CHECK-001`（数控机床操作工——开机前安全检查与门联锁验证，6 步骤/3 学习目标/4 常见错误/4 考核题/6 来源缺口）。契约层已完成：`TrainingContent` 已扩展可选字段（学习目标/适用条件/教学步骤/常见错误/练习任务/考核/补学建议），`contracts.validate_training_content_optional` 已提供。

## 涉及文件
- `src/zhice_yuxun/agents/generator.py`（唯一改动文件）
- `tests/test_training_generator.py`（新建）

## 需求

### 1. generate_content 签名扩展（保持向后兼容）
```python
def generate_content(
    画像: dict[str, Any],
    知识列表: list[dict[str, Any]],
    培训主题: str,
    修改建议: str = "",
    *,
    任务包: dict[str, Any] | None = None,
) -> dict[str, Any]
```
`任务包` 为 None 时行为与现在完全一致（旧路径零改动）。

### 2. 任务包驱动的离线确定性生成 `_offline_generate_taskpkg(profile, knowledge, topic, taskpkg, mode)`
当 `任务包` 非空且 `任务包["验证状态"] == "已核验"` 时走此路径；`验证状态 != "已核验"` 时必须**拒绝生成**（抛 `ContractError("任务包尚未核验，不能作为完整培训课程依据")`），绝不把草稿伪装成完整课程。为便于开发调试，环境变量 `ALLOW_DRAFT_TASKPKG=1` 时可放行草稿（生成模式标注"离线确定性（草稿任务包）"）。

输出结构（全部字段都从任务包填充，禁止自由发挥）：
```json
{
  "类型": "实操指南",   // 任务包微课固定为实操指南，忽略画像资源类型映射
  "标题": "{任务名称}｜{岗位} 岗位微课",
  "正文": "见下方 Markdown 渲染规则",
  "引用来源": [任务包引用知识ID对应的来源，去重],
  "引用知识ID": [任务包 知识ID + 各步骤/目标/错误中的引用知识ID，去重],
  "生成模式": "离线确定性（任务包驱动）",
  "学习目标": [从任务包 学习目标 原样带入],
  "适用条件": {
    "设备": 任务包.适用范围.设备类型,
    "环境": 任务包.适用范围.培训环境,
    "前置技能": 任务包.前置技能,
    "建议时长分钟": 任务包.适用范围.建议时长分钟
  },
  "教学步骤": [从任务包 操作步骤 原样带入],
  "常见错误": [从任务包 常见错误 原样带入],
  "练习任务": 任务包.练习任务,
  "考核": 任务包.考核,
  "补学建议": [从 考核.错后补学 的"补学内容"字段生成列表]
}
```

### 3. Markdown 正文渲染规则（从结构化字段渲染，不能反过来猜）
按以下章节渲染（用 Markdown）：
- `## 本次培训任务`：任务名称 + 适用范围（设备类型/环境/建议时长/前置技能）
- `## 学习目标`：逐条列出 行为（条件，标准）
- `## 分步操作与判断标准`：逐步骤：`### 步骤N 操作` + `- 判定标准：...` + `- 异常处理：...`（异常处理非空才输出）
- `## 常见错误与纠正`：错误→后果→纠正
- `## 练习任务`：任务 + 所需材料 + 完成证据
- `## 考核与合格标准`：题目列表 + 合格线
- `## 错后补学`：补学建议
- 正文中每个步骤/目标/错误的**关键事实句末**标注 `[知识ID]`（从该条目 引用知识ID 取，多个用顿号分隔）。
- 适用条件中"具体型号"若为"未指定"或含"未知"，在正文开头加边界提示：`> 边界提示：本任务包未指定具体设备型号，涉及型号专属参数时请查阅本机操作说明书。`

### 4. 知识点加载
任务包驱动时，`知识列表` 由调用方传入（C2a 的检索方保证包含任务包引用的知识）。`_offline_generate_taskpkg` 内部要校验：任务包引用的知识ID ⊆ 传入知识列表的知识ID，缺了抛 `ContractError`（防止任务包引用了没加载的知识还继续生成）。标题/正文渲染不受旧 `_resource_type` 影响。

### 5. 旧函数不动
`_offline_generate`、`_llm_generate`、`_validate_grounding`、`_filter_hallucinated_sources` 等旧函数**不修改**。在 `generate_content` 中加分支：任务包非空→`_offline_generate_taskpkg`（不区分 LLM/离线，第一版任务包微课一律确定性生成，真实 LLM 语言优化留待 C4 之后）。

### 6. 测试（tests/test_training_generator.py）
- 传入 None 任务包：输出与旧版字段一致（不含"教学步骤"等新字段）；
- 传入已核验任务包（测试里构造一个 `验证状态="已核验"` 的最小任务包 fixture）：输出含全部结构化字段、正文含"## 分步操作与判断标准"、每步骤判定标准在正文出现、引用知识ID 覆盖任务包引用；
- 传入草稿任务包：默认抛 ContractError；设置 `ALLOW_DRAFT_TASKPKG=1` 后成功且生成模式含"草稿任务包"；
- 任务包引用知识不在知识列表：抛 ContractError；
- 无具体型号时正文含边界提示。

## 验证命令（完成后必须跑）
```bash
cd /Users/xuyunze/Documents/AiWork && source venv/bin/activate && unset PYTHONPATH
python -m pytest tests/test_training_generator.py -q
python -m compileall -q src/zhice_yuxun/agents/generator.py
# 全量回归（必须仍全过，含旧 88 项 + C2a 新增）
python -m pytest -q 2>&1 | tail -3
```

## 禁止事项
- 不改 contracts.py、retrieval.py、profile.py、reviewer.py、orchestrator.py、data/training_tasks.json。
- 不建分支、不 commit、不 push。
- 草稿任务包不得伪装成完整课程（默认必须拒绝）。
- 不从自由文本猜测结构化字段——结构只来自任务包数据。
- 不引入第三方依赖。
