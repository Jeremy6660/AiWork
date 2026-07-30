# P3 对 P2 的独立离线复验证据

- 执行日期：2026-07-30
- 被验收提交：`eefddbbc005afe4c5fb5d2c20979840f4efd293e`
- 检出方式：`git archive --format=zip` 到临时目录
- Python：3.13.9
- 临时解释器：独立新建的 `venv`
- 网络模型调用：0

## 依赖

| 包 | 版本 |
|---|---:|
| openai | 2.50.0 |
| streamlit | 1.60.0 |
| chromadb | 1.5.9 |
| networkx | 3.6.1 |
| python-dotenv | 1.2.2 |
| pytest | 9.1.1 |

首次依赖安装因沙箱网络限制失败；获批访问清华 PyPI 镜像后使用同一
`pip install -r requirements.txt` 命令成功。没有访问任何模型 API。

## 结论

P3 在独立临时环境实际执行 P2 指定的建库、编译、pytest、三场景和机器初标
评测命令，五条命令最终退出码均为 0。建库为 39 条，历史测试为
44 passed，三场景均通过；评测输出明确标记
“非正式：包含机器初标”。因此 P2 的 2026-07-28 离线复现结论通过 P3
独立复验，但其中指标仍不得作为正式竞赛成绩。

关键 stdout 与退出码见 `acceptance_output.txt`。P2 原始 52 条明细仍以
`artifacts/p2_offline_reproduction_20260728/` 为权威，不重复复制。
