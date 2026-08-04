# P2 离线复现原始证据清单

执行日期：2026-07-28  
项目 commit：`eefddbbc005afe4c5fb5d2c20979840f4efd293e`

## 文件用途

| 文件 | 用途 |
|---|---|
| `01_environment_setup_full.txt` | 初始环境、Git、旧 venv 删除、建 venv，以及首次激活失败 |
| `02_activation_retry_and_dependencies_full.txt` | 当前进程执行策略修复、激活成功，以及首次 pip 网络失败 |
| `03_dependency_install_network_retry_full.txt` | 获批联网安装的执行轨迹；PowerShell 5.1 transcript 未捕获原生命令 stdout |
| `04_offline_acceptance_full.txt` | 首轮命令 4–8 的执行轨迹；PowerShell 5.1 transcript 未捕获原生命令 stdout |
| `05_boundary_sample_full.txt` | 未覆盖问题安全拒答的执行轨迹 |
| `06_command3_pip_install_success_full.txt` | 命令 3 成功路径的完整 stdout、stderr、退出码 |
| `07_dependency_versions_full.txt` | 全部直接和传递依赖版本 |
| `08_command4_build_full.txt` | 命令 4 完整输出与退出码 |
| `09_command5_compileall_full.txt` | 命令 5 完整输出与退出码 |
| `10_command6_pytest_full.txt` | 命令 6 完整输出与退出码 |
| `11_command7_three_scenarios_full.txt` | 命令 7 完整输出与退出码 |
| `12_command8_draft_benchmark_full.txt` | 命令 8 完整输出、52 条明细与退出码 |
| `13_git_worktree_state_full.txt` | Git commit、最终工作树状态和运行前已存在的 `test_run.py` 差异 |

## SHA-256

```text
01_environment_setup_full.txt  28C06398DDE64E40CBEFDF9BC060E9D52FD74CE3C7AB7485E5EB52D46F262BD9
02_activation_retry_and_dependencies_full.txt  DDD608F48D2A19020D533AA9E92E3E3E8B85E14019841553BDF2517B6CA70C66
03_dependency_install_network_retry_full.txt  6A508209BA55545D0F2A87D6FC3E6C69A1323D0E24244F2B7EE6826371D53067
04_offline_acceptance_full.txt  5C71B279CF45ED45864BD8E1A77191FD7E858192CFC153210781E40DFDD52B0F
05_boundary_sample_full.txt  D5949C334546C23F3C6BC396F53747A923ED7B1E58B7D0E7BB496EACED2E09B2
06_command3_pip_install_success_full.txt  94A3F193592C9E8BED9857E3AF6E622688B520E7B163F1FD57E17896F63704D9
07_dependency_versions_full.txt  CFBF2D27EE54A261807205DE005E748B140BEEB9785BD626AE29CFC6B067C6ED
08_command4_build_full.txt  DC7FD46389F8CE55ECCDCA354DA1844465AC18EDD1864A318D016CB2F8C61892
09_command5_compileall_full.txt  2C1F933A8B112835302BA8B9E3501395BDA43ED95B7539374C52CFF66B202E66
10_command6_pytest_full.txt  392B20D05019793BEB74BDF424FFA69898F0161DA36EA10604563EC9F06E27EC
11_command7_three_scenarios_full.txt  95DADE250EDDD52925C2F1CFBED4CD4248338F3662CF8D9A593477AA1D22632E
12_command8_draft_benchmark_full.txt  239EC39CEC86E653AE9D18062599394C3CB3D38FCCDF044054B2A9A6151237C8
```

`README.md` 和 `13_git_worktree_state_full.txt` 在清单生成后创建或更新，因此不把自身哈希写入自身。

## 跨 checkout 规范化校验

上面的原始字节哈希保留为 2026-07-28 的历史记录；其中前 5 个日志会受 Git
`core.autocrlf` 影响，不作为跨操作系统校验依据。新的权威清单是
`checksums.canonical-sha256.json`：按 BOM 读取 UTF-8/UTF-16，将 CRLF/CR 统一为
LF，再以无 BOM 的 UTF-8 计算 SHA-256。运行：

```powershell
python scripts/verify_artifact_hashes.py
```

校验器只读原始日志，不会修改历史证据。

> 2026-07-30 全面验收曾发现当前 checkout 中前 5 个原始字节哈希与上表不一致，
> 其余 7 项一致。该历史缺口现已由上面的规范化清单和只读校验器关闭；
> 原始字节哈希继续保留为当时记录，不再作为跨 checkout 的权威判断依据。
> 原始发现见 `docs/验收记录_E1_全面验收.md`，整改见
> `docs/验收记录_2026-08-01_日报问题整改.md`。

