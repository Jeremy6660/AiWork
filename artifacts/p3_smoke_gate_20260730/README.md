# P3 真实模型 smoke 零费用门禁

- 执行日期：2026-07-30
- 命令：`python scripts/smoke_llm.py --provider deepseek --scenario generate`
- 供应商：DeepSeek
- 模型：`deepseek-v4-flash`
- 本机 Key：已配置，但未输出、未读取其值
- 预计逻辑调用次数：0
- 实际网络调用：0
- 费用：0

默认命令只输出脱敏计划并以 dry-run 结束。真实调用必须额外提供 `--execute`，
随后在终端输入 `EXECUTE`；本证据包没有执行该路径。

无 Key、超时、无效 JSON、单供应商失败及可用独立供应商不足两个等路径由
离线 pytest 模拟，见 `tests/test_smoke_llm.py`、`tests/test_llm_client.py` 和
`tests/test_orchestrator.py`。
