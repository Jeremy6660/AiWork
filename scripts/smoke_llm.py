"""真实模型手动 smoke 门禁；默认 dry-run，绝不隐式发起请求。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_text = str(PROJECT_ROOT)
if project_root_text in sys.path:
    sys.path.remove(project_root_text)
sys.path.insert(0, project_root_text)

import src.zhice_yuxun.llm_client as llm_client_module
from src.zhice_yuxun.llm_client import LLMError, PROVIDERS, call_llm_json


SCENARIOS = {
    "generate": [
        {
            "role": "system",
            "content": "你是制造业培训内容 smoke test，只输出严格 JSON。",
        },
        {
            "role": "user",
            "content": (
                '只返回严格 JSON：{"通过": true, "说明": "smoke"}。'
                "不要补充参数、标准或安全结论。"
            ),
        },
    ]
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="真实模型手动 smoke 门禁")
    parser.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    parser.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    parser.add_argument(
        "--execute",
        action="store_true",
        help="允许在再次人工确认后发起 1 次逻辑调用；默认仅 dry-run",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = PROVIDERS[args.provider]
    model = os.getenv(config.model_env, config.default_model)
    key_configured = bool(os.getenv(config.key_env, "").strip())

    print(f"供应商：{args.provider}")
    print(f"模型：{model}")
    print(f"场景：{args.scenario}")
    print(f"适配器路径：{Path(llm_client_module.__file__).resolve()}")
    print(f"Key 已配置：{'是' if key_configured else '否'}")
    print(f"预计逻辑调用次数：{1 if args.execute else 0}")

    if not args.execute:
        print("[DRY-RUN] 未发起任何网络请求。")
        return 0
    if not key_configured:
        print(f"[BLOCKED] 未配置 {config.key_env}，未创建客户端。")
        return 2

    confirmation = input(
        "即将发起可能产生费用的真实调用。输入 EXECUTE 确认，其余输入取消："
    ).strip()
    if confirmation != "EXECUTE":
        print("[CANCELLED] 操作者未确认，未发起请求。")
        return 3

    started = time.perf_counter()
    try:
        result = call_llm_json(
            args.provider,
            SCENARIOS[args.scenario],
            timeout=20.0,
            max_attempts=1,
        )
    except LLMError as exc:
        elapsed = time.perf_counter() - started
        print(f"[FAILED] 耗时秒：{elapsed:.3f}")
        print(f"失败类型：{type(exc).__name__}")
        return 1

    elapsed = time.perf_counter() - started
    sanitized = {
        "供应商": args.provider,
        "模型": result.get("_模型", model),
        "场景": args.scenario,
        "耗时秒": round(elapsed, 3),
        "结果字段": sorted(key for key in result if not key.startswith("_")),
    }
    print("[PASS] 脱敏结果：")
    print(json.dumps(sanitized, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
