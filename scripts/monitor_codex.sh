#!/usr/bin/env bash
# Codex 任务监控循环：每 5 分钟探活（不报告），每 15 分钟企微汇报进度
# 卡死检测：Codex 进程存在但输出文件 20 分钟未增长 → 判卡死并立即企微告警
# 用法: bash scripts/monitor_codex.sh <codex会话ID或进程关键字> <状态文件>
set -u

PROC_KEY="${1:-codex}"          # pgrep 关键字
STATE_FILE="${2:-artifacts/zg_profile_comparison_20260808/进度状态.json}"
REPORT_SCRIPT="$(cd "$(dirname "$0")" && pwd)/wecom_report.sh"
LOG="artifacts/zg_profile_comparison_20260808/monitor_codex.log"

cd "$(dirname "$0")/.." || exit 1
mkdir -p "$(dirname "$LOG")"
touch "$LOG"

# 记录某次探活的 codex 进程输出体积（字节），用于卡死检测
LAST_SIZE=0
LAST_SIZE_TIME=$(date +%s)
LAST_REPORT=$(date +%s)
STALL_THRESHOLD=1200   # 20 分钟无进展判卡死
REPORT_INTERVAL=900    # 15 分钟企微汇报

log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" >> "$LOG"; }

while true; do
  NOW=$(date +%s)

  # ── 每 5 分钟探活（不报告）──
  if pgrep -f "$PROC_KEY" > /dev/null 2>&1; then
    ALIVE=1
  else
    ALIVE=0
  fi

  # 计算 codex 输出进展（用日志/临时文件体积近似；codex 无固定日志时用最近心跳文件）
  PROC_SIZE_FILE="artifacts/zg_profile_comparison_20260808/codex_progress.txt"
  if [ -f "$PROC_SIZE_FILE" ]; then
    SIZE=$(wc -c < "$PROC_SIZE_FILE" | tr -d ' ')
  else
    SIZE=0
  fi

  # ── 卡死检测：进程活着但 20 分钟输出没增长 ──
  if [ "$ALIVE" = 1 ] && [ "$SIZE" -gt 0 ] && [ "$SIZE" -le "$LAST_SIZE" ]; then
    if [ $((NOW - LAST_SIZE_TIME)) -ge "$STALL_THRESHOLD" ]; then
      log "⚠️ 卡死检测：codex 进程存活但输出 $STALL_THRESHOLD 秒未增长 (size=$SIZE)"
      bash "$REPORT_SCRIPT" "🚨【智策育训整改-卡死告警】Codex 进程存活但 20 分钟无输出进展（size=$SIZE）。请检查：\n- 是否在等待输入（如需回答请用 process submit）\n- 是否网络/API 卡住\n我会继续监控，若持续无进展将上报。" >> "$LOG" 2>&1
      LAST_SIZE_TIME=$NOW  # 重置计时，避免重复刷屏
    fi
  else
    LAST_SIZE=$SIZE
    LAST_SIZE_TIME=$NOW
  fi

  # ── 每 15 分钟企微汇报 ──
  if [ $((NOW - LAST_REPORT)) -ge "$REPORT_INTERVAL" ]; then
    if [ -f "$STATE_FILE" ]; then
      STAGE=$(python3 -c "import json;print(json.load(open('$STATE_FILE'))['阶段'])" 2>/dev/null || echo "?")
      STATUS=$(python3 -c "import json;print(json.load(open('$STATE_FILE'))['状态'])" 2>/dev/null || echo "?")
      SUMMARY=$(python3 -c "import json;print(json.load(open('$STATE_FILE'))['进度摘要'])" 2>/dev/null || echo "?")
    else
      STAGE="?"; STATUS="?"; SUMMARY="状态文件缺失"
    fi
    ALIVE_TXT=$([ "$ALIVE" = 1 ] && echo "运行中" || echo "已结束/未启动")
    bash "$REPORT_SCRIPT" "📊【智策育训整改-${STAGE}】Codex进程: ${ALIVE_TXT} | 状态: ${STATUS} | 进度: ${SUMMARY}" >> "$LOG" 2>&1
    LAST_REPORT=$NOW
    log "15分钟例行汇报完成 (alive=$ALIVE_TXT stage=$STAGE)"
  fi

  sleep 300  # 5 分钟一轮
done
