你是智策育训项目的 Python 工程师。任务：为两个新岗位编写培训任务包草稿，加入 `data/training_tasks.json`。

## 背景
黄金任务包（TASK-CNC-SAFE-CHECK-001，数控机床操作工——开机前安全检查）已落地并通过全链路。现在扩展两个稳定岗位的任务包（方案 C4 范围，前提 C2/C3 已通过）：
1. **CNC 编程员**——主轴、冷却液、程序结束指令与安全运行检查（方案 3.2 指定）
2. **质检员**——卡尺测量、读数、误差判断与结果记录（方案 3.2 指定）

## 涉及文件（只允许改这一个）
- `data/training_tasks.json`（当前是单任务包对象，需改为**对象数组**：原黄金任务包 + 两个新任务包）

## 数据纪律（最高优先级，违反即失败）
1. **先读 `data/knowledge.json` 全文**。CNC 编程任务包可引用 CNC 编程相关已验证知识（主题含 CNC编程/M代码/主轴/冷却液/加工缺陷等，ID 形如 CNC-PROG-*/CNC-M-*/CNC-CUT-* 等）；质检任务包可引用 QC-MEASURE-*/QC-* 相关已验证知识。**确认每个引用的知识ID真实存在、内容吻合、验证状态=已验证**。
2. **禁止编造**：知识库没有的设备参数（如具体转速数值）、标准号、量化指标（如"误差小于0.02mm"）→ 一律留空/写进 `来源缺口`，不得虚构。
3. `验证状态` 一律 "草稿"，`版本` "0.1"，`核验记录` 空数组。
4. 两个新任务包**必须与黄金任务包保持相同结构**（学习目标/操作步骤/常见错误/练习任务/考核/来源缺口），字段完整。
5. 每个任务包的任务名称和步骤设计要贴合真实岗位任务（15-30分钟微课）。

## 结构要求（每个新任务包）
- `任务包ID`：`TASK-CNC-PROG-SAFE-001`（CNC编程员）、`TASK-QC-CALIPER-001`（质检员）
- `岗位`：CNC编程员 / 质检员
- `适用范围`：设备类型/具体型号（未指定）+培训环境+建议时长分钟
- `前置技能`：≥2 条
- `知识ID`：该任务包主要引用的知识ID列表
- `学习目标`：≥1 条（行为/条件/标准/引用知识ID）
- `操作步骤`：≥4 条（序号/操作/判定标准/异常处理/引用知识ID）
- `常见错误`：≥2 条（错误/后果/纠正/引用知识ID）
- `练习任务`：任务/所需材料/完成证据
- `考核`：题目≥2（含标准答案+引用知识ID）/评分规则≥2/合格线/错后补学≥2（含引用知识ID）
- `来源缺口`：所有无法用现有知识支撑的内容

## 验证命令（完成后必须跑）
```bash
cd /Users/xuyunze/Documents/AiWork && source venv/bin/activate && unset PYTHONPATH
python3 -c "
import json
raw = json.load(open('data/training_tasks.json', encoding='utf-8'))
tasks = raw if isinstance(raw, list) else [raw]
kb = json.load(open('data/knowledge.json', encoding='utf-8'))
ids = {k['知识ID'] for k in kb if k.get('验证状态') == '已验证'}
assert len(tasks) == 3, f'应有3个任务包，实际{len(tasks)}'
for t in tasks:
    assert t['验证状态'] == '草稿'
    refs = set(t['知识ID'])
    for o in t['操作步骤']: refs.update(o['引用知识ID'])
    for g in t['学习目标']: refs.update(g['引用知识ID'])
    for e in t['常见错误']: refs.update(e['引用知识ID'])
    assert refs <= ids, f\"{t['任务包ID']} 越界: {refs - ids}\"
    assert len(t['操作步骤']) >= 4
    assert len(t['考核']['题目']) >= 2
    assert all(k in g for g in t['学习目标'] for k in ('行为','条件','标准'))
print('C4a 校验通过:', [t['任务包ID'] for t in tasks])
"
python -m pytest -q 2>&1 | tail -3
```

## 禁止事项
- 不改 knowledge.json、不改任何代码文件。
- 不建分支、不 commit、不 push。
- 不把"草稿"写成"已核验"。
- 不编造知识库没有的参数/标准/后果。
- 黄金任务包内容**不得改动**（只允许把它包进数组）。
