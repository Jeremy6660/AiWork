# P3 三画像离线对比证据

- 执行日期：2026-07-30
- 生成命令：`python scripts/generate_3_profile_comparison.py`
- 网络调用：0；脚本强制 `GENERATION_MODE=offline`
- 适用范围：稳定岗位“质检员”的入门、应用、进阶三种画像

`3_profile_comparison.json` 保存同一主题、同一岗位下的三种画像与三类资源输出。
该结果只证明离线差异化路径可重复，不是人工复核后的适配准确率，也不是
真实大模型效果。
