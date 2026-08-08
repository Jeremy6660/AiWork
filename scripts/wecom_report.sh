#!/usr/bin/env bash
# 企微进度汇报脚本（整改期间 15 分钟一次）
# 用法: bash scripts/wecom_report.sh "消息文本"
# 依赖: env -i 干净环境调用 hermes send（会话 env 污染会误报 wecom 未配置）
set -u

MSG="${1:-}"
if [ -z "$MSG" ]; then
  echo "usage: wecom_report.sh <消息文本>" >&2
  exit 2
fi

HERMES_BIN=/Users/xuyunze/.hermes/hermes-agent/venv/bin/hermes
OUT=$(env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin "$HERMES_BIN" send --to wecom "$MSG" 2>&1)
RC=$?
if [ $RC -eq 0 ] && echo "$OUT" | grep -q "Sent to wecom"; then
  echo "[OK] 企微已发送: ${MSG:0:60}..."
  exit 0
else
  echo "[FAIL] 企微发送失败 rc=$RC out=$OUT" >&2
  exit 1
fi
