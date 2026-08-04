"""校验证据文本的跨平台规范化 SHA-256 清单。"""

from __future__ import annotations

import argparse
import codecs
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "artifacts"
    / "p2_offline_reproduction_20260728"
    / "checksums.canonical-sha256.json"
)


def canonical_text_sha256(path: Path) -> str:
    """按 BOM 解码 UTF-8/UTF-16，并忽略 BOM 与 CRLF/LF 差异。"""
    raw = path.read_bytes()
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_manifest(manifest_path: Path) -> list[str]:
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent.resolve()
    errors: list[str] = []
    for relative_name, expected in manifest.get("files", {}).items():
        target = (base / relative_name).resolve()
        if target.parent != base:
            errors.append(f"非法清单路径：{relative_name}")
            continue
        if not target.is_file():
            errors.append(f"文件不存在：{relative_name}")
            continue
        actual = canonical_text_sha256(target)
        if actual != expected:
            errors.append(f"哈希不一致：{relative_name} expected={expected} actual={actual}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    errors = verify_manifest(manifest_path)
    if errors:
        print("[FAIL] 证据哈希校验失败")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"[PASS] 证据哈希校验通过：{manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
